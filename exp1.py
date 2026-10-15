import sys; sys.path.insert(0, ".")
from lib import *
from prompts import *
from concurrent.futures import ThreadPoolExecutor
jobs = [("lite-strict","google/gemini-3.1-flash-lite-image",STRICT),
        ("g25-strict","google/gemini-2.5-flash-image",STRICT),
        ("pro-strict","google/gemini-3-pro-image",STRICT),
        ("flash-strict","google/gemini-3.1-flash-image",STRICT),
        ("flash-strict-b","google/gemini-3.1-flash-image",STRICT),
        ("lite-loose","google/gemini-3.1-flash-lite-image",LOOSE)]
def run(j):
    n, m, p = j
    try:
        im = generate(p, m, label="exp1-"+n); im.save(f"out/e1_{n}_raw.png")
        r = pixelate(im, 32, PAL); upscale(r, 16).save(f"out/e1_{n}_post.png")
        return n, im.size, ncolors(r)
    except Exception as e: return n, "ERR", str(e)[:200]
with ThreadPoolExecutor(6) as ex:
    for r in ex.map(run, jobs): print(r)
print("spent", spent())
