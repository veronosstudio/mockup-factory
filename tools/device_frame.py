#!/usr/bin/env python3
"""Present a concept like an agency would: laptop + phone on a clean backdrop.

Usage: python3 tools/device_frame.py <desktop.png> <mobile.png> <out.jpg> [--bg "#E9EEF3"] [--label "NEW CONCEPT"]
       python3 tools/device_frame.py --before <their-site.png> <desktop.png> <mobile.png> <out.jpg>
  desktop.png = 1440x900 viewport shot (any scale), mobile.png = 390x844 viewport shot.
  --before makes the email image: their current site (plain, greyed laptop) on the left, the framed concept on the right.
"""
import sys
from PIL import Image, ImageDraw, ImageFilter, ImageFont

def font(sz, bold=True):
    for f in ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"]:
        try: return ImageFont.truetype(f, sz)
        except Exception: pass
    return ImageFont.load_default()

def rr(d, box, r, fill): d.rounded_rectangle(box, r, fill=fill)

def shadow(canvas, box, r, blur, off, alpha):
    sh = Image.new("L", canvas.size, 0); ImageDraw.Draw(sh).rounded_rectangle((box[0], box[1]+off, box[2], box[3]+off), r, fill=alpha)
    sh = sh.filter(ImageFilter.GaussianBlur(blur)); black = Image.new("RGB", canvas.size, (12, 18, 28))
    canvas.paste(black, (0, 0), sh)

def laptop(canvas, shot, x, y, w, grey=False):
    """screen 16:10 area, bezel, hinge and base."""
    S = canvas; d = ImageDraw.Draw(S)
    bez = int(w*0.018); sw = w-2*bez; sh_ = int(sw*900/1440); h = sh_+2*bez+int(w*0.012)
    shadow(S, (x, y, x+w, y+h+int(w*.03)), int(w*.02), int(w*.03), int(w*.02), 110)
    rr(d, (x, y, x+w, y+h), int(w*0.02), (28, 30, 34))
    img = shot.convert("RGB").resize((sw, sh_), Image.LANCZOS)
    if grey: img = Image.blend(img, img.convert("L").convert("RGB"), .35)
    S.paste(img, (x+bez, y+bez))
    d.ellipse((x+w//2-3, y+bez//2-3, x+w//2+3, y+bez//2+3), fill=(70, 72, 78))
    by = y+h; bw = int(w*1.12); bx = x-(bw-w)//2; bh = int(w*0.028)
    d.polygon([(bx, by), (bx+bw, by), (bx+bw-int(w*.02), by+bh), (bx+int(w*.02), by+bh)], fill=(196, 200, 206))
    d.rectangle((bx, by, bx+bw, by+int(bh*.35)), fill=(214, 218, 223))
    d.rounded_rectangle((x+w//2-int(w*.07), by, x+w//2+int(w*.07), by+int(bh*.35)), 4, fill=(176, 180, 186))
    return h+bh

def phone(canvas, shot, x, y, w):
    S = canvas; d = ImageDraw.Draw(S)
    bez = int(w*0.045); sw = w-2*bez; sh_ = int(sw*844/390); h = sh_+2*bez
    shadow(S, (x, y, x+w, y+h), int(w*.16), int(w*.08), int(w*.05), 140)
    rr(d, (x, y, x+w, y+h), int(w*0.16), (20, 22, 26))
    img = shot.convert("RGB").resize((sw, sh_), Image.LANCZOS)
    m = Image.new("L", (sw, sh_), 0); ImageDraw.Draw(m).rounded_rectangle((0, 0, sw, sh_), int(w*.12), fill=255)
    S.paste(img, (x+bez, y+bez), m)
    d.rounded_rectangle((x+w//2-int(w*.16), y+bez+int(w*.03), x+w//2+int(w*.16), y+bez+int(w*.03)+int(w*.075)), int(w*.04), fill=(20, 22, 26))
    return h

def framed(desk, mob, W=2400, bg=(233, 238, 243)):
    H = int(W*0.62); S = Image.new("RGB", (W, H), bg)
    lw = int(W*.74); lx = int(W*.06); ly = int(H*.09)
    laptop(S, desk, lx, ly, lw)
    pw = int(W*.17); phone(S, mob, lx+lw-int(pw*.55), int(H*.33), pw)
    return S

def main(a):
    bg = (233, 238, 243)
    if "--bg" in a: h = a[a.index("--bg")+1].lstrip("#"); bg = tuple(int(h[i:i+2], 16) for i in (0, 2, 4)); i = a.index("--bg"); del a[i:i+2]
    if a[0] == "--before":
        before, desk, mob, out = a[1:5]
        W = 3000; H = 1180; S = Image.new("RGB", (W, H), bg); d = ImageDraw.Draw(S)
        f = font(44)
        d.text((90, 70), "YOUR SITE TODAY", font=f, fill=(150, 70, 60))
        d.text((1180, 70), "NEW CONCEPT", font=f, fill=(30, 110, 70))
        laptop(S, Image.open(before), 90, 210, 920, grey=True)
        lw = 1480; lx = 1180; laptop(S, Image.open(desk), lx, 170, lw)
        pw = 330; phone(S, Image.open(mob), lx+lw-int(pw*.45), 430, pw)
        S = S.resize((W//2, H//2), Image.LANCZOS)
    else:
        desk, mob, out = a[:3]
        S = framed(Image.open(desk), Image.open(mob), bg=bg).resize((1600, int(1600*.62)), Image.LANCZOS)
    S.save(out, "JPEG", quality=86, optimize=True, progressive=True); print(out, S.size)

if __name__ == "__main__": main(sys.argv[1:])
