# ==============================================================================
#  IMMORTAL SUPERVISOR & SCHEDULED TASK SERVICE FOR WINDOWS (PRESIDENT PC)
#  AlphaForge 24/7 Autonomous Quantitative Hedge Fund Swarm
# ==============================================================================
param(
    [switch]$InstallTask,
    [switch]$UninstallTask,
    [switch]$StartTask,
    [switch]$StopTask,
    [switch]$Status
)

$appDir = $PSScriptRoot
if (!$appDir) { $appDir = "$HOME\Documents\Finance" }
Set-Location $appDir

$TaskName = "AlphaForgeDaemon"

# ------------------------------------------------------------------------------
# 1. TASK SCHEDULER MANAGEMENT
# ------------------------------------------------------------------------------

# Uninstall Scheduled Task
if ($UninstallTask) {
    Write-Host "[*] Removing $TaskName from Windows Task Scheduler..." -ForegroundColor Yellow
    try {
        Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction Stop
        Write-Host "[+] Successfully removed $TaskName." -ForegroundColor Green
    } catch {
        Write-Host "[-] Task $TaskName was not found or already removed." -ForegroundColor DarkGray
    }
    Exit
}

# Install Scheduled Task (Runs silently on Logon / Boot)
if ($InstallTask) {
    Write-Host "[*] Registering $TaskName in Windows Task Scheduler..." -ForegroundColor Cyan
    
    $scriptPath = Join-Path $appDir "service.ps1"
    $taskArgs = "-ExecutionPolicy Bypass -WindowStyle Hidden -File `"$scriptPath`""
    $action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument $taskArgs -WorkingDirectory $appDir
    $trigger = New-ScheduledTaskTrigger -AtLogOn
    $settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit 0
    
    Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Settings $settings -Force | Out-Null
    Write-Host "[+] Successfully registered $TaskName in Windows Task Scheduler!" -ForegroundColor Green
    Write-Host "• Mode:          Runs 24/7 in background on logon / startup" -ForegroundColor White
    Write-Host "• Location:      $appDir" -ForegroundColor White
    Write-Host "• Local URL:     http://localhost:8000" -ForegroundColor White
    Write-Host "• Tailscale URL: http://100.81.54.5:8000" -ForegroundColor White
    Write-Host "• Start now:     powershell -ExecutionPolicy Bypass -File `"$scriptPath`" -StartTask" -ForegroundColor Gray
    Exit
}

# Start Task
if ($StartTask) {
    Write-Host "[*] Starting $TaskName via Task Scheduler..." -ForegroundColor Cyan
    Start-ScheduledTask -TaskName $TaskName
    Write-Host "[+] $TaskName trigger sent. Check status in a few seconds." -ForegroundColor Green
    Exit
}

# Stop Task
if ($StopTask) {
    Write-Host "[*] Stopping $TaskName..." -ForegroundColor Yellow
    try { Stop-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue } catch { }
    Get-Process -Name "python" -ErrorAction SilentlyContinue | Where-Object { $_.Path -like "*Finance*" } | Stop-Process -Force -ErrorAction SilentlyContinue
    Write-Host "[+] $TaskName stopped." -ForegroundColor Green
    Exit
}

# Status Check
if ($Status) {
    Write-Host "==========================================================" -ForegroundColor Cyan
    Write-Host " 🔍 ALPHAFORGE 24/7 SERVICE STATUS" -ForegroundColor Green
    Write-Host "==========================================================" -ForegroundColor Cyan
    
    $task = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    if ($task) {
        Write-Host ("• Task Scheduler: Registered (State: " + $task.State + ")") -ForegroundColor Green
    } else {
        Write-Host "• Task Scheduler: Not registered (Use -InstallTask to register)" -ForegroundColor Yellow
    }
    
    try {
        $apiStatus = Invoke-RestMethod -Uri "http://localhost:8000/api/status" -TimeoutSec 3 -ErrorAction Stop
        Write-Host "• Engine Status:  ONLINE" -ForegroundColor Green
        Write-Host ("• Uptime:         " + $apiStatus.uptime_human) -ForegroundColor White
        Write-Host ("• Equity:         $" + $apiStatus.account.total_equity) -ForegroundColor White
        Write-Host ("• Signals Total:  " + $apiStatus.total_signals_detected) -ForegroundColor White
        Write-Host ("• Trades Total:   " + $apiStatus.total_trades_executed) -ForegroundColor White
    } catch {
        Write-Host "• Engine Status:  OFFLINE or Starting up (http://localhost:8000/api/status)" -ForegroundColor Red
    }
    Write-Host "==========================================================" -ForegroundColor Cyan
    Exit
}

