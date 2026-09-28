# ==============================================================================
#  24/7 SUPERVISOR & SCHEDULED TASK SERVICE FOR WINDOWS (PRESIDENT PC)
#  AlphaForge Autonomous Multi-Agent Swarm
#
#  One-time setup (elevated PowerShell, from the repo folder):
#    powershell -ExecutionPolicy Bypass -File .\service.ps1 -InstallTask
#    powershell -ExecutionPolicy Bypass -File .\service.ps1 -StartTask
#
#  Other commands: -Status, -StopTask, -Restart, -Update, -UninstallTask
#  (ASCII only: Windows PowerShell 5.1 misreads UTF-8 files without a BOM)
# ==============================================================================
param(
    [switch]$InstallTask,
    [switch]$UninstallTask,
    [switch]$StartTask,
    [switch]$StopTask,
    [switch]$Restart,
    [switch]$Update,
    [switch]$Status
)

$appDir = $PSScriptRoot
if (!$appDir) { $appDir = Join-Path $HOME 'Documents\Finance' }
Set-Location $appDir

$TaskName = 'AlphaForgeDaemon'
$Port = 8000
$HealthUrl = 'http://127.0.0.1:' + $Port + '/api/health'
$StatusUrl = 'http://127.0.0.1:' + $Port + '/api/status'

$dataDir = Join-Path $appDir 'data'
if (-not (Test-Path $dataDir)) { New-Item -ItemType Directory -Path $dataDir | Out-Null }
$supervisorLog = Join-Path $dataDir 'supervisor.log'
$engineOutLog = Join-Path $dataDir 'engine_stdout.log'
$engineErrLog = Join-Path $dataDir 'engine_stderr.log'

function Write-LogLine([string]$message, [string]$color = 'White') {
    $timestamp = (Get-Date).ToString('yyyy-MM-dd HH:mm:ss')
    $line = '[' + $timestamp + '] ' + $message
    Write-Host $line -ForegroundColor $color
    Add-Content -Path $supervisorLog -Value $line -ErrorAction SilentlyContinue
}

function Test-Admin {
    $id = [Security.Principal.WindowsIdentity]::GetCurrent()
    return (New-Object Security.Principal.WindowsPrincipal($id)).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Get-EngineProcesses {
    # python processes running run.py from this folder
    Get-CimInstance Win32_Process -Filter "Name='python.exe'" -ErrorAction SilentlyContinue |
        Where-Object { $_.CommandLine -like '*run.py*' -and ($_.ExecutablePath -like ($appDir + '*') -or $_.CommandLine -like ('*' + $appDir + '*')) }
}

function Stop-EngineProcesses {
    Get-EngineProcesses | ForEach-Object {
        try { Stop-Process -Id $_.ProcessId -Force -ErrorAction Stop } catch { }
    }
}

function Get-ApiToken {
    $envFile = Join-Path $appDir '.env'
    if (Test-Path $envFile) {
        $line = Get-Content $envFile | Where-Object { $_ -like 'API_TOKEN=*' } | Select-Object -First 1
        if ($line) { return $line.Substring(10).Trim() }
    }
    return ''
}

function Test-EngineHealthy {
    try {
        Invoke-RestMethod -Uri $HealthUrl -TimeoutSec 10 -ErrorAction Stop | Out-Null
        return $true
    } catch {
        return $false
    }
}

# ------------------------------------------------------------------------------
# 1. TASK SCHEDULER MANAGEMENT
# ------------------------------------------------------------------------------

if ($UninstallTask) {
    Write-Host ('[*] Removing ' + $TaskName + ' from Task Scheduler...') -ForegroundColor Yellow
    try { Stop-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue } catch { }
    Stop-EngineProcesses
    try {
        Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction Stop
        Write-Host '[+] Removed scheduled task.' -ForegroundColor Green
    } catch {
        Write-Host '[-] Task not found or already removed.' -ForegroundColor DarkGray
    }
    Exit
}

if ($InstallTask) {
    if (-not (Test-Admin)) {
        Write-Host '[-] Run this from an elevated (Administrator) PowerShell.' -ForegroundColor Red
        Exit 1
    }
    Write-Host '[*] Registering in Windows Task Scheduler...' -ForegroundColor Cyan

    $scriptPath = Join-Path $appDir 'service.ps1'
    $taskArgs = '-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "' + $scriptPath + '"'
    $action = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument $taskArgs -WorkingDirectory $appDir

    # Start at boot (no login needed) and also at logon as a safety net.
    $triggers = @(
        (New-ScheduledTaskTrigger -AtStartup),
        (New-ScheduledTaskTrigger -AtLogOn)
    )

    # S4U = run whether the user is logged on or not, without storing a password.
    $user = [Security.Principal.WindowsIdentity]::GetCurrent().Name
    $principal = New-ScheduledTaskPrincipal -UserId $user -LogonType S4U -RunLevel Highest

    # Restart the supervisor itself if it ever dies; never time out; only one instance.
    $settings = New-ScheduledTaskSettingsSet `
        -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
        -StartWhenAvailable -ExecutionTimeLimit ([TimeSpan]::Zero) `
        -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1) `
        -MultipleInstances IgnoreNew

    Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $triggers `
        -Principal $principal -Settings $settings -Force | Out-Null

    # Keep the PC awake on AC power so the swarm never pauses.
    powercfg /change standby-timeout-ac 0 | Out-Null
    powercfg /change hibernate-timeout-ac 0 | Out-Null

    Write-Host '[+] Registered in Task Scheduler.' -ForegroundColor Green
    Write-Host ('  Mode:      starts at boot, runs whether logged on or not (' + $user + ')') -ForegroundColor White
    Write-Host '  Power:     sleep + hibernate on AC disabled' -ForegroundColor White
    Write-Host ('  Location:  ' + $appDir) -ForegroundColor White
    Write-Host ('  Local URL: http://localhost:' + $Port) -ForegroundColor White
    Write-Host ('  Start now: powershell -ExecutionPolicy Bypass -File "' + $scriptPath + '" -StartTask') -ForegroundColor Gray
    Exit
}

