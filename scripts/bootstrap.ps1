param([switch]$Apply)

$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$Python = if (Get-Command python3 -ErrorAction SilentlyContinue) { "python3" } else { "python" }

function Link-ItemSafely {
    param([string]$Source, [string]$Target)

    if (Test-Path -LiteralPath $Target) {
        $item = Get-Item -LiteralPath $Target -Force
        if ($item.LinkType -and $item.Target -contains $Source) {
            Write-Host "ok      $Target"
            return
        }
        throw "Conflict: $Target already exists. Move or merge it manually."
    }

    if ($Apply) {
        $parent = Split-Path -Parent $Target
        New-Item -ItemType Directory -Force -Path $parent | Out-Null
        New-Item -ItemType SymbolicLink -Path $Target -Target $Source | Out-Null
        Write-Host "linked  $Target -> $Source"
    } else {
        Write-Host "would   $Target -> $Source"
    }
}

function Install-MergedConfig {
    param([string]$CodexHome)

    $target = Join-Path $CodexHome "config.toml"
    $local = Join-Path $CodexHome "config.local.toml"
    $generated = Join-Path $Root ".codex/config.generated.toml"
    $base = Join-Path $Root ".codex/config.toml"
    $sync = Join-Path $Root "scripts/sync_config.py"

    if (Test-Path -LiteralPath $target) {
        $item = Get-Item -LiteralPath $target -Force
        if ($item.LinkType) {
            if (-not ($item.Target -contains $generated)) {
                throw "Conflict: $target points somewhere else."
            }
        } elseif (Test-Path -LiteralPath $local) {
            throw "Conflict: $target and $local both exist; merge them manually."
        } elseif ($Apply) {
            Move-Item -LiteralPath $target -Destination $local
            Write-Host "local   preserved existing config at $local"
        } else {
            Write-Host "would   preserve existing config at $local"
        }
    }

    if ($Apply) {
        & $Python $sync --base $base --local $local --output $generated
        if ($LASTEXITCODE -ne 0) { throw "Config merge failed." }
        if (-not (Test-Path -LiteralPath $target)) {
            New-Item -ItemType SymbolicLink -Path $target -Target $generated | Out-Null
            Write-Host "linked  $target -> $generated"
        } else {
            Write-Host "ok      $target"
        }
    } else {
        Write-Host "would   merge portable base with $local"
        Write-Host "would   $target -> $generated"
    }
}

$CodexHome = Join-Path $HOME ".codex"
Link-ItemSafely (Join-Path $Root "AGENTS.global.md") (Join-Path $CodexHome "AGENTS.md")
Install-MergedConfig $CodexHome
Link-ItemSafely (Join-Path $Root ".codex/hooks.json") (Join-Path $CodexHome "hooks.json")
Link-ItemSafely (Join-Path $Root ".codex/hooks") (Join-Path $CodexHome "hooks")
Link-ItemSafely (Join-Path $Root ".codex/agents") (Join-Path $CodexHome "agents")
Link-ItemSafely (Join-Path $Root "skills") (Join-Path $HOME ".agents/skills")

Get-ChildItem (Join-Path $Root "profiles") -Filter "*.config.toml" | ForEach-Object {
    Link-ItemSafely $_.FullName (Join-Path $CodexHome $_.Name)
}

if (-not $Apply) {
    Write-Host "Dry-run only. Re-run with -Apply after resolving any conflicts."
}
