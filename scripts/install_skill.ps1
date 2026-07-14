param(
    [string]$CodexHome = $(if ($env:CODEX_HOME) { $env:CODEX_HOME } else { Join-Path $HOME ".codex" })
)

$source = Join-Path (Split-Path $PSScriptRoot -Parent) "skills\zentao-monthly-worklog"
$skillsRoot = Join-Path $CodexHome "skills"
$target = Join-Path $skillsRoot "zentao-monthly-worklog"

New-Item -ItemType Directory -Force -Path $skillsRoot | Out-Null
New-Item -ItemType Directory -Force -Path $target | Out-Null
Copy-Item -Path (Join-Path $source "*") -Destination $target -Recurse -Force

Write-Host "Installed zentao-monthly-worklog to $target"
