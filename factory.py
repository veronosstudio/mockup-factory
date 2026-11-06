#!/usr/bin/env python3
"""Veronos mockup factory: turns a business website into a new homepage concept, automatically, no AI.

For each business (business, website, email, phone, town, province, category):
  1. Opens their live site in a real browser: screenshots it ("before"), collects their logo, photos,
     headings, menu items, a real paragraph about them, and the colours the site actually uses.
  2. Picks one of several layout recipes and a font pairing, fills it ONLY with what was found on their
     site (plus the facts we already have: name, town, phone, email). Nothing is invented.
  3. Renders the concept, makes the email image (their site vs the concept in a laptop + phone),
     and writes a hosted page to docs/<slug>/ (served at preview.veronosstudio.com/<slug>/).

Usage:
  python3 factory.py --csv leads.csv [--limit 10] [--workers 3]
  python3 factory.py --sheet            (reads rows with status "new" from the Master Contacts sheet,
                                         writes status + links back; needs SHEET_URL and SHEET_TOKEN)
"""
import argparse, colorsys, csv, hashlib, html, io, json, os, re, shutil, subprocess, sys, time
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urljoin, urlparse
import requests
from PIL import Image
from playwright.sync_api import sync_playwright

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)
DOCS = os.path.join(ROOT, "docs")
BASE_URL = os.environ.get("PREVIEW_BASE", "https://preview.veronosstudio.com")
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
PROV = {"AB": "Alberta", "BC": "British Columbia", "SK": "Saskatchewan", "MB": "Manitoba", "ON": "Ontario",
        "QC": "Quebec", "NS": "Nova Scotia", "NB": "New Brunswick", "NL": "Newfoundland and Labrador", "PE": "Prince Edward Island"}
CAT = {"electrician": "Electrical", "plumber": "Plumbing", "hvac": "Heating & cooling", "heating_engineer": "Heating",
       "roofer": "Roofing", "carpenter": "Carpentry", "painter": "Painting", "plasterer": "Drywall & plaster",
       "tiler": "Tile", "floorer": "Flooring", "glaziery": "Glass", "insulation": "Insulation", "stonemason": "Stonework",
       "metal_construction": "Metal fabrication", "welder": "Welding", "window_construction": "Windows", "builder": "Construction",
       "gardener": "Landscaping", "landscaper": "Landscaping", "locksmith": "Locksmith", "cleaning": "Cleaning",
       "chimney_sweeper": "Chimney service", "car_repair": "Auto repair", "tyres": "Tires", "car_parts": "Auto parts",
       "motorcycle_repair": "Motorcycle repair", "truck_repair": "Truck repair", "car": "Auto sales", "hairdresser": "Hair salon",
       "beauty": "Beauty", "massage": "Massage", "tattoo": "Tattoo", "cosmetics": "Beauty", "physiotherapist": "Physiotherapy",
       "chiropractor": "Chiropractic", "dentist": "Dental", "optometrist": "Eye care", "podiatrist": "Foot care",
       "psychotherapist": "Counselling", "alternative": "Wellness", "flooring": "Flooring", "furniture": "Furniture",
       "hardware": "Hardware", "doityourself": "Hardware", "kitchen": "Kitchens", "bathroom_furnishing": "Bathrooms",
       "paint": "Paint", "appliance": "Appliances", "curtain": "Window coverings", "garden_centre": "Garden centre",
       "florist": "Florist", "gift": "Gifts", "bicycle": "Bikes", "outdoor": "Outdoor gear", "pet": "Pet supplies",
       "jewelry": "Jewellery", "optician": "Eyewear", "accountant": "Accounting", "insurance": "Insurance", "lawyer": "Law",
       "estate_agent": "Real estate", "architect": "Architecture", "surveyor": "Surveying", "church": "Church",
       "trade": "Trade supply", "electrical": "Electrical supply", "plumbing": "Plumbing supply", "security": "Security",
       "fireplace": "Fireplaces", "water": "Water treatment", "boat": "Boats & marine", "agrarian": "Farm supply"}
GENERIC = re.compile(r"^(home|welcome.*|about( us)?|contact( us)?|gallery|photos|blog|news|faq.*|login|log in|cart|checkout|"
                     r"privacy.*|terms.*|careers?|jobs|testimonials|reviews|book.*|call.*|menu|search|more|links?|"
                     r"our services|services|what we do|get in touch|follow us|location|hours|map|shop|store|"
                     r"skip to .*|close|open menu|toggle.*|english|français|\d+)$", re.I)

def log(*a): print(*a, flush=True)

def slugify(s):
    s = re.sub(r"&", " and ", s.lower()); s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s[:60] or "business"

# ---------------- colour ----------------
def hexc(rgb): return "#%02x%02x%02x" % tuple(int(x) for x in rgb[:3])
def lum(rgb):
    def ch(c): c = c / 255; return c / 12.92 if c <= .03928 else ((c + .055) / 1.055) ** 2.4
    r, g, b = rgb[:3]; return .2126 * ch(r) + .7152 * ch(g) + .0722 * ch(b)
