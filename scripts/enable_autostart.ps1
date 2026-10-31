param()

$ErrorActionPreference = 'Stop'

$ScriptDir = Split-Path -Path $MyInvocation.MyCommand.Path -Parent
$RepoRoot = Split-Path -Path $ScriptDir -Parent
$Target = Join-Path $RepoRoot "scripts\\autostart_fram.cmd"
$Startup = [Environment]::GetFolderPath("Startup")
$ShortcutPath = Join-Path $Startup "FRAM Always On.lnk"

if (-not (Test-Path $Target)) {
  throw "Missing autostart target: $Target"
}

$Shell = New-Object -ComObject WScript.Shell
$Shortcut = $Shell.CreateShortcut($ShortcutPath)
$Shortcut.TargetPath = $Target
$Shortcut.WorkingDirectory = $RepoRoot
$Shortcut.Save()

Write-Host "Autostart enabled: $ShortcutPath"
