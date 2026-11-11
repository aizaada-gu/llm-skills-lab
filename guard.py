#!/usr/bin/env python3
"""Guarded chat demo.

Layer 1: Llama Guard 3 checks the QUESTION. Harmful -> blocked.
Layer 2: a system prompt makes the chosen model refuse off-topic questions.
Optional skill: a SKILL.md from ./skills is added to the instructions.
Layer 3: Llama Guard 3 checks the ANSWER. Harmful -> blocked.

Run in the browser:  python3 guard.py          (open port 8001)
Run in the terminal: python3 guard.py "your question"
"""
import glob
import json
import os
import re
import sys
import threading
import time
import uuid
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

OLLAMA = "http://localhost:11434"
GUARD_MODEL = "llama-guard3:1b"
DEFAULT_MODEL = "phi4-mini"
PORT = 8001
JOBS = {}  # job id -> result (None while the model is still working)
SKILLS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "skills")

REFUSAL = "Sorry, I can only help with Linux and cybersecurity questions for this course."
SYSTEM_PROMPT = f"""You are the teaching assistant for a Unix/Linux and cybersecurity course at Gannon University.
Only answer questions about Linux, Unix, the command line, networking, and defensive cybersecurity.
If the question is about anything else (weather, cars, sports, cooking, news, shopping, etc.),
reply with exactly this sentence and nothing else:
"{REFUSAL}"
Never give instructions for breaking into systems you don't own, writing malware, or weapons."""

CATEGORIES = {
    "S1": "Violent crimes", "S2": "Non-violent crimes", "S3": "Sex-related crimes",
    "S4": "Child sexual exploitation", "S5": "Defamation", "S6": "Specialized advice",
    "S7": "Privacy", "S8": "Intellectual property", "S9": "Indiscriminate weapons",
    "S10": "Hate", "S11": "Suicide & self-harm", "S12": "Sexual content",
    "S13": "Elections", "S14": "Code interpreter abuse",
}


