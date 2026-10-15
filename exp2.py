import sys; sys.path.insert(0, ".")
from lib import *
from prompts import PAL, STRICT
from concurrent.futures import ThreadPoolExecutor
GOLD = "out/e1_flash-strict-b_raw.png"
ROLES = {"reviewer":"wears round glasses and holds a tiny magnifying glass",
         "planner":"wears a small flat cap and has a clipboard icon on the chest",
         "builder":"wears a yellow-orange hard hat and has a wrench on the chest",
         "scribe":"has a quill pen antenna and a small scroll on the chest"}
REF = ("The attached image is the golden style reference. Match its art style, pixel size, proportions, 1-pixel dark outline, "
       "framing, flat background and exact color palette. Draw a NEW robot agent in that same style: this one ")
jobs = []
for r, d in ROLES.items():
    jobs.append((f"ref-flash-{r}", "google/gemini-3.1-flash-image", REF + d + ".", [GOLD]))
    jobs.append((f"ref-lite-{r}", "google/gemini-3.1-flash-lite-image", REF + d + ".", [GOLD]))
    jobs.append((f"noref-flash-{r}", "google/gemini-3.1-flash-image", STRICT.replace("a friendly robot agent,", f"a friendly robot agent that {d},"), []))
def run(j):
    n, m, p, refs = j
    try:
        im = generate(p, m, refs=refs, label="exp2-"+n); im.save(f"out/e2_{n}_raw.png")
        r = pixelate(im, 64, PAL); upscale(r, 8).save(f"out/e2_{n}_post.png")
        return n, ncolors(r)
    except Exception as e: return n, "ERR " + str(e)[:200]
if __name__ == "__main__":
    with ThreadPoolExecutor(6) as ex:
        for r in ex.map(run, jobs): print(r)
    print("spent", spent())