def contrast(a, b):
    la, lb = sorted([lum(a), lum(b)], reverse=True); return (la + .05) / (lb + .05)
def shade(rgb, f):  # f<1 darker, >1 lighter (toward white)
    if f < 1: return tuple(int(c * f) for c in rgb)
    return tuple(int(c + (255 - c) * (f - 1)) for c in rgb)

def palette_from(img):
    """Pick the most-used saturated colour (brand) and a second distinct hue (accent) from a screenshot."""
    small = img.convert("RGB").resize((240, 150))
    q = small.quantize(colors=16, method=Image.Quantize.MEDIANCUT)
    pal = q.getpalette()[:48]; counts = sorted(q.getcolors(), reverse=True)
    cands = []
    for n, i in counts:
        rgb = tuple(pal[i * 3:i * 3 + 3]); h, s, v = colorsys.rgb_to_hsv(*[c / 255 for c in rgb])
        if s > .32 and .18 < v < .95: cands.append((n * (0.6 + s), rgb, h))
    cands.sort(reverse=True)
    brand = cands[0][1] if cands else None
    accent = None
    if brand:
        bh = cands[0][2]
        for _, rgb, h in cands[1:]:
            if min(abs(h - bh), 1 - abs(h - bh)) > .08: accent = rgb; break
    return brand, accent

# ---------------- 1. read their site ----------------
JS_COLLECT = """
() => {
  const txt = e => (e.innerText || '').replace(/\\s+/g, ' ').trim();
  const imgs = [...document.images].map(i => ({src: i.currentSrc || i.src, w: i.naturalWidth, h: i.naturalHeight,
      alt: i.alt || '', cls: (i.className && i.className.baseVal === undefined ? i.className : '') + ' ' + (i.id || ''),
      inHeader: !!i.closest('header, nav, [class*=header], [id*=header], [class*=logo], [id*=logo]'),
      top: i.getBoundingClientRect().top + scrollY}));
  const bgs = [...document.querySelectorAll('section, div, header')].slice(0, 400).map(e => {
      const m = getComputedStyle(e).backgroundImage.match(/url\\(["']?([^"')]+)/); const r = e.getBoundingClientRect();
      return m ? {src: m[1], w: r.width, h: r.height, top: r.top + scrollY} : null }).filter(Boolean);
  return {
    title: document.title,
    desc: (document.querySelector('meta[name=description]') || {}).content || '',
    h1: [...document.querySelectorAll('h1')].map(txt).filter(Boolean),
    h2: [...document.querySelectorAll('h2, h3')].map(txt).filter(Boolean).slice(0, 40),
    nav: [...document.querySelectorAll('nav a, header a, [class*=menu] a')].map(txt).filter(Boolean).slice(0, 60),
    paras: [...document.querySelectorAll('p, [class*=text] div, td, font, span')].map(txt).filter(t => t.length > 90 && t.length < 1200).slice(0, 40),
    items: [...document.querySelectorAll('li, strong, b, td a, a, h4, h5')].map(txt).filter(t => t.length > 2 && t.length < 45).slice(0, 220),
    alts: [...document.images].map(i => (i.alt || '').trim()).filter(t => t.length > 3 && t.length < 45).slice(0, 40),
    body: (document.body ? document.body.innerText : '').slice(0, 20000),
    imgs, bgs,
    tel: [...document.querySelectorAll('a[href^="tel:"]')].map(a => a.getAttribute('href').slice(4)).slice(0, 3),
  };
}
"""

def download(url, path, referer):
    try:
        r = requests.get(url, headers={"User-Agent": UA, "Referer": referer}, timeout=20)
        if r.status_code != 200 or len(r.content) < 1500: return False
        im = Image.open(io.BytesIO(r.content))
        if im.mode in ("P", "LA", "RGBA"):
            im = im.convert("RGBA")
            if path.endswith(".png"): im.save(path); return im.size
            bg = Image.new("RGB", im.size, (255, 255, 255)); bg.paste(im, mask=im.split()[-1]); im = bg
        im = im.convert("RGB")
        if im.width > 1800: im.thumbnail((1800, 1800))
        im.save(path, quality=82); return im.size
    except Exception:
        return False

