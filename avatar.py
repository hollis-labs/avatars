#!/usr/bin/env python3
"""Idempotent 8-bit agent avatar generator.
usage: avatar.py <urn-name> [--role R] [--species S] [--mood M] [--accent #hex] [--bg #hex]
                 [--model M] [--out DIR] [--force] [--dry-run]
Output: <out>/<safe-urn-name>.png (64x64 palette-locked) + .json sidecar. Existing file => no model call."""
import argparse, colorsys, hashlib, json, os, re, sys, unicodedata, io
from collections import Counter
from PIL import Image
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib import generate, pixelate, upscale, ncolors, spent, despeckle

HERE = os.path.dirname(os.path.abspath(__file__))
GOLDEN = os.path.join(HERE, "golden", "robot-01.png")
DEFAULT_MODEL = "google/gemini-3.1-flash-lite-image"
GRID = 64
BASE = ["#0B0B14", "#2B2D42", "#5C6378", "#8D99AE", "#C5CBD6", "#EDF2F4"]  # outline + greys + white

# curated (name, accent, bg): distinct hues, dark contrasting backgrounds. Shared-table candidate for both generators.
CURATED = [("coral","#FF6B5B","#1F2A44"),("amber","#FFB627","#2B2D5B"),("lime","#A6E22E","#3B2A4D"),("mint","#2EE6A6","#3A2438"),
 ("cyan","#3DDCF2","#4A2C2A"),("sky","#5AA9FF","#2D3A2A"),("violet","#9B6BFF","#1D3B3A"),("magenta","#FF4FA3","#1E3A5F"),
 ("red","#FF3B3B","#14323A"),("orange","#FF8A2B","#263A5E"),("yellow","#FFE14D","#2E2A5E"),("teal","#1FC8B8","#4A2B4F"),
 ("pink","#FF8FC7","#243B4A"),("green","#44D96B","#3D2B3F"),("periwinkle","#7C8CFF","#3A3326"),("cream","#F2E3A1","#3B2B55")]

REGISTRY = os.environ.get("AVATAR_REGISTRY", os.path.join(HERE, "palette_registry.json"))

def curated_pair(urn, commit=True):
    """Palette slot is assigned at first use and persisted, so ids never share a slot while free slots remain.
    Start at sha256(NFC urn) % N and probe forward past taken slots. Deterministic for a given registry; the
    assignment depends on first-use order, so the registry file is the source of truth (commit it)."""
    urn = unicodedata.normalize("NFC", urn)
    try: reg = json.load(open(REGISTRY))
    except Exception: reg = {}
    if urn not in reg:
        h = hashlib.sha256(urn.encode()).digest(); idx = (h[0] << 8 | h[1]) % len(CURATED)
        used = set(reg.values())
        for k in range(len(CURATED)):
            if (idx + k) % len(CURATED) not in used: idx = (idx + k) % len(CURATED); break
        reg[urn] = idx   # all slots taken: falls back to the hash slot (shared)
        if commit:
            tmp = REGISTRY + ".tmp"; json.dump(reg, open(tmp, "w"), indent=1, ensure_ascii=False); os.replace(tmp, REGISTRY)
    name, accent, bg = CURATED[reg[urn]]
    return name, bg, accent

def safe_name(urn):  # filename must match the URN name: keep unicode letters (NFC), strip only path-hostile chars
    return re.sub(r"[^\w.@+-]", "_", unicodedata.normalize("NFC", urn))

def seeded_colors(urn):
    h = hashlib.sha256(urn.encode()).digest()
    hue = h[0] / 255; sat = 0.55 + h[1] / 255 * 0.35
    def hx(hh, s, v): return "#%02X%02X%02X" % tuple(int(c*255) for c in colorsys.hsv_to_rgb(hh % 1, s, v))
    return hx(hue + 0.5, 0.55, 0.35), hx(hue, sat, 0.95)   # bg (dark complement), accent

def lighten_darken(hexc):
    r, g, b = (int(hexc[i:i+2], 16)/255 for i in (1, 3, 5)); hh, s, v = colorsys.rgb_to_hsv(r, g, b)
    f = lambda vv, ss: "#%02X%02X%02X" % tuple(int(c*255) for c in colorsys.hsv_to_rgb(hh, ss, vv))
    return [f(min(1, v*1.15), s*0.7), f(v*0.6, min(1, s*1.1))]

