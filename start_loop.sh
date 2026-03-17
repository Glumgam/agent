#!/bin/bash
# スリープを防止しながら自律ループを起動する
AGENT_DIR="/Volumes/ESD-EHA/agent"
PYTHON="${AGENT_DIR}/venv/bin/python"
LOG_DIR="${AGENT_DIR}/logs"

mkdir -p "$LOG_DIR"

echo "🚀 自律ループ起動"
echo "   終了: Ctrl+C"
echo "   ログ: ${LOG_DIR}/autonomous_loop.log"
echo "   状態: ${LOG_DIR}/loop_status.json"
echo ""

# caffeinate: macOS がスリープしないようにする
# -i: システムスリープを防止
# -d: ディスプレイスリープを防止
caffeinate -i -d bash -c "
  cd '${AGENT_DIR}'
  '${PYTHON}' autonomous_loop.py --hours 18 --interval 30
"
