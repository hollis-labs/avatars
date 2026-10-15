import sys; sys.path.insert(0, ".")
from lib import *
from prompts import PAL
from concurrent.futures import ThreadPoolExecutor
GOLD = "out/e1_flash-strict-b_raw.png"; L = "google/gemini-3.1-flash-lite-image"
REF = ("The attached image is the golden style reference. Match its art style, pixel size, proportions, 1-pixel dark outline and framing. ")
jobs = [
 # background + accent recolor
 ("bg-purple", REF+"Same robot design, but flat background color #5B3FA0 and accent (eyes, antenna, chest emblem) color #FF4FA3."),
 ("bg-sand",   REF+"Same robot design, but flat background color #D9B77E and accent (eyes, antenna, chest emblem) color #1B7F4B."),
 ("bg-night",  REF+"Same robot design, but flat background color #10102A and accent (eyes, antenna, chest emblem) color #FFD23F."),
 # coarser grid
 ("grid24", REF+"Same robot, but drawn on a much coarser 24x24 pixel grid: each pixel is a big chunky block, very few details."),
 ("grid48", REF+"Same robot, but drawn on a finer 48x48 pixel grid with slightly more detail."),
 # species / form variation
 ("fox",    REF+"A NEW agent in this exact style and palette: a fox character wearing a tiny headset."),
 ("ghost",  REF+"A NEW agent in this exact style and palette: a friendly ghost with a small bow tie."),
 ("owl",    REF+"A NEW agent in this exact style and palette: an owl wearing round spectacles."),
 ("cat",    REF+"A NEW agent in this exact style and palette: a cat wearing a tiny wizard hat."),
 # mood
 ("sleepy", REF+"Same robot design, but sleepy: half-closed eyes, small 'z' above."),
 ("angry",  REF+"Same robot design, but grumpy: angled eyebrows, frown."),
 ("excited",REF+"Same robot design, but excited: wide eyes, open smile, sparkle."),
]
def run(j):
    n, p = j
    try:
        im = generate(p, L, refs=[GOLD], label="exp3-"+n); im.save(f"out/e3_{n}_raw.png")
        return n, "ok"
    except Exception as e: return n, "ERR " + str(e)[:200]
if __name__ == "__main__":
    with ThreadPoolExecutor(6) as ex:
        for r in ex.map(run, jobs): print(r)
    print("spent", spent())