def _hex(c): return tuple(int(c[i:i+2], 16) for i in (1, 3, 5))

def sprite_ref(path, bg, accent=None, style="sprite", grid=8):
    """Identity reference image built from the procedural sprite. Returns (png path, dominant colour hex, ascii mask).
    style: sprite = sprite as-is | outline = silhouette only, dark outline, flat fill | mask = sprite (prompt also carries ASCII mask).
    If accent is given the sprite is recoloured to it (luminance ramp) so identity and palette agree."""
    im = Image.open(path).convert("RGBA"); W = im.width; cell = W // grid
    lit = Counter(im.getpixel((x, y))[:3] for y in range(0, W, cell) for x in range(0, W, cell) if im.getpixel((x, y))[3] > 0)
    domc = lit.most_common(1)[0][0]; dom = "#%02X%02X%02X" % domc
    lum = lambda c: 0.3*c[0] + 0.59*c[1] + 0.11*c[2]
    cells = [[im.getpixel((x*cell + cell//2, y*cell + cell//2)) for x in range(grid)] for y in range(grid)]
    mask = ["".join("#" if cells[y][x][3] > 0 else "." for x in range(grid)) for y in range(grid)]
    tgt = _hex(accent) if accent else domc
    def recolor(c):
        if not accent: return c
        r = lum(c) / max(lum(domc), 1)
        return tuple(min(255, int(v*r + (255-v)*max(0, r-1)*0.8)) if r >= 1 else int(v*r) for v in tgt)
    bgc = _hex(bg) if isinstance(bg, str) else bg
    small = Image.new("RGB", (grid, grid), bgc)
    for y in range(grid):
        for x in range(grid):
            if cells[y][x][3] > 0: small.putpixel((x, y), recolor(cells[y][x][:3]))
    big = small.resize((grid*64, grid*64), Image.NEAREST)
    if style == "outline":
        big = Image.new("RGB", (grid*64, grid*64), bgc); px = big.load(); m = [[cells[y][x][3] > 0 for x in range(grid)] for y in range(grid)]
        S = 64
        for y in range(grid):
            for x in range(grid):
                if not m[y][x]: continue
                for yy in range(S):
                    for xx in range(S):
                        px[x*S+xx, y*S+yy] = tgt
        # 4px dark outline on silhouette edges
        edge = []
        for y in range(grid):
            for x in range(grid):
                if not m[y][x]: continue
                for dx, dy in ((1,0),(-1,0),(0,1),(0,-1)):
                    nx, ny = x+dx, y+dy
                    if not (0 <= nx < grid and 0 <= ny < grid and m[ny][nx]): edge.append((x, y, dx, dy))
        for x, y, dx, dy in edge:
            for t in range(S):
                for k in range(5):
                    ox = (x*S + (S-1-k if dx > 0 else k)) if dx else x*S + t
                    oy = (y*S + (S-1-k if dy > 0 else k)) if dy else y*S + t
                    px[ox, oy] = (11, 11, 20)
    tmp = os.path.join(HERE, "out", ".sprite_ref_%s.png" % hashlib.sha1((path + str(bg) + str(accent) + style).encode()).hexdigest()[:10])
    big.save(tmp); return tmp, dom, mask

MASK = []

def build_prompt(a, bg, accent):
    subj = f"a {a.species} agent"
    if a.role: subj += f" ({a.role})"
    if a.mood: subj += f", mood: {a.mood}"
    if a.identity_ref:
        how = {"sprite": "IMAGE 2 is a tiny 8x8 pixel sprite that defines THIS agent's identity: keep its overall silhouette (head shape, ear/antenna bumps, body shape) and its main color as the character's accent color, but redraw it as a fully detailed character in the style of IMAGE 1 (face, eyes, outline, shading). ",
               "outline": "IMAGE 2 is a flat silhouette of THIS agent: the filled shape is the character's exact outer outline. Keep that outline shape (head, ear/antenna bumps, shoulders, arms) as the outer contour of the character and use its fill color as the accent color; draw all interior detail (face, eyes, shading) in the style of IMAGE 1. ",
               "mask": "IMAGE 2 is a tiny 8x8 pixel sprite that defines THIS agent's identity, and here it is as an ASCII mask (# = body pixel, . = empty), top to bottom:\n" + "\n".join(MASK) + "\nFollow the mask: the character's outer silhouette (head, ear/antenna bumps, shoulders, arms) must match it, with its color as the accent color; redraw it fully detailed in the style of IMAGE 1. "}[a.ref_style]
        return ("Two reference images. IMAGE 1 is the golden style reference: match its art style, pixel size, proportions, 1-pixel dark outline, shading and framing exactly. " + how +
                "Hard pixel edges only, no anti-aliasing, no gradients, no text. " + f"Subject: a {a.species} agent" + (f" ({a.role})" if a.role else "") + ". "
                f"Flat solid background color {bg}. Head and shoulders, centered, facing the viewer, square image.")
    return ("The attached image is the golden style reference. Match its art style, pixel size, proportions, "
            "1-pixel dark outline, framing and shading exactly. Hard pixel edges only, no anti-aliasing, "
            "no gradients, no text. Draw a NEW character in that style: " + subj + ". "
            f"Flat solid background color {bg}. Accent color (eyes, antenna/ear details, chest emblem) {accent}. "
            "Head and shoulders, centered, facing the viewer, square image.")

def main():
    p = argparse.ArgumentParser()
    p.add_argument("urn"); p.add_argument("--role", default=""); p.add_argument("--species", default="robot")
    p.add_argument("--mood", default=""); p.add_argument("--identity-ref"); p.add_argument("--ref-style", default="sprite", choices=["sprite","outline","mask"]); p.add_argument("--curated", action="store_true"); p.add_argument("--no-despeckle", action="store_true"); p.add_argument("--accent"); p.add_argument("--bg")
    p.add_argument("--model", default=DEFAULT_MODEL); p.add_argument("--out", default=os.path.join(HERE, "agents"))
    p.add_argument("--force", action="store_true"); p.add_argument("--dry-run", action="store_true")
    a = p.parse_args()
    name = safe_name(a.urn); os.makedirs(a.out, exist_ok=True)
    png, meta = os.path.join(a.out, name + ".png"), os.path.join(a.out, name + ".json")
    if os.path.exists(png) and not a.force:
        print(f"exists, unchanged: {png}"); return
    sbg, sac = seeded_colors(a.urn); pname = None
    if a.curated: pname, sbg, sac = curated_pair(a.urn, commit=not a.dry_run)
    bg, accent = (a.bg or sbg).upper(), (a.accent or sac).upper()
    refs = [GOLDEN]
    if a.identity_ref:
        tmp, dom, mask = sprite_ref(a.identity_ref, bg, accent if (a.curated or a.accent) else None, a.ref_style)
        MASK[:] = mask; refs.append(tmp)
        if not (a.curated or a.accent): accent = dom
    prompt = build_prompt(a, bg, accent)
    if a.dry_run: print(prompt); return
    raw = generate(prompt, a.model, refs=refs, label="avatar-" + ("hybrid-" if a.identity_ref else "") + name)
    palette = BASE + [bg, accent] + lighten_darken(accent) + lighten_darken(bg)
    small = pixelate(raw, GRID, palette)
    if not a.no_despeckle: small = despeckle(small)
    small.save(png)  # canonical 64x64
    upscale(small, 8).save(os.path.join(a.out, name + "@8x.png"))
    json.dump({"urn": a.urn, "model": a.model, "prompt": prompt, "golden": os.path.basename(GOLDEN), "identity_ref": os.path.basename(a.identity_ref) if a.identity_ref else None,
               "palette": palette, "palette_name": pname, "ref_style": a.ref_style if a.identity_ref else None, "despeckle": not a.no_despeckle, "grid": GRID, "colors_used": ncolors(small)}, open(meta, "w"), indent=1)
    print(f"wrote {png} ({ncolors(small)} colors); total spent ${spent():.2f}")

if __name__ == "__main__": main()
