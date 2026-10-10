$ErrorActionPreference = 'Stop'
$composePath = (Join-Path $PSScriptRoot 'compose.ha-test.yaml').Replace('\', '/')
$linuxCompose = (& wsl -d Ubuntu -- wslpath -u $composePath).Trim()
if ($LASTEXITCODE -ne 0) { throw 'Cannot resolve the test environment path in WSL.' }
& wsl -d Ubuntu -u root -- docker compose -f $linuxCompose up -d
if ($LASTEXITCODE -ne 0) { throw 'Cannot start the isolated HA development container.' }
# systemd services alone do not keep a WSL distro alive. Hold a normal WSL
# process until this specific development container stops; no system policy change.
$keeper = Start-Process -FilePath 'wsl.exe' -ArgumentList @('-d','Ubuntu','-u','root','--','docker','wait','fanuc-ha-test') -WindowStyle Hidden -PassThru
& wsl -d Ubuntu -u root -- docker exec -d fanuc-ha-test bash -lc 'supervisor_run > /tmp/fanuc-supervisor.log 2>&1'
if ($LASTEXITCODE -ne 0) { throw 'Cannot start the isolated Supervisor.' }
Write-Output "Test Home Assistant is starting at http://127.0.0.1:7123 (WSL keeper PID $($keeper.Id))."