def read_site(page, biz, out):
    url = biz["website"]
    page.goto(url, wait_until="domcontentloaded", timeout=35000)
    page.wait_for_timeout(3500)
    try: page.mouse.move(400, 300); page.mouse.wheel(0, 300); page.wait_for_timeout(600); page.mouse.wheel(0, -300); page.wait_for_timeout(500)
    except Exception: pass
    page.screenshot(path=os.path.join(out, "_before.png"))
    data = page.evaluate(JS_COLLECT)
    final = page.url
    before = Image.open(os.path.join(out, "_before.png"))
    brand, accent = palette_from(before)
    # logo
    logo = None
    cands = [i for i in data["imgs"] if i["src"] and i["w"] >= 60 and (re.search(r"logo", i["src"] + i["alt"] + i["cls"], re.I) or i["inHeader"]) and i["top"] < 400]
    cands.sort(key=lambda i: (not re.search(r"logo", i["src"] + i["alt"] + i["cls"], re.I), i["top"]))
    for c in cands[:3]:
        ext = ".png" if re.search(r"\.png|\.svg|webp", c["src"], re.I) else ".jpg"
        if ".svg" in c["src"].lower(): continue
        sz = download(urljoin(final, c["src"]), os.path.join(out, "logo" + ext), final)
        if sz and sz[0] >= 60 and sz[0] / max(sz[1], 1) < 8: logo = "logo" + ext; break
    # photos: big images that are not the logo
    seen, photos = set(), []
    pool = [i for i in data["imgs"] if i["w"] >= 380 and 0.55 < i["w"] / max(i["h"], 1) < 2.6]
    pool += [{"src": b["src"], "w": b["w"], "h": b["h"], "alt": "", "cls": "", "inHeader": False, "top": b["top"]}
             for b in data["bgs"] if b["w"] >= 500 and b["h"] >= 220]
    pool.sort(key=lambda i: i["top"])
    for c in pool:
        src = urljoin(final, c["src"])
        if src in seen or re.search(r"logo|icon|sprite|badge|\.svg|\.gif", src, re.I): continue
        seen.add(src); n = len(photos) + 1
        sz = download(src, os.path.join(out, f"p{n}.jpg"), final)
        if sz and sz[0] >= 380 and sz[1] >= 220:
            if sz[0] < 1100:
                from PIL import ImageFilter
                im = Image.open(os.path.join(out, f"p{n}.jpg")); f = 1100 / sz[0]
                im = im.resize((1100, int(sz[1] * f)), Image.LANCZOS).filter(ImageFilter.UnsharpMask(1.2, 60, 2)); im.save(os.path.join(out, f"p{n}.jpg"), quality=84)
            photos.append(f"p{n}.jpg")
        if len(photos) >= 4: break
    return data, final, brand, accent, logo, photos

# ---------------- 2. content (only what's real) ----------------
def sentencey(t):
    """Real prose, not a menu mashed together: mostly lowercase, has a verb-ish word, ends like a sentence."""
    letters = [ch for ch in t if ch.isalpha()]
    if not letters or sum(ch.isupper() for ch in letters) / len(letters) > .35: return False
    if not re.search(r"\b(is|are|we|our|offer|offers|provide|provides|serving|serve|specializ\w*|have|has|been|can|will|make|help)\b", t, re.I): return False
    return True

def clean(t, n):
    t = re.sub(r"\s+", " ", t or "").strip()
    if len(t) <= n: return t
    cut = t[:n]; m = max(cut.rfind(". "), cut.rfind("! "))
    return cut[:m + 1] if m > n * 0.5 else cut.rsplit(" ", 1)[0] + "…"

def pick_services(data, name):
    out = []
    for t in data["nav"] + data["h2"] + data.get("items", []) + data.get("alts", []):
        t = t.strip(" -|•·>").strip()
        if not (3 <= len(t) <= 38) or GENERIC.match(t) or name.lower() in t.lower(): continue
        if re.search(r"[@©]|\d{3}[\s.-]\d{3}|http|www\.|copyright|rights reserved|click|read more|learn more|we're|you", t, re.I): continue
        if len(t.split()) > 6: continue
        nm = [w for w in re.findall(r"[a-z]{4,}", name.lower()) if w not in ("auto", "service", "services", "ltd", "inc")]
        if any(w in t.lower() for w in nm): continue
        if re.search(r"index|links?\b|join|team|email|find us|how to|sitemap|directions|specials|coupon|careers|photo|video|facebook|instagram|twitter|youtube|google|map\b", t, re.I): continue
        tt = t if not t.isupper() else t.title()
        if tt.lower() not in [o.lower() for o in out]: out.append(tt)
        if len(out) >= 6: break
    return out

def pick_headline(data, biz, cat, place):
    for h in data["h1"]:
        h = clean(h, 90)
        if 12 <= len(h) <= 70 and not re.match(r"^(welcome|home|hello|hi\b)", h, re.I) and "|" not in h:
            return h
    return f"{cat} in {place}" if cat else biz["business"]

def pick_about(data, name):
    for p in data["paras"]:
        p = clean(p, 330)
        if re.search(r"cookie|privacy|javascript|subscribe|newsletter|copyright|all rights", p, re.I): continue
        if len(p) >= 90 and sentencey(p): return p
    return ""