if ($StartTask) {
    Write-Host '[*] Starting service via Task Scheduler...' -ForegroundColor Cyan
    Start-ScheduledTask -TaskName $TaskName
    Write-Host '[+] Trigger sent. Check with -Status in ~20 seconds.' -ForegroundColor Green
    Exit
}

if ($StopTask) {
    Write-Host '[*] Stopping service...' -ForegroundColor Yellow
    try { Stop-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue } catch { }
    Stop-EngineProcesses
    Write-Host '[+] Service stopped.' -ForegroundColor Green
    Exit
}

if ($Restart) {
    # Kill only the engine; the supervisor loop brings it back within seconds.
    Write-Host '[*] Restarting engine (supervisor will relaunch it)...' -ForegroundColor Yellow
    Stop-EngineProcesses
    Write-Host '[+] Engine killed.' -ForegroundColor Green
    Exit
}

if ($Update) {
    Write-Host '[*] Pulling latest code...' -ForegroundColor Cyan
    git -C $appDir pull --ff-only
    if ($LASTEXITCODE -ne 0) { Write-Host '[-] git pull failed; not restarting.' -ForegroundColor Red; Exit 1 }
    $venvPip = Join-Path $appDir '.venv\Scripts\pip.exe'
    if (Test-Path $venvPip) { & $venvPip install -q -r (Join-Path $appDir 'requirements.txt') }
    Stop-EngineProcesses
    Write-Host '[+] Updated. Supervisor will relaunch the engine.' -ForegroundColor Green
    Exit
}

if ($Status) {
    Write-Host '==========================================================' -ForegroundColor Cyan
    Write-Host ' ALPHAFORGE 24/7 SERVICE STATUS' -ForegroundColor Green
    Write-Host '==========================================================' -ForegroundColor Cyan

    $task = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    if ($task) {
        Write-Host ('  Task Scheduler: Registered (State: ' + $task.State + ')') -ForegroundColor Green
    } else {
        Write-Host '  Task Scheduler: Not registered (use -InstallTask)' -ForegroundColor Yellow
    }

    $procs = @(Get-EngineProcesses)
    Write-Host ('  Engine PIDs:    ' + (($procs | ForEach-Object { $_.ProcessId }) -join ', ')) -ForegroundColor White

    try {
        $headers = @{ 'X-API-Key' = (Get-ApiToken) }
        $apiStatus = Invoke-RestMethod -Uri $StatusUrl -Headers $headers -TimeoutSec 5 -ErrorAction Stop
        Write-Host '  Engine Status:  ONLINE' -ForegroundColor Green
        Write-Host ('  Uptime:         ' + $apiStatus.uptime_human) -ForegroundColor White
        Write-Host ('  Equity:         USD ' + $apiStatus.account.total_equity) -ForegroundColor White
        Write-Host ('  Signals Total:  ' + $apiStatus.total_signals_detected) -ForegroundColor White
        Write-Host ('  Trades Total:   ' + $apiStatus.total_trades_executed) -ForegroundColor White
    } catch {
        Write-Host ('  Engine Status:  OFFLINE or starting up (' + $StatusUrl + ')') -ForegroundColor Red
    }
    Write-Host ('  Logs:           ' + $supervisorLog) -ForegroundColor DarkGray
    Write-Host '==========================================================' -ForegroundColor Cyan
    Exit
}

