import json, os, sys, base64, re, urllib.request, urllib.error, contextlib, fcntl
from PIL import Image
import io
HERE = os.path.dirname(os.path.abspath(__file__))
LAST_COST = 0.0   # cost of the most recent generate() call (also set on a billed failure)

PICO8 = ["#000000","#1D2B53","#7E2553","#008751","#AB5236","#5F574F","#C2C3C7","#FFF1E8",
         "#FF004D","#FFA300","#FFEC27","#00E436","#29ADFF","#83769C","#FF77A8","#FFCCAA"]

# ---- configuration: env overrides, defaults unchanged. Evaluated at call time, never at import. ----
def ledger_path(): return os.environ.get("AVATAR_LEDGER") or os.path.join(HERE, "ledger.json")
def key_file():    return os.path.expanduser(os.environ.get("AVATAR_KEY_FILE") or "~/.config/avatars/avatar-openrouter")
def spend_cap():
    try: return float(os.environ.get("AVATAR_SPEND_CAP") or 9.50)   # hard stop below the $10 authorization
    except ValueError: raise AvatarError("model_error", "AVATAR_SPEND_CAP is not a number")

class AvatarError(Exception):
    """code is the machine-readable class; exit is the process exit status for it."""
    EXIT = {"over_budget": 10, "credential_missing": 11, "scope_missing": 12, "no_image": 13,
            "model_error": 14, "ledger_corrupt": 15, "registry_corrupt": 16, "internal_error": 70}
    def __init__(self, code, message, cost=0.0):
        super().__init__(message); self.code, self.message, self.cost = code, message, cost
        self.exit = self.EXIT.get(code, 14)

@contextlib.contextmanager
def locked(path):
    """Advisory exclusive lock on <path>.lock (flock). Other writers (e.g. the Go server) must flock the same file."""
    fd = os.open(path + ".lock", os.O_CREAT | os.O_RDWR, 0o644)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX); yield
    finally:
        try: fcntl.flock(fd, fcntl.LOCK_UN)
        finally: os.close(fd)

def _key():
    """Read the key only when a call is about to be made. Never printed or put in an error message."""
    p = key_file()
    try: k = open(p).read().strip()
    except OSError: raise AvatarError("credential_missing", f"key file not readable: {p}")
    if not k: raise AvatarError("credential_missing", f"key file is empty: {p}")
    return k

def _read_ledger():
    p = ledger_path()
    if not os.path.exists(p): return {"total": 0.0, "calls": []}
    try:
        d = json.load(open(p))
        if not isinstance(d, dict) or not isinstance(d.get("total"), (int, float)) or not isinstance(d.get("calls"), list): raise ValueError("bad shape")
        return d
    except Exception as e:
        raise AvatarError("ledger_corrupt", f"spend ledger unreadable ({p}): {e}")

def spent(): return _read_ledger()["total"]

def _log(model, cost, label):
    p = ledger_path()
    with locked(p):
        d = _read_ledger()
        d["total"] = round(d["total"] + cost, 6)
        d["calls"].append({"model": model, "cost": cost, "label": label})
        tmp = p + ".tmp"; json.dump(d, open(tmp, "w"), indent=1); os.replace(tmp, p)

def generate(prompt, model="google/gemini-3.1-flash-image", refs=(), label=""):
    """Returns PIL image. refs = list of PNG paths sent as style references. Raises AvatarError (cost set when billed)."""
    global LAST_COST; LAST_COST = 0.0
    if spent() >= spend_cap(): raise AvatarError("over_budget", f"budget cap reached: ${spent():.2f}")
    key = _key()
    content = [{"type": "text", "text": prompt}]
    for p in refs:
        b = base64.b64encode(open(p, "rb").read()).decode()
        content.append({"type": "image_url", "image_url": {"url": "data:image/png;base64," + b}})
    body = {"model": model, "modalities": ["image", "text"], "messages": [{"role": "user", "content": content}]}
    req = urllib.request.Request("https://openrouter.ai/api/v1/chat/completions", json.dumps(body).encode(),
        {"Authorization": "Bearer " + key, "Content-Type": "application/json"})
    try:
        r = json.load(urllib.request.urlopen(req, timeout=180))
    except urllib.error.HTTPError as e:
        code = {401: "credential_missing", 402: "over_budget", 403: "scope_missing"}.get(e.code, "model_error")
        raise AvatarError(code, f"HTTP {e.code}: {e.read()[:300].decode(errors='replace')}")
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as e:
        raise AvatarError("model_error", f"request failed: {type(e).__name__}: {e}")
    cost = (r.get("usage") or {}).get("cost", 0.0) or 0.0
    _log(model, cost, label); LAST_COST = cost
    try: imgs = r["choices"][0]["message"].get("images") or []
    except (KeyError, IndexError, TypeError): imgs = []
    if not imgs: raise AvatarError("no_image", "no image returned", cost)
    m = re.match(r"data:image/\w+;base64,(.*)", imgs[0]["image_url"]["url"], re.S)
    if not m: raise AvatarError("no_image", "no image returned (unrecognised image payload)", cost)
    return Image.open(io.BytesIO(base64.b64decode(m.group(1)))).convert("RGB")

