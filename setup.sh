#!/usr/bin/env bash
# Installs Ollama, downloads the models, and builds the course assistant.
# Safe to run more than once.
set -e

if ! command -v ollama >/dev/null; then
  echo "== Installing Ollama =="
  sudo apt-get update -y && sudo apt-get install -y zstd curl
  curl -fsSL https://ollama.com/install.sh | sh
fi

# Codespaces has no systemd, so start the Ollama server ourselves
if ! curl -s http://localhost:11434 >/dev/null; then
  echo "== Starting Ollama server =="
  nohup ollama serve > /tmp/ollama.log 2>&1 &
  sleep 5
fi

echo "== Downloading models (a few minutes the first time) =="
ollama pull llama3.2:1b        # small, fast chat model
ollama pull phi4-mini          # recommended model (follows skills better)
ollama pull llama-guard3:1b    # the safety model (guardrail)

echo "== Building class-assistant from Modelfile =="
ollama create class-assistant -f Modelfile

echo "== Setup done. Now run: bash start.sh =="