PROV_RE = r"(AB|Alta\.?|Alberta|BC|B\.C\.|British Columbia|SK|Sask\.?|Saskatchewan|MB|Manitoba|ON|Ont\.?|Ontario|NS|NB|NL|PE|QC)"
def find_city(body):
    for m in re.finditer(r"([A-Z][A-Za-z'.]+(?:\s[A-Z][A-Za-z'.]+){0,2}),?\s+" + PROV_RE + r"\b", body or ""):
        city = m.group(1).strip()
        if not re.search(r"(street|st|ave|avenue|road|rd|drive|dr|box|suite|unit|hwy|highway|trail|blvd|way|crescent|close|bay)$", city, re.I) and len(city) <= 28:
            return city.split()[-2] + " " + city.split()[-1] if len(city.split()) > 2 else city
    return ""

def find_since(body):
    m = re.search(r"(?:since|established|est\.?|founded(?: in)?|serving[^.]{0,40}since|in business since)\s*(?:in\s*)?((?:18|19|20)\d\d)", body or "", re.I)
    if m and 1850 <= int(m.group(1)) <= 2021: return m.group(1)
    return ""

def find_hours(body):
    out = []
    for m in re.finditer(r"((?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)[a-z]*\.?(?:\s*(?:-|–|to|&)\s*(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)[a-z]*\.?)?)\s*:?\s*((?:\d{1,2}(?::\d\d)?\s*(?:am|pm|a\.m\.|p\.m\.)?\s*(?:-|–|to)\s*\d{1,2}(?::\d\d)?\s*(?:am|pm|a\.m\.|p\.m\.)?)|closed|by appointment)", body or "", re.I):
        d, h = m.group(1).strip(), m.group(2).strip()
        if d.lower() not in [x[0].lower() for x in out]: out.append((d, h))
        if len(out) >= 6: break
    return out if len(out) >= 2 else []

def find_points(data, name):
    """Up to 3 real sentences from their own site that say something about them (not legal or cookie text)."""
    pts = []
    for p in data["paras"]:
        for sent in re.split(r"(?<=[.!?])\s+", p):
            sent = sent.strip()
            if not (45 <= len(sent) <= 170) or not sentencey(sent): continue
            if re.search(r"cookie|privacy|copyright|rights reserved|javascript|click|website|newsletter|subscribe|\?$", sent, re.I): continue
            if not re.search(r"\b(we|our|us|family|years|since|team|owned|customers?|quality|service|experience|locally|proud|guarantee|certified|licensed)\b", sent, re.I): continue
            if sent not in pts: pts.append(sent)
            if len(pts) >= 3: return pts
    return pts

STOCK_MAP = {"electrician": "electrician", "electrical": "electrician", "plumber": "plumber", "plumbing": "plumber", "hvac": "furnace and HVAC",
             "heating_engineer": "furnace and HVAC", "roofer": "roofing", "painter": "painting contractor", "gardener": "landscaping",
             "landscaper": "landscaping", "car_repair": "auto repair", "tyres": "auto repair", "car_parts": "auto repair", "truck_repair": "auto repair",
             "motorcycle_repair": "auto repair", "car": "auto repair", "hairdresser": "hair salon", "beauty": "spa and massage", "massage": "spa and massage",
             "cleaning": "cleaning service", "flooring": "flooring store", "floorer": "flooring store", "tiler": "flooring store", "furniture": "furniture store",
             "florist": "florist", "gift": "gift shop"}
def stock_for(cat, out):
    try:
        idx = json.load(open(os.path.join(ROOT, "stock", "INDEX.json")))
        files = idx.get(STOCK_MAP.get(cat, ""), [])
    except Exception:
        files = []
    used = []
    for f in files[:3]:
        src = os.path.join(ROOT, "stock", f)
        if os.path.exists(src):
            shutil.copy(src, os.path.join(out, "s_" + f)); used.append("s_" + f)
    return used

# ---------------- 3. layouts ----------------
FONTS = [
    ("Archivo Black", "Archivo:wght@400;500;600", "'Archivo Black'", "Archivo"),
    ("Fraunces:opsz,wght@9..144,600", "Manrope:wght@400;500;700", "Fraunces", "Manrope"),
    ("Oswald:wght@600;700", "Source+Sans+3:wght@400;600", "Oswald", "'Source Sans 3'"),
    ("DM+Serif+Display", "DM+Sans:wght@400;500;700", "'DM Serif Display'", "'DM Sans'"),
    ("Sora:wght@700;800", "Inter:wght@400;500;600", "Sora", "Inter"),
    ("Bricolage+Grotesque:opsz,wght@12..96,700;12..96,800", "Figtree:wght@400;500;600", "'Bricolage Grotesque'", "Figtree"),
    ("Zilla+Slab:wght@600;700", "Rubik:wght@400;500", "'Zilla Slab'", "Rubik"),
    ("Playfair+Display:wght@700;800", "Karla:wght@400;500;700", "'Playfair Display'", "Karla"),
]
DEFAULT_BRANDS = [(31, 63, 143), (154, 31, 43), (34, 94, 74), (196, 92, 29), (40, 44, 52), (92, 54, 122)]