def ask(model, messages):
    body = json.dumps({"model": model, "messages": messages, "stream": False,
                       "options": {"num_ctx": 8192}}).encode()  # room for skill text
    req = urllib.request.Request(OLLAMA + "/api/chat", body, {"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=600) as resp:
        return json.load(resp)["message"]["content"].strip()


def list_models():
    """Downloaded chat models (the guard model is hidden from the list)."""
    with urllib.request.urlopen(OLLAMA + "/api/tags", timeout=30) as resp:
        names = sorted(m["name"] for m in json.load(resp)["models"])
    names = [n for n in names if not n.startswith(("llama-guard", "class-assistant"))]
    if DEFAULT_MODEL in names:
        names.remove(DEFAULT_MODEL)
        names.insert(0, DEFAULT_MODEL)
    return names


def list_skills():
    """Folder names of skills/<name>/SKILL.md"""
    return sorted(os.path.basename(os.path.dirname(f))
                  for f in glob.glob(os.path.join(SKILLS_DIR, "*", "SKILL.md")))


def load_skill(name):
    """SKILL.md text without the YAML header (keeps name + description)."""
    if not name or name not in list_skills():
        return ""
    text = open(os.path.join(SKILLS_DIR, name, "SKILL.md")).read()
    desc = re.search(r"^description:\s*'?(.*?)'?\s*\n(?=\w+:)", text, re.S | re.M)
    body = re.sub(r"^---.*?\n---\s*\n", "", text, count=1, flags=re.S)
    header = f"Skill: {name}\n" + (" ".join(desc.group(1).split()) + "\n" if desc else "")
    return header + body


def guard_check(messages):
    """Returns a list of violated categories ([] means safe)."""
    lines = ask(GUARD_MODEL, messages).splitlines()
    if not lines or not lines[0].strip().lower().startswith("unsafe"):
        return []
    codes = lines[1].replace(" ", "").split(",") if len(lines) > 1 else ["?"]
    return [f"{c} {CATEGORIES.get(c, '')}".strip() for c in codes]


def guarded_answer(question, model=DEFAULT_MODEL, skill=""):
    start = time.time()
    result = _guarded(question, model, skill)
    result["model"] = model
    result["skill"] = skill or "none"
    result["seconds"] = round(time.time() - start, 1)
    return result


def _guarded(question, model, skill=""):
    user = {"role": "user", "content": question}

    bad = guard_check([user])
    if bad:
        return {"status": "BLOCKED", "layer": "Llama Guard (question)", "categories": bad,
                "answer": "This question was blocked by the safety guardrail."}

    system = SYSTEM_PROMPT
    skill_text = load_skill(skill)
    if skill_text:
        system += ("\n\nFollow this expert skill when it is relevant to the question:\n\n" + skill_text)
    answer = ask(model, [{"role": "system", "content": system}, user])

    bad = guard_check([user, {"role": "assistant", "content": answer}])
    if bad:
        return {"status": "BLOCKED", "layer": "Llama Guard (answer)", "categories": bad,
                "answer": "The answer was blocked by the safety guardrail."}

    refused = "only help with Linux and cybersecurity" in answer
    return {"status": "OFF-TOPIC" if refused else "ANSWERED",
            "layer": "System prompt (topic)" if refused else "-",
            "categories": [], "answer": answer}


PAGE = """<!doctype html><html><head><meta charset="utf-8"><title>Guarded LLM demo</title>
<style>
body{font-family:system-ui,sans-serif;max-width:720px;margin:40px auto;padding:0 16px}
select{font-size:16px;margin-bottom:8px}textarea{width:100%;height:80px;font-size:16px}button{font-size:16px;padding:8px 16px;margin-top:8px}
.card{border:1px solid #ccc;border-radius:8px;padding:12px;margin-top:16px;white-space:pre-wrap}
.ANSWERED{border-left:6px solid #2e7d32}.OFF-TOPIC{border-left:6px solid #f9a825}.BLOCKED{border-left:6px solid #c62828}
</style></head><body>
<h2>Guarded LLM demo</h2>
<p>Llama Guard checks the question and the answer. The chosen model only answers Linux and cybersecurity questions.</p>
<label>Model: <select id="m"></select></label>
<label style="margin-left:12px">Skill: <select id="s"><option value="">none</option></select></label>
<textarea id="q" placeholder="Ask something..."></textarea><br>
<button onclick="go()">Ask</button><div id="out"></div>
<script>
fetch('skills').then(r=>r.json()).then(ss=>{
  const sel=document.getElementById('s');
  ss.forEach(n=>{const o=document.createElement('option');o.value=n;o.textContent=n;sel.appendChild(o);});
});
fetch('models').then(r=>r.json()).then(ms=>{
  const sel=document.getElementById('m');
  ms.forEach(n=>{const o=document.createElement('option');o.textContent=n;sel.appendChild(o);});
});
async function go(){
  const q=document.getElementById('q').value; if(!q) return;
  const m=document.getElementById('m').value;
  const sk=document.getElementById('s').value;
  const out=document.getElementById('out');
  const wait=document.createElement('div'); wait.className='card'; out.prepend(wait);
  const t0=Date.now();
  const tick=setInterval(()=>{wait.textContent='Thinking... '+Math.round((Date.now()-t0)/1000)+'s ('+m+', skill: '+(sk||'none')+')';},1000);
  let r;
  try {
    const job=await (await fetch('ask',{method:'POST',body:JSON.stringify({question:q,model:m,skill:sk})})).json();
    while(true){
      await new Promise(ok=>setTimeout(ok,2000));
      const res=await fetch('result?id='+job.id);
      if(res.status===200){ r=await res.json(); break; }
    }
  } catch(e) { r={status:'ERROR',layer:'-',categories:[],answer:String(e),model:m,skill:sk||'none',seconds:0}; }
  clearInterval(tick); wait.remove();
  const div=document.createElement('div'); div.className='card '+r.status;
  div.textContent='Model: '+r.model+'   Skill: '+r.skill+'   ('+r.seconds+' seconds)\\nQ: '+q+'\\n\\n['+r.status+']  Guardrail: '+r.layer+
    (r.categories.length?'  ('+r.categories.join(', ')+')':'')+'\\n\\n'+r.answer;
  out.prepend(div);
}
</script></body></html>"""


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path.startswith("/skills"):
            self._send(200, "application/json", json.dumps(list_skills()).encode())
        elif self.path.startswith("/result"):
            job = self.path.split("id=")[-1]
            if job not in JOBS:
                self._send(404, "application/json", b'{"error": "unknown job"}')
            elif JOBS[job] is None:
                self._send(202, "application/json", b'{"status": "working"}')
            else:
                self._send(200, "application/json", json.dumps(JOBS.pop(job)).encode())
        elif self.path.startswith("/models"):
            self._send(200, "application/json", json.dumps(list_models()).encode())
        else:
            self._send(200, "text/html", PAGE.encode())

    def do_POST(self):
        """Start the job in the background and return its id right away,
        so slow answers don't hit the port-forwarding timeout."""
        data = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        job = uuid.uuid4().hex
        JOBS[job] = None
        threading.Thread(target=self.work, args=(job, data), daemon=True).start()
        self._send(200, "application/json", json.dumps({"id": job}).encode())

    @staticmethod
    def work(job, data):
        try:
            result = guarded_answer(data["question"], data.get("model") or DEFAULT_MODEL,
                                    data.get("skill") or "")
        except Exception as e:  # e.g. Ollama not running
            result = {"status": "ERROR", "layer": "-", "categories": [], "answer": str(e),
                      "model": data.get("model"), "skill": data.get("skill") or "none", "seconds": 0}
        print(f"[{result['status']}] {result['model']} + skill {result['skill']} "
              f"({result['seconds']}s): {data['question']}", flush=True)
        JOBS[job] = result

    def _send(self, code, ctype, body):
        try:
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.end_headers()
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass  # browser closed the connection; nothing to do

    def log_message(self, *args):
        pass


if __name__ == "__main__":
    if len(sys.argv) > 1:
        # python3 guard.py "question"   or   MODEL=phi4-mini python3 guard.py "question"
        # SKILL=hardening-linux-endpoint-with-cis-benchmark python3 guard.py "question"
        print(json.dumps(guarded_answer(" ".join(sys.argv[1:]), os.environ.get("MODEL", DEFAULT_MODEL),
                                        os.environ.get("SKILL", "")), indent=2))
    else:
        print(f"Open port {PORT} (Ports tab in Codespaces). Ctrl+C to stop.")
        ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
