#!/usr/bin/env python3
"""Local browser for avatar experiment output. usage: serve.py [port]   (binds 127.0.0.1 only)"""
import http.server, json, os, re, sys, unicodedata, urllib.parse
ROOT = os.path.dirname(os.path.abspath(__file__)); OUT = os.path.join(ROOT, "out")
PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8765
EXP = {"e1": "Exp 1 · models × strict prompt", "e2": "Exp 2 · golden reference × roles", "e3": "Exp 3 · recolor, grid, species, mood"}

def scan():
    files = sorted(os.listdir(OUT)); d = {"experiments": [], "agents": [], "golden": [], "compare": [], "spent": None, "calls": []}
    for k, title in EXP.items():
        items = []
        for f in files:
            m = re.match(rf"{k}_(.+)_(raw|post)\.png$", f)
            if m: items.append({"name": m.group(1), "kind": m.group(2), "src": "out/" + f})
        by = {}
        for i in items: by.setdefault(i["name"], {})[i["kind"]] = i["src"]
        d["experiments"].append({"id": k, "title": title, "items": [{"name": n, **v} for n, v in by.items()]})
    ad = os.path.join(OUT, "agents")
    if os.path.isdir(ad):
        for f in sorted(os.listdir(ad)):
            if f.endswith(".png") and not f.endswith("@8x.png"):
                n = f[:-4]; meta = {}
                try: meta = json.load(open(os.path.join(ad, n + ".json")))
                except Exception: pass
                d["agents"].append({"name": n, "src": f"out/agents/{n}@8x.png", "meta": meta})
    cd, td, hd = os.path.join(OUT, "compare"), os.path.join(OUT, "theirs"), os.path.join(OUT, "hybrid")
    if os.path.isdir(cd):
        theirs = {}
        if os.path.isdir(td):
            for f in os.listdir(td):
                b, e = os.path.splitext(f)
                if e.lower() in (".png", ".svg", ".webp"): theirs[unicodedata.normalize("NFC", b)] = "out/theirs/" + f
        for f in sorted(os.listdir(cd)):
            if f.endswith(".png") and not f.endswith("@8x.png"):
                n = unicodedata.normalize("NFC", f[:-4]); meta = {}
                try: meta = json.load(open(os.path.join(cd, f[:-4] + ".json")))
                except Exception: pass
                d["compare"].append({"name": n, "mine": f"out/compare/{f[:-4]}@8x.png", "theirs": theirs.get(n), "hybrid": (f"out/hybrid/{f[:-4]}@8x.png" if os.path.exists(os.path.join(hd, f[:-4] + "@8x.png")) else None), "hybrid2": (f"out/h2-sprite/{f[:-4]}@8x.png" if os.path.exists(os.path.join(OUT, "h2-sprite", f[:-4] + "@8x.png")) else None), "meta": meta})
    gd = os.path.join(ROOT, "golden")
    if os.path.isdir(gd): d["golden"] = [{"name": f, "src": "golden/" + f} for f in sorted(os.listdir(gd)) if f.endswith(".png")]
    try:
        L = json.load(open(os.path.join(ROOT, "ledger.json"))); d["spent"] = L["total"]; d["calls"] = L["calls"]
    except Exception: pass
    return d

class H(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **k): super().__init__(*a, directory=ROOT, **k)
    def do_GET(self):
        p = urllib.parse.urlparse(self.path).path
        if p == "/api/data":
            b = json.dumps(scan()).encode(); self.send_response(200)
            self.send_header("Content-Type", "application/json"); self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b); return
        if p == "/": self.path = "/viewer.html"
        elif p not in ("/viewer.html",) and not p.startswith(("/out/", "/golden/")): self.send_error(404); return
        return super().do_GET()
    def log_message(self, *a): pass

if __name__ == "__main__":
    http.server.ThreadingHTTPServer(("127.0.0.1", PORT), H).serve_forever()
