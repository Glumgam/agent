#!/bin/bash
# Auto Research Agent の定期実行を設定する

AGENT_DIR="/Volumes/ESD-EHA/agent"
PYTHON="${AGENT_DIR}/venv/bin/python"
LOG_DIR="${AGENT_DIR}/logs"

mkdir -p "$LOG_DIR"

# crontab に追加（毎朝8時に実行）
CRON_JOB="0 8 * * * cd ${AGENT_DIR} && ${PYTHON} research_agent.py >> ${LOG_DIR}/research.log 2>&1"

# 既存のcronに追加（重複チェック付き）
( crontab -l 2>/dev/null | grep -v "research_agent.py"
  echo "$CRON_JOB"
) | crontab -

echo "✅ cron設定完了"
echo "実行時間: 毎朝8:00"
echo "ログ: ${LOG_DIR}/research.log"
crontab -l | grep research_agent
