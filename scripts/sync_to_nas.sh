#!/usr/bin/env bash
#
# OpenMem NAS 同步脚本 (Linux/macOS)
#
# 同步 users.json + wiki_root 至 NAS，由 OS 定时任务（cron）调用，不进 openmem 主进程。
#
# 用法:
#   ./sync_to_nas.sh                          # 使用脚本内默认配置
#   OPENMEM_NAS_TARGET=rsync://user@nas:/backup/openmem/ ./sync_to_nas.sh
#
# cron 示例 (每天凌晨 2 点同步):
#   0 2 * * * /path/to/openmem/scripts/sync_to_nas.sh >> /var/log/openmem_sync.log 2>&1
#
# 配置: 编辑下方变量或通过环境变量覆盖

set -euo pipefail

# ===== 配置区（按实际环境修改）=====
USERS_FILE="${OPENMEM_USERS_FILE:-$HOME/.config/openmem/users.json}"
WIKI_ROOT="${OPENMEM_WIKI_ROOT:-$HOME/.openmem/wiki}"
NAS_TARGET="${OPENMEM_NAS_TARGET:-rsync://backup@nas.local:/backup/openmem/}"
# ==================================

echo "[$(date '+%Y-%m-%d %H:%M:%S')] 开始同步至 NAS: ${NAS_TARGET}"

if [ ! -f "$USERS_FILE" ]; then
    echo "[ERROR] users.json 不存在: $USERS_FILE" >&2
    exit 1
fi

if [ ! -d "$WIKI_ROOT" ]; then
    echo "[ERROR] wiki_root 不存在: $WIKI_ROOT" >&2
    exit 1
fi

# 同步 users.json
rsync -avz "$USERS_FILE" "${NAS_TARGET}users.json"
echo "[OK] users.json 已同步"

# 同步 wiki（排除 .snapshots 快照目录）
rsync -avz --delete --exclude='.snapshots' "$WIKI_ROOT/" "${NAS_TARGET}wiki/"
echo "[OK] wiki 已同步"

echo "[$(date '+%Y-%m-%d %H:%M:%S')] 同步完成"
