#!/bin/bash
# loop_forever.sh — 24/365 永続自律ループ
#
# 使い方:
#   bash loop_forever.sh      # 起動
#   bash stop_loop.sh         # 停止
#
# 特徴:
#   - ターミナルを閉じても停止しない（nohup + disown）
#   - クラッシュ時は自動で再起動
#   - caffeinate で Mac スリープを防止
#   - 二重起動を防止（PID ファイル管理）

AGENT_DIR="$(cd "$(dirname "$0")"; pwd)"
PYTHON="${AGENT_DIR}/venv/bin/python"
LOG_DIR="${AGENT_DIR}/logs"
PID_FILE="${LOG_DIR}/loop_forever.pid"
RESTART_LOG="${LOG_DIR}/loop_restarts.log"

mkdir -p "$LOG_DIR"

# ── 二重起動チェック ──────────────────────────────────────────
if [ -f "$PID_FILE" ]; then
    OLD_PID=$(cat "$PID_FILE")
    if kill -0 "$OLD_PID" 2>/dev/null; then
        echo "⚠️  すでに起動中 (PID: $OLD_PID)"
        echo "   停止するには: bash stop_loop.sh"
        exit 1
    fi
    rm -f "$PID_FILE"
fi

# ── バックグラウンドで永続実行 ────────────────────────────────
# nohup + disown でターミナルを閉じても継続
# caffeinate で Mac がスリープしないようにする
nohup caffeinate -i bash -c "
    AGENT_DIR='${AGENT_DIR}'
    PYTHON='${PYTHON}'
    RESTART_LOG='${RESTART_LOG}'
    SESSION=0

    while true; do
        SESSION=\$((SESSION + 1))
        TS=\$(date '+%Y-%m-%d %H:%M:%S')
        echo \"[\${TS}] ===== セッション \${SESSION} 開始 =====\" | tee -a \"\${RESTART_LOG}\"

        cd \"\${AGENT_DIR}\"
        \"\${PYTHON}\" autonomous_loop.py --forever --interval 0
        EXIT=\$?

        TS=\$(date '+%Y-%m-%d %H:%M:%S')
        if [ \$EXIT -eq 0 ]; then
            echo \"[\${TS}] 正常終了 (exit=0) → 即再起動\" | tee -a \"\${RESTART_LOG}\"
        else
            echo \"[\${TS}] 異常終了 (exit=\${EXIT}) → 5秒後に再起動\" | tee -a \"\${RESTART_LOG}\"
            sleep 5
        fi
    done
" >> "${LOG_DIR}/loop_nohup.log" 2>&1 &

LOOP_PID=$!
echo $LOOP_PID > "$PID_FILE"
disown $LOOP_PID

echo "✅ 永続ループ起動完了"
echo "   PID:        $LOOP_PID"
echo "   メインログ: ${LOG_DIR}/autonomous_loop.log"
echo "   再起動ログ: ${RESTART_LOG}"
echo "   状態確認:   cat ${LOG_DIR}/loop_status.json"
echo "   停止:       bash stop_loop.sh"