def hex2rgb(h): h = h.lstrip("#"); return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))

def pixelate(img, size=64, palette=None, method="mode"):
    """Downscale to size x size on a hard grid; optionally snap to palette (hex list).
    mode = most common colour per block (crisp edges); nearest = centre sample."""
    from collections import Counter
    w, h = img.size
    if palette:  # snap at full res first so block-mode votes on palette colours
        pal = [hex2rgb(c) for c in palette]
        cache = {}
        def snap(c):
            if c not in cache: cache[c] = min(pal, key=lambda p: (p[0]-c[0])**2+(p[1]-c[1])**2+(p[2]-c[2])**2)
            return cache[c]
        src = img.resize((size*4, size*4), Image.BOX)  # modest res keeps this fast
        px = src.load()
        for y in range(src.height):
            for x in range(src.width): px[x, y] = snap(px[x, y])
        img = src
        w, h = img.size
    if method == "nearest":
        return img.resize((size, size), Image.NEAREST)
    small = Image.new("RGB", (size, size)); out = small.load(); px = img.load()
    bw, bh = w / size, h / size
    for y in range(size):
        for x in range(size):
            cnt = Counter(px[xx, yy] for yy in range(int(y*bh), max(int((y+1)*bh), int(y*bh)+1))
                                     for xx in range(int(x*bw), max(int((x+1)*bw), int(x*bw)+1)))
            out[x, y] = cnt.most_common(1)[0][0]
    return small

def upscale(img, factor=8): return img.resize((img.width*factor, img.height*factor), Image.NEAREST)

def ncolors(img): return len(img.getcolors(1 << 20))



def _luma(c): return 0.3*c[0] + 0.59*c[1] + 0.11*c[2]

def despeckle(img, maxdist=110, minagree=6, max_component=2, ring_share=0.6, protect=(45, 225), passes=3):
    """Two rules, repeated up to `passes` times:
      1. near-shade: an isolated pixel whose colour is a near shade (RGB dist < maxdist) of the colour that
         minagree+ of its 8 neighbours agree on takes that colour.
      2. tiny component: a 4-connected same-colour component of <= max_component pixels, whose luma is inside
         `protect` (so outline darks and highlight whites survive), takes the majority colour of its surrounding
         ring if that colour holds >= ring_share of the ring. Catches stray accent-coloured specks rule 1 misses."""
    from collections import Counter
    w, h = img.size; out = img.copy(); o = out.load()
    for _ in range(passes):
        px = out.copy().load(); changed = 0
        for y in range(h):
            for x in range(w):
                c = px[x, y]
                nb = [px[xx, yy] for yy in range(max(0, y-1), min(h, y+2)) for xx in range(max(0, x-1), min(w, x+2)) if (xx, yy) != (x, y)]
                if sum(1 for q in nb if q == c) > 1: continue
                top, cnt = Counter(nb).most_common(1)[0]
                if cnt >= minagree and top != c and sum((a-b)**2 for a, b in zip(c, top)) ** 0.5 < maxdist:
                    o[x, y] = top; changed += 1
        px = out.copy().load(); seen = set()
        for y in range(h):
            for x in range(w):
                if (x, y) in seen: continue
                c = px[x, y]; comp = [(x, y)]; seen.add((x, y)); i = 0
                while i < len(comp):                      # full 4-connected flood fill of this colour
                    cx, cy = comp[i]; i += 1
                    for nx, ny in ((cx+1, cy), (cx-1, cy), (cx, cy+1), (cx, cy-1)):
                        if 0 <= nx < w and 0 <= ny < h and (nx, ny) not in seen and px[nx, ny] == c:
                            seen.add((nx, ny)); comp.append((nx, ny))
                if len(comp) > max_component or not (protect[0] <= _luma(c) <= protect[1]): continue
                cs = set(comp)
                ring = {(xx, yy) for (cx, cy) in comp for yy in range(max(0, cy-1), min(h, cy+2))
                        for xx in range(max(0, cx-1), min(w, cx+2)) if (xx, yy) not in cs}
                if not ring: continue
                top, cnt = Counter(px[p] for p in ring).most_common(1)[0]
                if top != c and cnt / len(ring) >= ring_share:
                    for (cx, cy) in comp: o[cx, cy] = top
                    changed += len(comp)
        if not changed: break
    return out
