#!/usr/bin/env python3
"""Compare small LLMs on this Codespace: speed, size, and answers.

Usage:
  python3 compare.py                      # tests the default list below
  python3 compare.py gemma3:4b llama3.1:8b  # tests the models you name

Writes results.md (table + every answer) so you can read and grade them.
"""
import json
import subprocess
import sys
import time
import urllib.request

OLLAMA = "http://localhost:11434"

MODELS = ["llama3.2:1b", "gemma3:1b", "qwen2.5:1.5b", "llama3.2:3b", "phi4-mini", "gemma3:4b"]

# Questions with a known correct answer, so you can grade each model
QUESTIONS = [
    ("How do I list hidden files in Linux? Answer in 2 sentences.", "ls -a (current folder only)"),
    ("What does chmod 755 do to a file? Answer in 2 sentences.", "owner rwx, group and others r-x"),
    ("What port does SSH use by default? Answer in 1 sentence.", "22"),
]


def api(path, payload=None):
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(OLLAMA + path, data, {"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=900) as r:
        return json.load(r)


def size_gb(model):
    for m in api("/api/tags")["models"]:
        if m["name"] == model or m["name"] == model + ":latest":
            return m["size"] / 1e9
    return 0


def main():
    models = sys.argv[1:] or MODELS
    rows, answers = [], []
    for model in models:
        print(f"\n=== {model} ===", flush=True)
        if subprocess.run(["ollama", "pull", model]).returncode != 0:
            print(f"Could not download {model}, skipping")
            rows.append(f"| {model} | download failed | | | |")
            continue
        load = 0
        speeds, totals = [], []
        for i, (q, correct) in enumerate(QUESTIONS):
            r = api("/api/generate", {"model": model, "prompt": q, "stream": False,
                                      "options": {"num_predict": 200, "temperature": 0}})
            if i == 0:
                load = r.get("load_duration", 0) / 1e9
            tok_s = r["eval_count"] / (r["eval_duration"] / 1e9)
            speeds.append(tok_s)
            totals.append(r["total_duration"] / 1e9)
            answers.append(f"### {model}\n**Q:** {q}\n**Correct:** {correct}\n\n{r['response'].strip()}\n")
            print(f"  Q{i+1}: {tok_s:.1f} tokens/sec, {totals[-1]:.1f}s", flush=True)
        rows.append(f"| {model} | {size_gb(model):.1f} GB | {load:.1f}s "
                    f"| {sum(speeds)/len(speeds):.1f} | {sum(totals)/len(totals):.1f}s |")

    table = ("| Model | Size | First load | Tokens/sec | Avg answer time |\n"
             "|---|---|---|---|---|\n" + "\n".join(rows))
    with open("results.md", "w") as f:
        f.write("# Model comparison (CPU only)\n\n" + table +
                "\n\nAccuracy: read the answers below and grade each one.\n\n## Answers\n\n" +
                "\n".join(answers))
    print("\n" + table + "\n\nSaved to results.md")


if __name__ == "__main__":
    main()
