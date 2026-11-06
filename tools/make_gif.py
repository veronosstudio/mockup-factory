"""Before/after email GIF: their current site, a wipe to the new homepage, then a slow scroll down the new page.

Usage: python3 tools/make_gif.py <before desktop png> <new full-page jpg> <out.gif> [width=640] [poster jpg]
The poster (0-before-after.jpg) is the FIRST frame, because Outlook desktop only shows frame 1.
"""
import sys
from PIL import Image, ImageDraw, ImageFont

before_p, after_p, out_p = sys.argv[1:4]
W = int(sys.argv[4]) if len(sys.argv) > 4 else 640
H = W * 10 // 16  # laptop-ish 16:10 frame

def font(sz):
    for f in ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
              "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"]:
        try:
            return ImageFont.truetype(f, sz)
        except OSError:
            pass
    return ImageFont.load_default()

F = font(max(11, W // 46))

def fit_top(im):
    im = im.convert("RGB")
    h = round(im.height * W / im.width)
    return im.resize((W, h), Image.LANCZOS)

before = fit_top(Image.open(before_p)).crop((0, 0, W, H))
after_full = fit_top(Image.open(after_p))
after_top = after_full.crop((0, 0, W, H))

def label(img, text, gold=False):
    img = img.copy()
    d = ImageDraw.Draw(img)
    pad = W // 64
    tw = d.textlength(text, font=F)
    th = F.size
    x, y = pad * 2, pad * 2
    d.rounded_rectangle((x, y, x + tw + pad * 3, y + th + pad * 2), radius=th,
                        fill=(212, 168, 83) if gold else (20, 20, 20))
    d.text((x + pad * 1.5, y + pad * 0.8), text, font=F, fill=(20, 20, 20) if gold else (255, 255, 255))
    return img

frames, durs = [], []
def add(img, ms):
    frames.append(img); durs.append(ms)

# 0. poster: the static before/after, so clients that show only frame 1 (Outlook) still get the point
if len(sys.argv) > 5:
    pst = Image.open(sys.argv[5]).convert('RGB')
    pst.thumbnail((W, H), Image.LANCZOS)
    bg = Image.new('RGB', (W, H), (245, 243, 238)); bg.paste(pst, ((W - pst.width) // 2, (H - pst.height) // 2))
    add(bg, 2200)

# 1. current site
add(label(before, "YOUR SITE TODAY"), 1800)

# 2. wipe to the new homepage with a gold seam
steps = 10
for i in range(1, steps + 1):
    x = round(W * i / steps)
    f = before.copy()
    f.paste(after_top.crop((0, 0, x, H)), (0, 0))
    d = ImageDraw.Draw(f)
    d.rectangle((max(0, x - 2), 0, min(W, x + 2), H), fill=(212, 168, 83))
    add(label(f, "YOUR SITE TODAY") if i < steps * 0.5 else f, 55)

# 3. new homepage
add(label(after_top, "YOUR NEW HOMEPAGE", gold=True), 1600)

# 4. slow scroll down the new page
span = after_full.height - H
n = 22
for i in range(1, n + 1):
    t = i / n
    t = t * t * (3 - 2 * t)  # ease in/out
    y = round(span * t)
    add(label(after_full.crop((0, y, W, y + H)), "YOUR NEW HOMEPAGE", gold=True), 95)
add(label(after_full.crop((0, span, W, span + H)), "YOUR NEW HOMEPAGE", gold=True), 1400)

pal = [f.quantize(colors=96, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE) for f in frames]
pal[0].save(out_p, save_all=True, append_images=pal[1:], duration=durs, loop=0, optimize=True, disposal=1)
import os
print(out_p, f"{os.path.getsize(out_p)/1e6:.2f} MB", len(frames), "frames")
