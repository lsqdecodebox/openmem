#
# OpenMem NAS 同步脚本 (Windows)
#
# 同步 users.json + wiki_root 至 NAS，由 Windows 任务计划程序调用，不进 openmem 主进程。
#
# 用法:
#   .\sync_to_nas.ps1                          # 使用脚本内默认配置
#   $env:OPENMEM_NAS_TARGET="\\nas\backup\openmem"; .\sync_to_nas.ps1
#
# 任务计划程序示例 (每天凌晨 2 点同步):
#   程序: powershell.exe
#   参数: -ExecutionPolicy Bypass -File "C:\path\to\openmem\scripts\sync_to_nas.ps1"
#
# 配置: 编辑下方变量或通过环境变量覆盖

$ErrorActionPreference = "Stop"

# ===== 配置区（按实际环境修改）=====
$UsersFile = if ($env:OPENMEM_USERS_FILE) { $env:OPENMEM_USERS_FILE } else { "$env:USERPROFILE\.config\openmem\users.json" }
$WikiRoot  = if ($env:OPENMEM_WIKI_ROOT)  { $env:OPENMEM_WIKI_ROOT }  else { "$env:USERPROFILE\.openmem\wiki" }
$NasTarget = if ($env:OPENMEM_NAS_TARGET) { $env:OPENMEM_NAS_TARGET } else { "\\nas\backup\openmem" }
# ==================================

$timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
Write-Host "[$timestamp] 开始同步至 NAS: $NasTarget"

if (-not (Test-Path $UsersFile)) {
    Write-Error "users.json 不存在: $UsersFile"
    exit 1
}
if (-not (Test-Path $WikiRoot)) {
    Write-Error "wiki_root 不存在: $WikiRoot"
    exit 1
}

# 同步 users.json
robocopy (Split-Path $UsersFile -Parent) $NasTarget (Split-Path $UsersFile -Leaf) /R:3 /W:5 /NP
Write-Host "[OK] users.json 已同步"

# 同步 wiki（排除 .snapshots 快照目录）
robocopy $WikiRoot "$NasTarget\wiki" /MIR /XD ".snapshots" /R:3 /W:5 /NP
Write-Host "[OK] wiki 已同步"

$timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
Write-Host "[$timestamp] 同步完成"