# ------------------------------------------------------------------------------
# 2. SUPERVISOR DAEMON (ALWAYS-ON PERSISTENT RUNNER)
# ------------------------------------------------------------------------------

# Ensure data directory exists for logging
if (-not (Test-Path "$appDir\data")) {
    New-Item -ItemType Directory -Path "$appDir\data" | Out-Null
}

$supervisorLog = "$appDir\data\supervisor.log"

function Log-Message([string]$msg, [string]$color = "White") {
    $timestamp = (Get-Date).ToString("yyyy-MM-dd HH:mm:ss")
    $logLine = "[$timestamp] $msg"
    Write-Host $logLine -ForegroundColor $color
    Add-Content -Path $supervisorLog -Value $logLine -ErrorAction SilentlyContinue
}

Log-Message "==========================================================" "Cyan"
Log-Message " 🛡️  ALPHAFORGE 24/7 SUPERVISOR (ALWAYS ON)" "Green"
Log-Message (" Running directory : " + $appDir) "DarkGray"
Log-Message (" Log file          : " + $supervisorLog) "DarkGray"
Log-Message "==========================================================" "Cyan"

# Locate Python executable (.venv preferred)
$pythonPath = "python.exe"
if (Test-Path "$appDir\.venv\Scripts\python.exe") {
    $pythonPath = "$appDir\.venv\Scripts\python.exe"
}

Log-Message ("Python binary: " + $pythonPath) "DarkGray"

$forgeProcess = $null

function Start-ForgeProcess {
    global:forgeProcess
    Log-Message "[*] Starting AlphaForge 8-Agent Quant Engine (run.py)..." "Yellow"
    
    $pinfo = New-Object System.Diagnostics.ProcessStartInfo
    $pinfo.FileName = $pythonPath
    $pinfo.Arguments = "run.py"
    $pinfo.WorkingDirectory = $appDir
    $pinfo.UseShellExecute = $false
    
    $global:forgeProcess = [System.Diagnostics.Process]::Start($pinfo)
    Log-Message ("[+] AlphaForge started successfully (PID: " + $global:forgeProcess.Id + ")") "Green"
}

function Stop-ForgeProcess {
    global:forgeProcess
    if ($global:forgeProcess -and !$global:forgeProcess.HasExited) {
        Log-Message ("[*] Stopping AlphaForge process (PID: " + $global:forgeProcess.Id + ")...") "Yellow"
        try {
            $global:forgeProcess.Kill()
            $global:forgeProcess.WaitForExit(3000)
        } catch { }
        Log-Message "[+] AlphaForge stopped." "DarkGray"
    }
}

# Start AlphaForge initially
Start-ForgeProcess

# Immortal Supervision Loop
try {
    while ($true) {
        Start-Sleep -Seconds 5
        
        # Health Check: Did process exit/crash?
        if ($global:forgeProcess.HasExited) {
            $exitCode = $global:forgeProcess.ExitCode
            Log-Message ("[!] AlphaForge engine exited unexpectedly with code " + $exitCode + "! Restarting in 3 seconds...") "Red"
            Start-Sleep -Seconds 3
            Start-ForgeProcess
        }
    }
} finally {
    Stop-ForgeProcess
}