def theme(brand, accent, seed):
    if not brand: brand = DEFAULT_BRANDS[seed % len(DEFAULT_BRANDS)]
    if lum(brand) > .45: brand = shade(brand, .62)  # too light to carry white text
    dark = shade(brand, .38)
    if not accent or contrast(accent, (255, 255, 255)) < 1.6: accent = shade(brand, 1.55) if lum(brand) < .2 else (242, 193, 78)
    on_brand = "#ffffff" if contrast(brand, (255, 255, 255)) >= 3 else "#111111"
    paper = shade(brand, 1.94)
    brand2 = shade(brand, 1.45) if lum(brand) < .25 else brand
    return {"brand": hexc(brand), "brand2": hexc(brand2), "dark": hexc(dark), "accent": hexc(accent), "on": on_brand,
            "paper": hexc(paper), "paper2": hexc(shade(brand, 1.88)), "line": hexc(shade(brand, 1.78)),
            "on_accent": "#111111" if lum(accent) > .35 else "#ffffff"}

LAYOUTS = ["split", "fullbleed", "bold", "editorial", "panel", "minimal"]
PHOTO_LAYOUTS = {"split", "fullbleed", "panel"}

def render_html(biz, c, layout, fonts):
    e = lambda s: html.escape(s or "")
    f1, f2, d1, d2 = fonts
    name, phone, email = e(biz["business"]), e(c["phone"]), e(biz["email"])
    hero_img = c["photos"][0] if c["photos"] else ""
    logo_html = f'<img class="logo" src="{c["logo"]}" alt="{name}">' if c["logo"] else f'<span class="word">{name}</span>'
    services = c["services"]
    svc_cards = "".join(
        f'<div class="svc">' + (f'<img src="{c["photos"][(i + 1) % len(c["photos"])]}" alt="">' if c["photos"] and layout != "minimal" and i < 3 else "")
        + f'<h3>{e(s)}</h3></div>' for i, s in enumerate(services[:6]))
    if not svc_cards:
        svc_cards = f'<div class="svc"><h3>{e(c["cat"] or "Our work")}</h3></div><div class="svc"><h3>Serving {e(c["place"])}</h3></div><div class="svc"><h3>Call {phone or "us"}</h3></div>'
    about = f'<section class="about"><div class="wrap"><h2>About {name}</h2><p>{e(c["about"])}</p></div></section>' if c["about"] else ""
    sub = e(c["sub"])
    tagline = e(" · ".join(x for x in [c["cat"], c["place"]] if x))
    T = c["theme"]
    css = f"""
:root{{--brand:{T['brand']};--dark:{T['dark']};--accent:{T['accent']};--on:{T['on']};--paper:{T['paper']};--onacc:{T['on_accent']}}}
*{{box-sizing:border-box;margin:0;padding:0}}body{{font-family:{d2},system-ui,sans-serif;color:#15171c;background:#fff;font-size:18px;line-height:1.6}}
a{{color:inherit;text-decoration:none}}img{{display:block;max-width:100%}}
h1,h2,h3,.word{{font-family:{d1},serif;line-height:1.02;letter-spacing:-.01em}}
.concept{{background:#111;color:#bbb;font-size:12px;text-align:center;padding:6px}}
.wrap{{max-width:1180px;margin:0 auto;padding:0 40px}}
header .wrap{{display:flex;align-items:center;gap:24px;height:86px}}.logo{{max-height:60px;max-width:240px;object-fit:contain}}
.word{{font-size:26px;color:var(--dark)}}nav{{margin-left:auto;display:flex;gap:24px;font-size:15px;font-weight:500}}
.call{{background:var(--brand);color:var(--on);padding:11px 18px;border-radius:8px;font-weight:600;font-size:15px;white-space:nowrap}}
.tag{{font-size:13px;letter-spacing:.14em;text-transform:uppercase;font-weight:600;opacity:.85}}
h1{{font-size:clamp(42px,5.2vw,78px);margin:16px 0 18px}}.sub{{font-size:19px;max-width:32em;opacity:.9}}
.btns{{display:flex;gap:12px;margin-top:28px;flex-wrap:wrap}}.btn{{padding:15px 24px;border-radius:8px;font-weight:600;font-size:16px}}
.b1{{background:var(--accent);color:var(--onacc)}}.b2{{border:2px solid currentColor}}
section{{padding:90px 0}}h2{{font-size:clamp(34px,3.8vw,54px);margin-bottom:26px;color:var(--dark)}}
.grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:18px}}
.svc{{background:var(--paper);border-radius:12px;overflow:hidden}}.svc img{{aspect-ratio:16/10;object-fit:cover;width:100%}}
.svc h3{{font-size:24px;padding:22px 22px 24px;color:var(--dark)}}
.about{{background:var(--dark);color:#fff}}.about h2{{color:#fff}}.about p{{font-size:21px;max-width:40em;opacity:.92}}
.contact{{text-align:center}}.contact .big{{font-family:{d1};font-size:clamp(40px,6vw,84px);color:var(--brand);margin:12px 0}}
.contact p{{color:#555}}footer{{border-top:1px solid #eee;padding:22px 0;font-size:13px;color:#777}}
footer .wrap{{display:flex;justify-content:space-between;flex-wrap:wrap;gap:8px}}
"""
    hero = {
        "split": f"""<section class="hero" style="padding:0;background:var(--paper)"><div class="wrap" style="display:grid;grid-template-columns:1.05fr .95fr;gap:50px;align-items:center;padding-top:70px;padding-bottom:70px">
<div><div class="tag" style="color:var(--brand)">{tagline}</div><h1 style="color:var(--dark)">{e(c['headline'])}</h1><p class="sub">{sub}</p>
<div class="btns"><a class="btn b1" href="#">Get in touch</a><a class="btn b2" style="color:var(--dark)" href="#">{phone or 'Contact us'}</a></div></div>
<div style="border-radius:18px;overflow:hidden;height:470px;background:url({hero_img}) center/cover;box-shadow:0 40px 70px -40px rgba(0,0,0,.5)"></div></div></section>""",
        "fullbleed": f"""<section class="hero" style="min-height:600px;display:flex;align-items:flex-end;color:#fff;background:linear-gradient(90deg,rgba(0,0,0,.78),rgba(0,0,0,.25)),url({hero_img}) center/cover;padding:0">
<div class="wrap" style="padding-bottom:80px;width:100%"><div class="tag">{tagline}</div><h1 style="max-width:13em">{e(c['headline'])}</h1><p class="sub">{sub}</p>
<div class="btns"><a class="btn b1" href="#">Get in touch</a><a class="btn b2" href="#">{phone or 'Contact us'}</a></div></div></section>""",
        "bold": f"""<section class="hero" style="background:var(--brand);color:var(--on);padding:90px 0 100px"><div class="wrap">
<div class="tag">{tagline}</div><h1 style="font-size:clamp(50px,6.6vw,104px);max-width:12em">{e(c['headline'])}</h1><p class="sub">{sub}</p>
<div class="btns"><a class="btn b1" href="#">Get in touch</a><a class="btn b2" href="#">{phone or 'Contact us'}</a></div></div></section>""",
        "editorial": f"""<section class="hero" style="background:var(--paper);text-align:center;padding:100px 0 80px"><div class="wrap" style="max-width:900px">
<div class="tag" style="color:var(--brand)">{tagline}</div><h1 style="color:var(--dark);font-size:clamp(46px,6vw,92px)">{e(c['headline'])}</h1><p class="sub" style="margin:0 auto">{sub}</p>
<div class="btns" style="justify-content:center"><a class="btn b1" style="background:var(--brand);color:var(--on)" href="#">Get in touch</a><a class="btn b2" style="color:var(--dark)" href="#">{phone or 'Contact us'}</a></div></div>
{f'<div class="wrap" style="margin-top:60px"><div style="height:380px;border-radius:6px;background:url({hero_img}) center/cover"></div></div>' if hero_img else ''}</section>""",
        "panel": f"""<section class="hero" style="padding:0;position:relative;background:url({hero_img}) center/cover;min-height:620px"><div class="wrap" style="padding-top:120px;padding-bottom:90px">
<div style="background:var(--dark);color:#fff;max-width:620px;padding:46px 46px 40px;border-radius:6px;box-shadow:0 40px 80px -40px #000">
<div class="tag" style="color:var(--accent)">{tagline}</div><h1>{e(c['headline'])}</h1><p class="sub">{sub}</p>
<div class="btns"><a class="btn b1" href="#">Get in touch</a><a class="btn b2" href="#">{phone or 'Contact us'}</a></div></div></div></section>""",
        "minimal": f"""<section class="hero" style="padding:110px 0 70px;border-bottom:8px solid var(--brand)"><div class="wrap">
<div class="tag" style="color:var(--brand)">{tagline}</div><h1 style="font-size:clamp(52px,7vw,112px);max-width:11em;color:var(--dark)">{e(c['headline'])}</h1>
<div style="display:flex;gap:40px;justify-content:space-between;align-items:end;flex-wrap:wrap"><p class="sub">{sub}</p><div class="btns"><a class="btn b1" style="background:var(--brand);color:var(--on)" href="#">Get in touch</a></div></div></div></section>""",
    }[layout]
    mobile = "@media(max-width:880px){.wrap{padding:0 18px}nav{display:none}.call{margin-left:auto}header .wrap{height:70px}.logo{max-height:44px;max-width:160px}.word{font-size:20px}.hero .wrap{grid-template-columns:1fr!important;padding-top:40px!important}.hero .wrap>div[style*='height:470px']{height:260px!important}.grid{grid-template-columns:1fr}section{padding:60px 0}.hero{min-height:auto!important}}"
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex,nofollow"><title>{name}: concept by Veronos Studio</title>
<link href="https://fonts.googleapis.com/css2?family={f1}&family={f2}&display=swap" rel="stylesheet"><style>{css}{mobile}</style></head><body>
<div class="concept"><b>Concept preview</b> by Veronos Studio, not the official {name} website</div>
<header><div class="wrap">{logo_html}<nav><a href="#">Services</a><a href="#">About</a><a href="#">Contact</a></nav><a class="call" href="#">{phone or 'Contact'}</a></div></header>
{hero}
<section><div class="wrap"><h2>What we do</h2><div class="grid">{svc_cards}</div></div></section>
{about}
<section class="contact"><div class="wrap"><div class="tag" style="color:var(--brand)">Get in touch</div><div class="big">{phone or email}</div><p>{email}{' · ' + e(c['place']) if c['place'] else ''}</p></div></section>
<footer><div class="wrap"><span>{name}{', ' + e(c['place']) if c['place'] else ''}</span><span>Concept design by Veronos Studio</span></div></footer>
</body></html>"""

# ---------------- 4. build one ----------------
def build(biz, browser):
    slug = slugify(biz["business"] + "-" + (biz.get("town") or biz.get("province") or ""))
    out = os.path.join(DOCS, slug); os.makedirs(out, exist_ok=True)
    seed = int(hashlib.md5(slug.encode()).hexdigest(), 16)
    ctx = browser.new_context(viewport={"width": 1440, "height": 900}, user_agent=UA, ignore_https_errors=True)
    page = ctx.new_page()
    try:
        data, final, brand, accent, logo, photos = read_site(page, biz, out)
    finally:
        ctx.close()
    # Quality gate: if we could not read real content from their site, do not make a generic page.
    words = len(" ".join(data["h1"] + data["h2"] + data["paras"]).split())
    if words < 25 or (not photos and not logo and words < 80):
        raise RuntimeError(f"SKIP not enough real content on their site ({words} words, {len(photos)} photos, logo={bool(logo)})")
    cat_key = (biz.get("category") or "").lower()
    cat = CAT.get(cat_key, "")
    city = biz.get("town") or find_city(data.get("body", ""))
    place = city or PROV.get(biz.get("province", ""), "")
    phone = biz.get("phone") or (data["tel"][0] if data["tel"] else "")
    services = pick_services(data, biz["business"])
    lead = ""
    for h in data["h1"] + [data["desc"] or ""]:
        h = re.sub(r"^(about us|welcome|home)\s*[:\-–]?\s*", "", clean(h, 170), flags=re.I)
        if 25 <= len(h) <= 170 and sentencey(h) and biz["business"].lower() not in h.lower()[:len(biz["business"])+2] and not re.match(r"^(welcome|home)", h, re.I):
            lead = h; break
    if not lead:
        pts0 = find_points(data, biz["business"]); lead = pts0[0] if pts0 else (f"{cat} in {place}." if cat and place else "")
    if re.search(r"\b(has retired|have retired|permanently closed|closed permanently|no longer (?:in business|operating|open)|we have closed|ceased operations|out of business|thank you for \d+ years)\b", data.get("body", ""), re.I):
        raise RuntimeError("SKIP business looks closed or retired")
    if len(services) < 3:
        raise RuntimeError(f"SKIP could not find their services ({len(services)} found)")
    c = {"name": biz["business"], "email": biz.get("email", ""), "phone": phone, "place": place, "logo": logo,
         "photos": photos, "stock": stock_for(cat_key, out),
         "kicker": " · ".join(x for x in [cat, place] if x), "lead": lead,
         "svc_title": f"{cat} you can count on" if cat and not cat.endswith("s") else "What we do",
         "services": services, "points": [p for p in find_points(data, biz["business"]) if p != lead][:3],
         "about": pick_about(data, biz["business"]), "since": find_since(data.get("body", "")),
         "hours": find_hours(data.get("body", "")), "theme": theme(brand, accent, seed)}
    if c["svc_title"] != "What we do": c["svc_title"] = "What we do"
    import design
    doc, layout, font = design.render(c, seed)
    open(os.path.join(out, "index.html"), "w").write(doc)
    fonts = (None, None, font)
    # render concept
    ctx = browser.new_context(viewport={"width": 1440, "height": 900}, device_scale_factor=1.25)
    p = ctx.new_page(); p.goto("file://" + os.path.join(out, "index.html"), wait_until="networkidle"); p.wait_for_timeout(500)
    p.screenshot(path=os.path.join(out, "_desk.png")); p.screenshot(path=os.path.join(out, "_full.png"), full_page=True); ctx.close()
    ctx = browser.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2, is_mobile=True)
    p = ctx.new_page(); p.goto("file://" + os.path.join(out, "index.html"), wait_until="networkidle"); p.wait_for_timeout(400)
    p.screenshot(path=os.path.join(out, "_mob.png")); ctx.close()
    subprocess.run([sys.executable, os.path.join(ROOT, "tools/device_frame.py"), "--before", os.path.join(out, "_before.png"),
                    os.path.join(out, "_desk.png"), os.path.join(out, "_mob.png"), os.path.join(out, "before-after.jpg")],
                   check=True, capture_output=True)
    im = Image.open(os.path.join(out, "_full.png")).convert("RGB"); im.thumbnail((1200, 9999)); im.save(os.path.join(out, "full-page.jpg"), quality=78)
    ba = Image.open(os.path.join(out, "before-after.jpg")); ba.thumbnail((1200, 1200)); ba.save(os.path.join(out, "before-after.jpg"), quality=82)
    for f in os.listdir(out):
        if f.startswith("_") and f != "_before.png": os.remove(os.path.join(out, f))
    Image.open(os.path.join(out, "_before.png")).convert("RGB").save(os.path.join(out, "_before.jpg"), quality=70); os.remove(os.path.join(out, "_before.png"))
    return {"slug": slug, "layout": layout, "font": fonts[2], "photos": len(photos), "logo": bool(logo),
            "services": len(c["services"]), "about": bool(c["about"]), "headline": c["lead"], "since": c["since"], "hours": len(c["hours"]), "city": c["place"],
            "preview_url": f"{BASE_URL}/{slug}/", "mockup_url": f"{BASE_URL}/{slug}/before-after.jpg"}

def run(rows, workers):
    results = []
    def one(chunk):
        out = []
        with sync_playwright() as pw:
            px = os.environ.get('HTTPS_PROXY') or os.environ.get('https_proxy')
            b = pw.chromium.launch(proxy={'server': px} if px and not os.environ.get('GITHUB_ACTIONS') else None)
            for biz in chunk:
                t = time.time()
                try:
                    r = build(biz, b); r["ok"] = True
                except Exception as ex:
                    r = {"ok": False, "error": str(ex)[:160]}
                r["osm_id"] = biz.get("osm_id"); r["business"] = biz["business"]
                log(f"{'OK ' if r['ok'] else 'ERR'} {biz['business'][:40]:40} {round(time.time()-t)}s {r.get('layout','')} {r.get('error','')}")
                out.append(r)
            b.close()
        return out
    chunks = [rows[i::workers] for i in range(workers)]
    with ThreadPoolExecutor(workers) as ex:
        for res in ex.map(one, chunks): results += res
    return results

def sheet_env():
    cl = lambda v: (v or "").strip().strip('"').strip("'").strip()
    url, tok = cl(os.environ.get("SHEET_URL")), cl(os.environ.get("SHEET_TOKEN"))
    m = re.search(r"https://script\.google\.com/macros/s/[A-Za-z0-9_-]+/exec", url)
    return (m.group(0) if m else url), tok

def sheet_rows(limit):
    url, tok = sheet_env()
    r = requests.get(url, params={"token": tok, "status": "new", "limit": limit}, timeout=120).json()
    if not r.get("ok"): raise SystemExit("sheet read failed: " + str(r))
    return [{k: ("" if v is None else str(v)) for k, v in row.items()} for row in r["rows"]]

def sheet_update(results):
    url, tok = sheet_env(); ups = []
    for r in results:
        if r["ok"]: ups.append({"osm_id": r["osm_id"], "status": "mockup ready", "preview_url": r["preview_url"], "mockup_url": r["mockup_url"]})
        elif str(r.get("error", "")).startswith("SKIP") or "ERR_NAME_NOT_RESOLVED" in str(r.get("error", "")):
            ups.append({"osm_id": r["osm_id"], "status": "skip"})
    for i in range(0, len(ups), 100):
        res = requests.post(url, data=json.dumps({"token": tok, "action": "update", "updates": ups[i:i + 100]}),
                            headers={"Content-Type": "application/json"}, timeout=180)
        log("sheet update:", res.text[:120])

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv"); ap.add_argument("--sheet", action="store_true")
    ap.add_argument("--limit", type=int, default=0); ap.add_argument("--workers", type=int, default=3)
    a = ap.parse_args()
    rows = sheet_rows(a.limit or 100) if a.sheet else list(csv.DictReader(open(a.csv)))
    if a.limit: rows = rows[:a.limit]
    log(f"building {len(rows)} mockups")
    res = run(rows, a.workers)
    if a.sheet: sheet_update(res)
    ok = sum(r["ok"] for r in res)
    log(f"done: {ok}/{len(res)} built, {sum(1 for r in res if not r['ok'] and str(r.get('error','')).startswith('SKIP'))} skipped (not enough real content)")
