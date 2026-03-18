#!/bin/bash
# stop_loop.sh — 永続自律ループの停止
#
# 使い方: bash stop_loop.sh

AGENT_DIR="$(cd "$(dirname "$0")"; pwd)"
PID_FILE="${AGENT_DIR}/logs/loop_forever.pid"

echo "🛑 ループ停止中..."

# PID ファイルで特定して停止
if [ -f "$PID_FILE" ]; then
    PID=$(cat "$PID_FILE")
    if kill -0 "$PID" 2>/dev/null; then
        # caffeinate のプロセスグループごと終了
        kill -- -$(ps -o pgid= -p "$PID" | tr -d ' ') 2>/dev/null
        kill "$PID" 2>/dev/null
        sleep 1
        kill -9 "$PID" 2>/dev/null
    fi
    rm -f "$PID_FILE"
fi

# 残存する autonomous_loop.py を全て終了
KILLED=$(pkill -c -f "autonomous_loop.py" 2>/dev/null || echo 0)

if [ "$KILLED" -gt 0 ] 2>/dev/null || [ -f "$PID_FILE" ]; then
    echo "✅ ループを停止しました"
else
    echo "✅ ループを停止しました（または起動していませんでした）"
fi
