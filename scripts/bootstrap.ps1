param([switch]$Apply)

$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path

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

$CodexHome = Join-Path $HOME ".codex"
Link-ItemSafely (Join-Path $Root "AGENTS.global.md") (Join-Path $CodexHome "AGENTS.md")
Link-ItemSafely (Join-Path $Root ".codex/config.toml") (Join-Path $CodexHome "config.toml")
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