# ------------------------------------------------------------------------------
# 2. SUPERVISOR DAEMON (ALWAYS-ON PERSISTENT RUNNER)
# ------------------------------------------------------------------------------

# Single-instance guard: a second supervisor would fight over port 8000.
$mutex = New-Object System.Threading.Mutex($false, 'Global\AlphaForgeSupervisor')
if (-not $mutex.WaitOne(0)) {
    Write-LogLine '[!] Another supervisor is already running. Exiting.' 'Yellow'
    Exit
}

Write-LogLine '==========================================================' 'Cyan'
Write-LogLine ' ALPHAFORGE 24/7 SUPERVISOR (ALWAYS ON)' 'Green'
Write-LogLine (' Running directory : ' + $appDir) 'DarkGray'
Write-LogLine (' Log file          : ' + $supervisorLog) 'DarkGray'
Write-LogLine '==========================================================' 'Cyan'

$pythonPath = 'python.exe'
$venvPython = Join-Path $appDir '.venv\Scripts\python.exe'
if (Test-Path $venvPython) { $pythonPath = $venvPython }
Write-LogLine ('Python binary: ' + $pythonPath) 'DarkGray'

# Clear leftovers from a previous crashed supervisor so the port is free.
Stop-EngineProcesses

$global:forgeProcess = $null
$global:startedAt = Get-Date
$global:failedHealthChecks = 0
$restartDelay = 3

function Rotate-Log([string]$path) {
    if ((Test-Path $path) -and ((Get-Item $path).Length -gt 20MB)) {
        Move-Item -Force $path ($path + '.1')
    }
}

function Start-ForgeProcess {
    Rotate-Log $engineOutLog
    Rotate-Log $engineErrLog
    Rotate-Log $supervisorLog
    Write-LogLine '[*] Starting AlphaForge engine (run.py)...' 'Yellow'
    $env:PYTHONUNBUFFERED = '1'
    $env:PYTHONIOENCODING = 'utf-8'
    $global:forgeProcess = Start-Process -FilePath $pythonPath -ArgumentList 'run.py' `
        -WorkingDirectory $appDir -WindowStyle Hidden -PassThru `
        -RedirectStandardOutput $engineOutLog -RedirectStandardError $engineErrLog
    $global:startedAt = Get-Date
    $global:failedHealthChecks = 0
    Write-LogLine ('[+] Engine started (PID: ' + $global:forgeProcess.Id + ')') 'Green'
}

function Stop-ForgeProcess {
    if ($global:forgeProcess -and !$global:forgeProcess.HasExited) {
        Write-LogLine ('[*] Stopping PID ' + $global:forgeProcess.Id + '...') 'Yellow'
        try {
            $global:forgeProcess.Kill()
            $global:forgeProcess.WaitForExit(5000) | Out-Null
        } catch { }
    }
}

Start-ForgeProcess

try {
    while ($true) {
        Start-Sleep -Seconds 10

        if ($global:forgeProcess.HasExited) {
            # Back off if it keeps crashing right after start (bad code / bad .env).
            $ranFor = ((Get-Date) - $global:startedAt).TotalSeconds
            if ($ranFor -lt 60) { $restartDelay = [Math]::Min($restartDelay * 2, 300) } else { $restartDelay = 3 }
            Write-LogLine ('[!] Engine exited (code ' + $global:forgeProcess.ExitCode + ') after ' + [int]$ranFor + 's. Restarting in ' + $restartDelay + 's...') 'Red'
            Start-Sleep -Seconds $restartDelay
            Start-ForgeProcess
            continue
        }

        # Hang detection: process alive but API unresponsive for ~3 minutes.
        if (((Get-Date) - $global:startedAt).TotalSeconds -gt 90) {
            if (Test-EngineHealthy) {
                $global:failedHealthChecks = 0
            } else {
                $global:failedHealthChecks++
                if ($global:failedHealthChecks -ge 18) {
                    Write-LogLine '[!] Engine unresponsive for 3 minutes. Killing and restarting...' 'Red'
                    Stop-ForgeProcess
                    Start-Sleep -Seconds 3
                    Start-ForgeProcess
                }
            }
        }
    }
} finally {
    Stop-ForgeProcess
    $mutex.ReleaseMutex()
}
