param()

$ErrorActionPreference = 'Stop'

$Startup = [Environment]::GetFolderPath("Startup")
$ShortcutPath = Join-Path $Startup "FRAM Always On.lnk"

if (Test-Path $ShortcutPath) {
  Remove-Item -Path $ShortcutPath -Force
  Write-Host "Autostart disabled: $ShortcutPath"
} else {
  Write-Host "Autostart shortcut not found: $ShortcutPath"
}
