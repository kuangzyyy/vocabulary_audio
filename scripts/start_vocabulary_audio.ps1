param(
    [switch]$NoBrowser
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$frontendDir = Join-Path $root 'frontend'
$logsDir = Join-Path $root 'logs'
$python = Join-Path $root '.venv\Scripts\python.exe'
$backendOut = Join-Path $logsDir 'backend.stdout.log'
$backendErr = Join-Path $logsDir 'backend.stderr.log'
$frontendOut = Join-Path $logsDir 'frontend.stdout.log'
$frontendErr = Join-Path $logsDir 'frontend.stderr.log'

New-Item -ItemType Directory -Force -Path $logsDir | Out-Null
Set-Location $root

function Write-Step {
    param([string]$Message)
    Write-Host "[Vocabulary Audio] $Message"
}

function Test-Port {
    param([int]$Port)
    $client = New-Object System.Net.Sockets.TcpClient
    try {
        $result = $client.BeginConnect('127.0.0.1', $Port, $null, $null)
        if (-not $result.AsyncWaitHandle.WaitOne(300)) {
            return $false
        }
        $client.EndConnect($result)
        return $true
    } catch {
        return $false
    } finally {
        $client.Close()
    }
}

function Test-Backend {
    try {
        $response = Invoke-RestMethod -Uri 'http://127.0.0.1:8000/api/health' -TimeoutSec 2
        return $response.service -eq 'vocabulary-audio'
    } catch {
        return $false
    }
}

function Test-Frontend {
    try {
        $response = Invoke-WebRequest -UseBasicParsing -Uri 'http://127.0.0.1:5173/' -TimeoutSec 2
        return $response.StatusCode -eq 200 -and $response.Content -match 'Vocabulary Audio'
    } catch {
        return $false
    }
}

function Wait-Http {
    param(
        [string]$Url,
        [int]$Seconds
    )
    $deadline = (Get-Date).AddSeconds($Seconds)
    while ((Get-Date) -lt $deadline) {
        try {
            $response = Invoke-WebRequest -UseBasicParsing -Uri $Url -TimeoutSec 2
            if ($response.StatusCode -eq 200) {
                return $true
            }
        } catch {
            # The service is still starting.
        }
        Start-Sleep -Milliseconds 500
    }
    return $false
}

function Show-LogTail {
    param([string]$Path)
    if (Test-Path $Path) {
        Get-Content $Path -Tail 12 -ErrorAction SilentlyContinue | ForEach-Object {
            Write-Host "  $_"
        }
    }
}

function Stop-StartedProcess {
    param($Process)
    if ($null -eq $Process) {
        return
    }
    try {
        if (-not $Process.HasExited) {
            & taskkill.exe /PID $Process.Id /T /F 2>$null | Out-Null
        }
    } catch {
        # Best effort cleanup only.
    }
}

if (-not (Test-Path $python)) {
    Write-Host 'The project virtual environment was not found.'
    Write-Host 'Follow README.md: py -3.12 -m venv .venv, then install requirements-dev.txt and requirements-ocr.txt.'
    exit 1
}

if (-not (Test-Path (Join-Path $frontendDir 'node_modules'))) {
    Write-Host 'Frontend dependencies are missing.'
    Write-Host 'Run: cd frontend; npm install'
    exit 1
}

$backendProcess = $null
$frontendProcess = $null
$backendStarted = $false
$frontendStarted = $false

if (Test-Backend) {
    Write-Step 'Backend is already running.'
} else {
    if (Test-Port 8000) {
        Write-Host 'Port 8000 is already used by another program. Stop it or change the backend port.'
        exit 1
    }

    Write-Step 'Starting backend...'
    $backendProcess = Start-Process `
        -FilePath $python `
        -ArgumentList @('-m', 'uvicorn', 'backend.app.main:app', '--host', '127.0.0.1', '--port', '8000') `
        -WorkingDirectory $root `
        -WindowStyle Hidden `
        -RedirectStandardOutput $backendOut `
        -RedirectStandardError $backendErr `
        -PassThru
    $backendStarted = $true

    if (-not (Wait-Http 'http://127.0.0.1:8000/api/health' 30)) {
        Write-Host 'Backend failed to start. Recent log:'
        Show-LogTail $backendErr
        Stop-StartedProcess $backendProcess
        exit 1
    }
    Write-Step 'Backend is ready.'
}

if (Test-Frontend) {
    Write-Step 'Frontend is already running.'
} else {
    if (Test-Port 5173) {
        Write-Host 'Port 5173 is already used by another program. Stop it or change the Vite port.'
        if ($backendStarted) {
            Stop-StartedProcess $backendProcess
        }
        exit 1
    }

    $npm = Get-Command npm.cmd -ErrorAction SilentlyContinue
    if ($null -eq $npm) {
        Write-Host 'npm.cmd was not found. Install Node.js 22+ and reopen this launcher.'
        if ($backendStarted) {
            Stop-StartedProcess $backendProcess
        }
        exit 1
    }

    Write-Step 'Starting frontend...'
    $frontendCommand = "`"$($npm.Source)`" run dev -- --host 127.0.0.1 --strictPort"
    $frontendProcess = Start-Process `
        -FilePath $env:ComSpec `
        -ArgumentList @('/d', '/c', $frontendCommand) `
        -WorkingDirectory $frontendDir `
        -WindowStyle Hidden `
        -RedirectStandardOutput $frontendOut `
        -RedirectStandardError $frontendErr `
        -PassThru
    $frontendStarted = $true

    if (-not (Wait-Http 'http://127.0.0.1:5173/' 30)) {
        Write-Host 'Frontend failed to start. Recent log:'
        Show-LogTail $frontendErr
        Stop-StartedProcess $frontendProcess
        if ($backendStarted) {
            Stop-StartedProcess $backendProcess
        }
        exit 1
    }
    Write-Step 'Frontend is ready.'
}

$url = 'http://127.0.0.1:5173/'
Write-Step "Ready: $url"
Write-Step "Logs: $logsDir"
Write-Step 'To stop both services, run stop-vocabulary-audio.bat.'

if (-not $NoBrowser) {
    $browserCandidates = @()
    if (${env:ProgramFiles(x86)}) {
        $browserCandidates += (Join-Path ${env:ProgramFiles(x86)} 'Microsoft\Edge\Application\msedge.exe')
        $browserCandidates += (Join-Path ${env:ProgramFiles(x86)} 'Google\Chrome\Application\chrome.exe')
    }
    if (${env:ProgramFiles}) {
        $browserCandidates += (Join-Path ${env:ProgramFiles} 'Microsoft\Edge\Application\msedge.exe')
        $browserCandidates += (Join-Path ${env:ProgramFiles} 'Google\Chrome\Application\chrome.exe')
    }
    if (${env:LOCALAPPDATA}) {
        $browserCandidates += (Join-Path ${env:LOCALAPPDATA} 'Microsoft\Edge\Application\msedge.exe')
        $browserCandidates += (Join-Path ${env:LOCALAPPDATA} 'Google\Chrome\Application\chrome.exe')
    }

    $browser = $browserCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1
    if ($browser) {
        Start-Process -FilePath $browser -ArgumentList @("--app=$url") | Out-Null
    } else {
        Start-Process $url | Out-Null
    }
}

exit 0
