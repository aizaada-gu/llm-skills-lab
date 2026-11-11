#!/usr/bin/env bash
# Starts everything. Students only need: bash start.sh
cd "$(dirname "$0")"

if ! command -v ollama >/dev/null || ! ollama list 2>/dev/null | grep -q class-assistant; then
  bash setup.sh
fi

if ! curl -s http://localhost:11434 >/dev/null; then
  nohup ollama serve > /tmp/ollama.log 2>&1 &
  sleep 5
fi

python3 guard.py
