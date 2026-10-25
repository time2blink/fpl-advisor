# Creates a desktop shortcut "FPL Advisor" that runs run.bat (updates data and opens the dashboard).
$toolDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$desktop = [Environment]::GetFolderPath('Desktop')
$lnkPath = Join-Path $desktop 'FPL Advisor.lnk'
$ws = New-Object -ComObject WScript.Shell
$lnk = $ws.CreateShortcut($lnkPath)
$lnk.TargetPath = Join-Path $toolDir 'run.bat'
$lnk.WorkingDirectory = $toolDir
$lnk.IconLocation = (Join-Path $toolDir 'assets\fpl_advisor.ico') + ',0'
$lnk.Description = 'FPL Advisor: update data and open dashboard'
$lnk.WindowStyle = 1
$lnk.Save()
Write-Host "Shortcut created: $lnkPath"
