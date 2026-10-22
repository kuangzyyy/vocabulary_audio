$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot

function Get-ListeningProcessIds {
    param([int]$Port)
    try {
        return @(
            Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction Stop |
                Select-Object -ExpandProperty OwningProcess -Unique
        )
    } catch {
        return @()
    }
}

function Get-ProcessCommandLine {
    param([int]$ProcessId)
    try {
        $process = Get-CimInstance Win32_Process -Filter "ProcessId=$ProcessId" -ErrorAction Stop
        return [string]$process.CommandLine
    } catch {
        return ''
    }
}

function Stop-ProjectProcess {
    param(
        [int]$ProcessId,
        [string]$Label
    )
    try {
        & taskkill.exe /PID $ProcessId /T /F 2>$null | Out-Null
        if ($LASTEXITCODE -eq 0) {
            Write-Host "[Vocabulary Audio] Stopped $Label (PID $ProcessId)."
        } else {
            Write-Host "[Vocabulary Audio] Could not stop $Label (PID $ProcessId)."
        }
    } catch {
        Write-Host "[Vocabulary Audio] Could not stop $Label (PID $ProcessId)."
    }
}

$stopped = 0
$unrecognized = @()

foreach ($port in @(8000, 5173)) {
    $pids = Get-ListeningProcessIds $port
    if ($pids.Count -eq 0) {
        Write-Host "[Vocabulary Audio] Port $port is not listening."
        continue
    }

    foreach ($processId in $pids) {
        $commandLine = Get-ProcessCommandLine $processId
        if ($port -eq 8000 -and $commandLine -match 'uvicorn' -and $commandLine -match 'backend\.app\.main:app') {
            Stop-ProjectProcess $processId 'backend'
            $stopped += 1
        } elseif ($port -eq 5173 -and $commandLine -match 'vite') {
            Stop-ProjectProcess $processId 'frontend'
            $stopped += 1
        } else {
            $unrecognized += "Port $port PID $processId"
        }
    }
}

if ($unrecognized.Count -gt 0) {
    Write-Host '[Vocabulary Audio] These ports are used by other programs and were left running:'
    $unrecognized | ForEach-Object { Write-Host "  $_" }
}

if ($stopped -eq 0) {
    Write-Host '[Vocabulary Audio] No project services were stopped.'
}
