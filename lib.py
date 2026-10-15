import json, os, sys, base64, re, urllib.request, urllib.error
from PIL import Image
import io
HERE = os.path.dirname(os.path.abspath(__file__))
LEDGER = os.path.join(HERE, "ledger.json")
CAP = 9.50  # hard stop below the $10 authorization

PICO8 = ["#000000","#1D2B53","#7E2553","#008751","#AB5236","#5F574F","#C2C3C7","#FFF1E8",
         "#FF004D","#FFA300","#FFEC27","#00E436","#29ADFF","#83769C","#FF77A8","#FFCCAA"]

def _key():
    return open(os.path.expanduser("~/.config/avatars/avatar-openrouter")).read().strip()

def spent():
    try: return json.load(open(LEDGER))["total"]
    except Exception: return 0.0

def _log(model, cost, label):
    d = {"total": 0.0, "calls": []}
    if os.path.exists(LEDGER): d = json.load(open(LEDGER))
    d["total"] = round(d["total"] + cost, 6)
    d["calls"].append({"model": model, "cost": cost, "label": label})
    json.dump(d, open(LEDGER, "w"), indent=1)

def generate(prompt, model="google/gemini-3.1-flash-image", refs=(), label=""):
    """Returns PIL image. refs = list of PNG paths sent as style references."""
    if spent() >= CAP: raise SystemExit(f"budget cap reached: ${spent():.2f}")
    content = [{"type": "text", "text": prompt}]
    for p in refs:
        b = base64.b64encode(open(p, "rb").read()).decode()
        content.append({"type": "image_url", "image_url": {"url": "data:image/png;base64," + b}})
    body = {"model": model, "modalities": ["image", "text"], "messages": [{"role": "user", "content": content}]}
    req = urllib.request.Request("https://openrouter.ai/api/v1/chat/completions", json.dumps(body).encode(),
        {"Authorization": "Bearer " + _key(), "Content-Type": "application/json"})
    try:
        r = json.load(urllib.request.urlopen(req, timeout=180))
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"HTTP {e.code}: {e.read()[:300].decode(errors='replace')}")
    _log(model, (r.get("usage") or {}).get("cost", 0.0), label)
    imgs = r["choices"][0]["message"].get("images") or []
    if not imgs: raise RuntimeError("no image returned")
    m = re.match(r"data:image/\w+;base64,(.*)", imgs[0]["image_url"]["url"], re.S)
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


def despeckle(img, maxdist=110, minagree=6):
    """Replace isolated pixels whose colour is a near-shade of the colour 6+ of their 8 neighbours agree on.
    Leaves far-colour single pixels (pupils, highlights) alone."""
    from collections import Counter
    w, h = img.size; src = img.copy(); px = src.load(); out = img.copy(); o = out.load(); n = 0
    for y in range(h):
        for x in range(w):
            c = px[x, y]
            nb = [px[xx, yy] for yy in range(max(0, y-1), min(h, y+2)) for xx in range(max(0, x-1), min(w, x+2)) if (xx, yy) != (x, y)]
            if sum(1 for q in nb if q == c) > 1: continue
            top, cnt = Counter(nb).most_common(1)[0]
            if cnt >= minagree and top != c and sum((a-b)**2 for a, b in zip(c, top)) ** 0.5 < maxdist:
                o[x, y] = top; n += 1
    return out
