param(
    [switch]$Apply
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$ClaudeHome = Join-Path $HOME ".claude"
$LocalSettings = Join-Path $ClaudeHome "settings.local.json"
$ActiveSettings = Join-Path $ClaudeHome "settings.json"
$GeneratedSettings = Join-Path $Root ".claude/settings.generated.json"
$Python = (Get-Command python3 -ErrorAction SilentlyContinue)
if (-not $Python) { $Python = Get-Command py -ErrorAction Stop }

function Install-Link([string]$Source, [string]$Target) {
    if (Test-Path $Target) {
        $item = Get-Item $Target -Force
        if ($item.LinkType -and $item.Target -eq $Source) {
            Write-Host "ok      $Target"
            return
        }
        throw "conflict $Target already exists; move or merge it manually"
    }
    if ($Apply) {
        New-Item -ItemType Directory -Force -Path (Split-Path -Parent $Target) | Out-Null
        New-Item -ItemType SymbolicLink -Path $Target -Target $Source | Out-Null
        Write-Host "linked  $Target -> $Source"
    } else {
        Write-Host "would   $Target -> $Source"
    }
}

Write-Host ("Portable Claude Code bootstrap ({0})" -f $(if ($Apply) { "apply" } else { "dry-run" }))

$MergeLocal = $LocalSettings
$PreserveLocal = $false
if ((Test-Path $ActiveSettings) -and -not (Test-Path $LocalSettings)) {
    $MergeLocal = $ActiveSettings
    $PreserveLocal = $true
    Write-Host "would   preserve existing settings at $LocalSettings"
} elseif ((Test-Path $ActiveSettings) -and (Test-Path $LocalSettings)) {
    throw "conflict $ActiveSettings and $LocalSettings both exist; merge them manually"
}

if ($Apply) {
    if (-not (Get-Command claude -ErrorAction SilentlyContinue)) {
        throw "Claude Code CLI is required for -Apply; install it and rerun."
    }
    & $Python.Source (Join-Path $Root "scripts/sync_config.py") `
        --base (Join-Path $Root ".claude/settings.json") `
        --local $MergeLocal --output $GeneratedSettings
    if ($PreserveLocal) { Move-Item $ActiveSettings $LocalSettings }
    New-Item -ItemType Directory -Force -Path $ClaudeHome | Out-Null
    Copy-Item $GeneratedSettings $ActiveSettings
} else {
    Write-Host "would   merge portable settings with $LocalSettings"
    Write-Host "would   install merged settings at $ActiveSettings"
}

Install-Link (Join-Path $Root "CLAUDE.global.md") (Join-Path $ClaudeHome "CLAUDE.md")
Install-Link (Join-Path $Root ".claude/hooks") (Join-Path $ClaudeHome "hooks")
Install-Link (Join-Path $Root ".claude/agents") (Join-Path $ClaudeHome "agents")
Install-Link (Join-Path $Root "skills") (Join-Path $ClaudeHome "skills")

if ($Apply) {
    & claude mcp add --transport http --scope user context7 https://mcp.context7.com/mcp
    & claude mcp add --transport stdio --scope user codebase_memory -- npx -y codebase-memory-mcp@0.8.1
    if ($env:GITHUB_PAT_TOKEN) {
        $Github = '{"type":"http","url":"https://api.githubcopilot.com/mcp/","headers":{"Authorization":"Bearer ${GITHUB_PAT_TOKEN}"}}'
        & claude mcp add-json --scope user github $Github
    }
} else {
    Write-Host "would   add user MCP servers: context7, codebase_memory"
    Write-Host "would   add user MCP server github only when GITHUB_PAT_TOKEN is set"
    Write-Host "Dry-run only. Install Claude Code, then rerun with -Apply after resolving conflicts."
}
