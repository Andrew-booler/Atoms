#Requires -Version 5.1
<#
.SYNOPSIS
    Atoms 沙箱容器外部回收器：清理超过指定时长仍存活的 atoms 沙箱容器。

.DESCRIPTION
    仅处理带 label "atoms.sandbox=1" 的容器，兼容旧版本以 "atoms-sandbox-" 开头的容器名
    （名称过滤使用锚定正则 ^atoms-sandbox-，不会匹配到 docker-* 或其他项目容器）。
    超过 -MaxAgeMinutes 的容器执行 docker rm -f，较新的容器一律保留。
    不触碰 volume、network、image，也不触碰任何非本项目容器。

.NOTES
    由 Windows 计划任务 AtomsSandboxReaper 每 10 分钟触发一次。
#>
param(
    [int]$MaxAgeMinutes = 30
)

$ErrorActionPreference = "Stop"
$logFile = Join-Path $env:TEMP "atoms-sandbox-reaper.log"

function Write-Log {
    param([string]$Message)
    $line = "{0} {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $Message
    Add-Content -Path $logFile -Value $line -Encoding UTF8
    Write-Output $line
}

# 日志截断：超过 256 KB 时只保留最近 200 行
if (Test-Path $logFile) {
    if ((Get-Item $logFile).Length -gt 256KB) {
        Get-Content $logFile -Tail 200 | Set-Content -Path $logFile -Encoding UTF8
    }
}

try {
    $docker = (Get-Command docker -ErrorAction SilentlyContinue).Source
    if (-not $docker) {
        $docker = "C:\Users\liwu1\AppData\Local\Programs\DockerDesktop\resources\bin\docker.exe"
    }
    if (-not (Test-Path $docker)) {
        Write-Log "ERROR: docker CLI not found"
        exit 1
    }

    $ids = @()
    $ids += & $docker ps -aq --filter "label=atoms.sandbox=1"
    $ids += & $docker ps -aq --filter "name=^atoms-sandbox-"
    $ids = @($ids | Where-Object { $_ } | Sort-Object -Unique)

    if ($ids.Count -eq 0) {
        Write-Log "DONE: no atoms sandbox container"
        exit 0
    }

    $now = (Get-Date).ToUniversalTime()
    $removed = 0
    $kept = 0
    foreach ($id in $ids) {
        $raw = & $docker inspect $id 2>$null
        if ($LASTEXITCODE -ne 0 -or -not $raw) {
            Write-Log "SKIP: $id (inspect failed)"
            continue
        }
        $info = $raw | ConvertFrom-Json
        $created = ([datetimeoffset]::Parse($info.Created)).UtcDateTime
        $ageMinutes = [math]::Round(($now - $created).TotalMinutes, 1)
        if ($ageMinutes -lt $MaxAgeMinutes) {
            $kept++
            continue
        }
        & $docker rm -f $id | Out-Null
        if ($LASTEXITCODE -eq 0) {
            $removed++
            Write-Log "REMOVED: $($info.Name) age=${ageMinutes}m id=$id"
        } else {
            Write-Log "FAILED: $($info.Name) age=${ageMinutes}m id=$id"
        }
    }
    Write-Log "DONE: removed=$removed kept=$kept threshold=${MaxAgeMinutes}m"
} catch {
    Write-Log "ERROR: $($_.Exception.Message)"
    exit 1
}
