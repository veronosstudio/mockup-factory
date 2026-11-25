"""
Veronos automatic homepage builder.

  python builder/build_homepage.py https://their-site.com [slug=their-business] [niche=dental] [publish=yes]

1. Reads their website (home + about/services/contact pages).
2. Pulls their own content: name, logo, brand colour, phone, email, addresses, hours,
   services, the owner/practitioner and their bio, and any usable photos.
3. Fills templates/site with it and builds the page at /<slug>/.
4. Writes docs/<slug>/ (the page) and builder/out/<slug>/review.md (what to check before sending).

Never invents content: services, staff, reviews, prices and awards only come from their site.
When their site has no usable photo, the hero is a free-licensed photo of their city (credited).
"""
import asyncio, colorsys, io, json, os, re, shutil, subprocess, sys, urllib.parse
from collections import Counter

if os.path.isdir("/opt/pw-browsers"): os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", "/opt/pw-browsers")
from playwright.async_api import async_playwright
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATE = os.path.join(ROOT, "templates", "site")

DAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
DAY_RX = r"(?:mon|tue|tues|wed|thu|thur|thurs|fri|sat|sun)(?:day|sday|nesday|rsday|urday)?\.?"
HOURS_RX = re.compile(
    rf"^\s*({DAY_RX}(?:\s*(?:-|–|—|to|&|,|and)\s*{DAY_RX})*)\s*[:\-–—]?\s*"
    r"((?:closed|by appointment|\d{1,2}(?::\d{2})?\s*(?:a\.?m\.?|p\.?m\.?)?\s*(?:-|–|—|to)\s*\d{1,2}(?::\d{2})?\s*(?:a\.?m\.?|p\.?m\.?)?).*)$",
    re.I)
CA_POST = re.compile(r"\b([A-Z]\d[A-Z])\s?(\d[A-Z]\d)\b")
US_ZIP = re.compile(r"\b(A[LKZR]|C[AOT]|D[EC]|FL|GA|HI|I[DLNA]|K[SY]|LA|M[EDAINSOT]|N[EVHJMYCD]|O[HKR]|PA|RI|S[CD]|T[NX]|UT|V[TA]|W[AVIY])\s+(\d{5})(?:-\d{4})?\b")
PROV = r"(?:AB|BC|MB|NB|NL|NS|NT|NU|ON|PE|QC|SK|YT|Alberta|British Columbia|Manitoba|Ontario|Saskatchewan|Quebec|Nova Scotia|New Brunswick)"
PAGE_WORDS = re.compile(r"about|team|staff|meet|doctor|dentist|denturist|lawyer|attorney|service|treatment|what-we-do|practice|contact|location|hours|visit|our-", re.I)
NAV_WORDS = {"home", "about", "about us", "services", "contact", "contact us", "blog", "news", "faq", "faqs", "book now",
             "book online", "menu", "careers", "gallery", "reviews", "testimonials", "privacy policy", "terms", "login",
             "sitemap", "read more", "learn more", "location", "locations", "our team", "team", "click here", "call now"}

ROLE_WORDS = {"denturist", "dentist", "dentists", "owner", "lawyer", "lawyers", "staff", "our staff", "doctor", "doctors", "hygienist", "team", "meet the team", "our doctors"}
STOCK_RX = re.compile(r"unsplash|shutterstock|istock|pexels|gettyimages|depositphotos|adobestock|stock|wixstatic\.com/media/(11062b_|nsplsh_)|/themes?/|theme-|placeholder|default", re.I)

NICHES = {
    "denture": dict(match=r"denture|denturist", headline="Dentures made comfortable.", role="Denturist",
                    services="Everything for your dentures, in one place", person="Meet your denturist",
                    secondary="See our services", short="Book now", reviews="patients"),
    "dental": dict(match=r"dental|dentist|dentistry|orthodont", headline="Dental care in {city}.", role="Dentist",
                   services="Care for every smile", person="Meet your dentist",
                   secondary="See our services", short="Book now", reviews="patients"),
    "health": dict(match=r"chiropract|physiotherap|physical therap|massage therap|naturopath|optometr|clinic", headline="Feel better, close to home.",
                   role="", services="How we can help", person="Meet the team",
                   secondary="See our services", short="Book now", reviews="patients"),
    "law": dict(match=r"\blaw\b|lawyer|attorney|legal|barrister|solicitor|notary", headline="Clear legal help in {city}.", role="Lawyer",
                services="Practice areas", person="Meet your lawyer",
                secondary="See practice areas", short="Free consult", reviews="clients"),
    "trades": dict(match=r"plumb|hvac|furnace|heating|roof|electric|contractor|renovat|landscap|concrete|paving|garage door|windows|siding|painting",
                   headline="Local {trade} you can count on.", role="Owner", services="What we do",
                   person="Meet the owner", secondary="See our services", short="Get a quote", reviews="customers"),
    "auto": dict(match=r"auto|mechanic|tire|collision|car repair|transmission|detailing", headline="Honest auto service in {city}.",
                 role="Owner", services="What we do", person="Meet the owner",
                 secondary="See our services", short="Book service", reviews="customers"),
    "salon": dict(match=r"salon|hair|barber|spa\b|nails|lash|esthetic", headline="Look and feel your best.",
                  role="Owner", services="Services", person="Meet the owner",
                  secondary="See our services", short="Book now", reviews="clients"),
    "generic": dict(match=r".", headline="{name}", role="Owner", services="What we do", person="Meet the owner",
                    secondary="See what we do", short="Contact us", reviews="customers"),
}

PAGE_JS = r"""() => {
  const vis = e => { const r = e.getBoundingClientRect(); const s = getComputedStyle(e); return s.display !== 'none' && s.visibility !== 'hidden' && (r.width > 0 || r.height > 0); };
  const inChrome = e => !!e.closest('nav, footer, [role=navigation], .nav, .menu, .footer, #footer');
  const inHeader = e => !!e.closest('header, .header, #header, [class*=header], [class*=logo], [id*=logo]');
  const imgs = [...document.images].filter(vis).map(i => ({src: i.currentSrc || i.src, w: i.naturalWidth, h: i.naturalHeight, alt: i.alt || '', cls: (i.className || '') + ' ' + (i.id || '') + ' ' + ((i.closest('a') || {}).className || ''), header: inHeader(i), top: i.getBoundingClientRect().top + scrollY}));
  const bgs = [];
  for (const e of document.querySelectorAll('section, div, header, main, figure, a, span')) {
    const b = getComputedStyle(e).backgroundImage; if (!b || !b.startsWith('url(')) continue;
    const r = e.getBoundingClientRect(); const m = b.match(/url\(["']?([^"')]+)/); if (m) bgs.push({src: new URL(m[1], location.href).href, ew: r.width, eh: r.height, top: r.top + scrollY});
  }
  const heads = [...document.querySelectorAll('h1,h2,h3,h4')].filter(h => vis(h) && !inChrome(h)).map(h => {
    let n = h.nextElementSibling, t = ''; for (let k = 0; n && k < 3 && !t; k++, n = n.nextElementSibling) { if (/^H[1-4]$/.test(n.tagName)) break; const x = (n.innerText || '').trim(); if (x.length > 30) t = x; }
    return {tag: h.tagName, text: h.innerText.trim(), next: t.slice(0, 600)};
  });
  const lis = [...document.querySelectorAll('li')].filter(l => vis(l) && !inChrome(l) && !l.querySelector('ul,ol')).map(l => l.innerText.trim()).filter(t => t && t.length < 90);
  const paras = [...document.querySelectorAll('p, .paragraph, [class*=text] > div')].filter(p => vis(p) && !inChrome(p)).map(p => p.innerText.trim()).filter(t => t.length > 60);
  const links = [...document.querySelectorAll('a[href]')].map(a => ({text: a.innerText.trim().slice(0, 60), href: a.href}));
  const ld = [...document.querySelectorAll('script[type="application/ld+json"]')].map(s => s.textContent);
  const colors = {};
  const add = (c, w) => { if (c && c !== 'rgba(0, 0, 0, 0)' && c !== 'transparent') colors[c] = (colors[c] || 0) + w; };
  for (const e of document.querySelectorAll('a.btn, .button, button, [class*=btn], [class*=button], input[type=submit]')) { if (vis(e)) { const s = getComputedStyle(e); add(s.backgroundColor, 4); add(s.borderColor, 1); } }
  for (const e of document.querySelectorAll('header, nav, .header, footer')) { if (vis(e)) add(getComputedStyle(e).backgroundColor, 3); }
  for (const e of document.querySelectorAll('a, h1, h2, h3')) { if (vis(e) && !inChrome(e)) add(getComputedStyle(e).color, 1); }
  for (const e of document.querySelectorAll('section, div')) { const r = e.getBoundingClientRect(); if (r.width > 900 && r.height > 150) add(getComputedStyle(e).backgroundColor, 2); }
  const meta = n => (document.querySelector(`meta[name="${n}"], meta[property="${n}"]`) || {}).content || '';
  return {url: location.href, title: document.title, desc: meta('description') || meta('og:description'), site: meta('og:site_name'),
          theme: meta('theme-color'), text: document.body.innerText, imgs, bgs, heads, lis, paras, links, ld, colors};
}"""


# ---------------------------------------------------------------- crawl
async def crawl(url, shots_dir):
    pages = []
    async with async_playwright() as p:
        b = await p.chromium.launch()
        ctx = await b.new_context(viewport={"width": 1366, "height": 900}, user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0 Safari/537.36")
        pg = await ctx.new_page()

        async def visit(u):
            try:
                r = await pg.goto(u, wait_until="networkidle", timeout=40000)
            except Exception:
                try:
                    r = await pg.goto(u, wait_until="load", timeout=40000)
                except Exception as e:
                    print("  skip", u, str(e)[:80]); return None
            if r and r.status >= 400:
                print("  skip", u, r.status); return None
            await pg.evaluate("async()=>{for(let y=0;y<document.body.scrollHeight;y+=700){scrollTo(0,y);await new Promise(r=>setTimeout(r,60))}scrollTo(0,0)}")
            await pg.wait_for_timeout(400)
            d = await pg.evaluate(PAGE_JS)
            print("  read", d["url"], f'{len(d["text"])} chars')
            return d

        home = await visit(url)
        if not home:
            raise SystemExit("Could not open " + url)
        os.makedirs(shots_dir, exist_ok=True)
        await pg.screenshot(path=os.path.join(shots_dir, "their-site.png"), full_page=False)
        pages.append(home)
        host = urllib.parse.urlparse(home["url"]).netloc.replace("www.", "")
        norm = lambda u: re.sub(r"^https?://(www\.)?", "", u.split("#")[0]).rstrip("/")
        seen = {norm(home["url"])}
        cands = []
        for l in home["links"]:
            h = l["href"].split("#")[0].rstrip("/")
            pu = urllib.parse.urlparse(h)
            if pu.netloc.replace("www.", "") != host or norm(h) in seen or re.search(r"\.(pdf|jpg|png|zip)$|/blog/|/news/|/category/|/tag/|\?", h, re.I):
                continue
            if PAGE_WORDS.search(pu.path) or PAGE_WORDS.search(l["text"]):
                seen.add(norm(h)); cands.append(h)
        for h in cands[:6]:
            d = await visit(h)
            if d:
                pages.append(d)
        await b.close()
    return pages


# ---------------------------------------------------------------- helpers
def clean(t):
    return re.sub(r"[​ ]+", " ", re.sub(r"[ \t]+", " ", t or "")).strip()


def sentences(t, limit):
    t = clean(t).replace("\n", " ")
    out = ""
    for s in re.split(r"(?<=[.!?])\s+", t):
        if len(out) + len(s) > limit and out:
            break
        out = (out + " " + s).strip()
    return out if len(out) <= limit + 40 else out[:limit].rsplit(" ", 1)[0] + "…"


def ld_objects(pages):
    out = []
    def walk(o):
        if isinstance(o, list):
            for x in o: walk(x)
        elif isinstance(o, dict):
            out.append(o)
            for k in ("@graph", "location", "department", "subOrganization"):
                if k in o: walk(o[k])
    for p in pages:
        for raw in p["ld"]:
            try: walk(json.loads(raw))
            except Exception: pass
    return out


def rgb_of(css):
    m = re.match(r"rgba?\((\d+),\s*(\d+),\s*(\d+)(?:,\s*([\d.]+))?", css or "")
    if m:
        if m.group(4) is not None and float(m.group(4)) < 0.5: return None
        return tuple(int(m.group(i)) for i in (1, 2, 3))
    m = re.match(r"#([0-9a-f]{6})$", (css or "").strip(), re.I)
    return tuple(int(m.group(1)[i:i + 2], 16) for i in (0, 2, 4)) if m else None


def lum(c):
    def ch(v):
        v /= 255; return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    r, g, b = c; return 0.2126 * ch(r) + 0.7152 * ch(g) + 0.0722 * ch(b)


def contrast(a, b):
    la, lb = sorted([lum(a), lum(b)], reverse=True); return (la + 0.05) / (lb + 0.05)


def hexc(c): return "#%02X%02X%02X" % tuple(max(0, min(255, int(round(v)))) for v in c)


def with_l(c, l, s=None):
    h, _, s0 = colorsys.rgb_to_hls(*[v / 255 for v in c])
    return tuple(v * 255 for v in colorsys.hls_to_rgb(h, l, s0 if s is None else s))


def saturated(c):
    h, l, s = colorsys.rgb_to_hls(*[v / 255 for v in c]); return s > 0.28 and 0.12 < l < 0.85


def palette(base):
    """primary (dark brand), accent (button colour with white text >= 4.5:1), dark (section bg)."""
    h, l, s = colorsys.rgb_to_hls(*[v / 255 for v in base])
    s = max(0.45, min(s, 0.85))
    accent = with_l(base, min(l, 0.42), s)
    while contrast(accent, (255, 255, 255)) < 4.6:
        accent = with_l(accent, colorsys.rgb_to_hls(*[v / 255 for v in accent])[1] - 0.03)
    primary = with_l(base, 0.22, min(s, 0.7))
    dark = with_l(base, 0.12, min(s, 0.6))
    return dict(primary=hexc(primary), primaryLight=hexc(accent), accent=hexc(accent), dark=hexc(dark))


# ---------------------------------------------------------------- extract
def extract(pages, url, niche_arg=None):
    home = pages[0]
    alltext = "\n".join(p["text"] for p in pages)
    lds = ld_objects(pages)
    biz = next((o for o in lds if re.search(r"Business|Dentist|Medical|Physician|Attorney|Legal|Store|Clinic|Organization|Contractor|Plumber|Electrician|Roofing|AutoRepair|Salon|Spa", str(o.get("@type", "")))), {})
    notes = []

    # name
    name = clean(biz.get("name") or home["site"] or "")
    parts = [clean(x) for x in re.split(r"\s+[|\-–—:•]\s+", home["title"]) if clean(x)]
    parts = [x for x in parts if x.lower() not in ("home", "homepage", "welcome", "about", "about us", "contact", "contact us")]
    droot = re.sub(r"[^a-z0-9]", "", urllib.parse.urlparse(url).netloc.lower().replace("www.", "").rsplit(".", 1)[0])
    if not name:
        compact = lambda x: re.sub(r"[^a-z0-9]", "", x.lower())
        match = [x for x in parts if compact(x) and (compact(x) in droot or droot in compact(x) or compact(x)[:6] == droot[:6])]
        name = (match or [x for x in parts if len(x.split()) <= 5] or [droot.title()])[0]
    name = re.sub(r"^(welcome to|home)\s*[-|:]?\s*", "", name, flags=re.I)
    descriptor = next((x for x in parts if x != name and len(x.split()) >= 2 and len(x) <= 50 and not CA_POST.search(x)), "")

    # niche
    blob = (home["title"] + " " + home["desc"] + " " + alltext[:6000]).lower()
    niche = niche_arg or next((k for k, v in NICHES.items() if k != "generic" and re.search(v["match"], blob)), "generic")
    N = NICHES[niche]

    # phone / email
    phone = ""
    for p in pages:
        for l in p["links"]:
            if l["href"].startswith("tel:"):
                phone = phone or re.sub(r"[^\d+]", "", urllib.parse.unquote(l["href"][4:]))
    phone = phone or re.sub(r"[^\d+]", "", str(biz.get("telephone", "")))
    if not phone:
        m = re.search(r"\(?\b(\d{3})\)?[\s.\-]?(\d{3})[\s.\-](\d{4})\b", alltext)
        phone = "".join(m.groups()) if m else ""
    digits = re.sub(r"\D", "", phone)[-10:]
    phone_disp = f"{digits[:3]}-{digits[3:6]}-{digits[6:]}" if len(digits) == 10 else phone
    host = urllib.parse.urlparse(home["url"]).netloc.replace("www.", "")
    email = ""
    for p in pages:
        for l in p["links"]:
            if l["href"].lower().startswith("mailto:"):
                e = urllib.parse.unquote(l["href"][7:].split("?")[0]).strip().lower()
                if not email or e.endswith("@" + host): email = e
    if not email:
        m = re.search(r"[\w.+-]+@" + re.escape(host), alltext, re.I)
        email = m.group(0).lower() if m else ""

    # locations + hours (text order: address block, then the hours after it)
    locs, cur, loose_hours = {}, None, []
    for p in pages:
        lines = [clean(x) for x in p["text"].split("\n")]
        lines = [x for x in lines if x]
        for i, line in enumerate(lines):
            post = CA_POST.search(line) or US_ZIP.search(line)
            if post and len(line) < 160:
                key = post.group(0).replace(" ", "").upper()
                if re.search(r"\d+\s+\w+", line.split(",")[0]) and "," in line:
                    segs = [s.strip() for s in line.split(",")]
                    street = segs[0]; rest = ", ".join(segs[1:])
                    street = re.sub(r"^(address|location|office)\s*:\s*", "", street, flags=re.I)
                else:
                    prev = lines[i - 1] if i else ""
                    street = prev if re.search(r"\d", prev) and len(prev) < 80 and not HOURS_RX.match(prev) else ""
                    street = re.sub(r"^(address|location|office)\s*:\s*", "", street, flags=re.I)
                    rest = line
                cm = re.search(r"([A-Za-z .'\-]+?),?\s+" + PROV + r"\b", rest, re.I) or re.search(r"([A-Za-z .'\-]+?),\s*[A-Z]{2}\s+\d{5}", rest)
                city = clean(cm.group(1)) if cm else ""
                if key not in locs:
                    locs[key] = dict(name=city or "Our location", address=[a for a in [street, rest] if a], city=city, hours=[])
                cur = locs[key]
                continue
            m = HOURS_RX.match(line)
            if m and len(line) < 70:
                pair = [clean(m.group(1)).title(), clean(m.group(2)).replace(" - ", " – ")]
                tgt = cur["hours"] if cur else loose_hours
                if pair not in tgt: tgt.append(pair)
            elif cur and re.match(r"^(copyright|©)", line, re.I):
                cur = None
        cur = None
    if not locs and isinstance(biz.get("address"), dict):
        a = biz["address"]
        street, city = a.get("streetAddress", ""), a.get("addressLocality", "")
        locs["ld"] = dict(name=city or "Our location", city=city, hours=[],
                          address=[x for x in [street, f'{city}, {a.get("addressRegion", "")} {a.get("postalCode", "")}'.strip(", ")] if x])
    locations = list(locs.values())[:3]
    if locations and not any(l["hours"] for l in locations) and loose_hours:
        locations[0]["hours"] = loose_hours[:8]
    for l in locations:
        l["hours"] = l["hours"][:8]
        l["map"] = "https://www.google.com/maps/search/?api=1&query=" + urllib.parse.quote_plus(" ".join(l["address"]))
        l.pop("city", None)
    city = next((l["name"] for l in locations if l["name"] != "Our location"), "")
    if len({l["name"] for l in locations}) < len(locations):
        for i, l in enumerate(locations): l["name"] = l["address"][0] if l["address"] else f"Location {i + 1}"

    # services
    svc_pages = [p for p in pages if re.search(r"servic|treatment|what-we-do|practice|procedure", p["url"] + " " + p["title"], re.I)]
    services, seenk = [], set()
    def add_svc(title, text=""):
        t = clean(title).strip("•-–:· ")
        k = t.lower()
        if not (3 <= len(t) <= 60) or k in NAV_WORDS or k in ROLE_WORDS or k in seenk or re.search(r"\d{3}.\d{3}.\d{4}|@|copyright|©|http|call us|follow us|cookie", k):
            return
        if len(t.split()) > 8 or t.endswith((".", "?", "!")) and len(t.split()) > 5:
            return
        seenk.add(k); services.append({"title": t[0].upper() + t[1:], "text": sentences(text, 170) if text else ""})
    for p in svc_pages:
        for li in p["lis"]:
            add_svc(li)
    for p in (svc_pages if len(services) < 3 else []):
        for h in p["heads"]:
            if h["tag"] in ("H2", "H3", "H4") and not re.search(r"our services|services|welcome|contact|hours|location|testimonial|review|about|faq|why choose", h["text"], re.I):
                add_svc(h["text"], h["next"])
    if len(services) < 3:
        for h in home["heads"]:
            if re.search(r"special|service|treatment|what we do|we offer|practice area", h["text"], re.I):
                for li in home["lis"]: add_svc(li)
    if len(services) < 3:
        skip = NAV_WORDS | {"equipment", "materials", "past projects", "projects", "portfolio", "showroom", "care & maintenance", "sitemap",
                            "financing", "specials", "promotions", "shop", "store", "cart", "account", "my account", "resources", "links",
                            "patient forms", "new patients", "forms", "insurance", "testimonials", "our work", "photos", "videos", "events", "home page"}
        menu = []
        for l in home["links"]:
            t = clean(l["text"]); h = l["href"]
            if not t or "\n" in t or t.lower() in skip or t.lower() in ROLE_WORDS or len(t) > 40: continue
            if urllib.parse.urlparse(h).netloc.replace("www.", "") != host or h.startswith(("tel:", "mailto:")): continue
            if t not in menu: menu.append(t)
        if len(menu) >= 3:
            for t in menu[:8]: add_svc(t)
            notes.append("Services list came from their website menu; check it.")
    if len(services) < 3:
        notes.append("Found fewer than 3 services on their site; check the services list.")
    services = services[:8]

    # person
    person = None
    cnt = Counter()
    role_word = ""
    for m in re.finditer(r"\b(Dr\.?\s+[A-Z][a-zA-Z'\-]+(?:\s+[A-Z][a-zA-Z'\-]+)?)", alltext):
        cnt[re.sub(r"^Dr\.?\s+", "Dr. ", m.group(1))] += 2
    for m in re.finditer(r"\b(Denturist|Dentist|Owner|Founder|Lawyer|Attorney|Principal|Chiropractor|Physiotherapist|President)\b\s*[:,\-–]?\s*([A-Z][a-z]+\s+[A-Z][a-zA-Z'\-]{2,})", alltext):
        cnt[m.group(2)] += 3; role_word = role_word or m.group(1)
    for m in re.finditer(r"\b(?:Meet|About)\s+(?:Our\s+\w+\s*[:\-–]?\s*)?([A-Z][a-z]+\s+[A-Z][a-zA-Z'\-]{2,})", alltext):
        cnt[m.group(1)] += 2
    bad = re.compile(r"Denture Clinic|Dental|Clinic|Centre|Center|Services|Location|Office|Street|Avenue|Road|Highway|Business|Bureau|Association|Google|Facebook|Monday|Tuesday|Our Team|The Team", re.I)
    for nm, c in cnt.most_common():
        if bad.search(nm) or nm.lower() in name.lower():
            continue
        last = nm.split()[-1]
        paras = []
        for p in pages:
            for para in p["paras"] + [h["next"] for h in p["heads"]]:
                if (nm in para or (last in para and len(last) > 3)) and len(para) > 80 and not any(para[:80] in x or x[:80] in para for x in paras):
                    paras.append(para)
        if c >= 2 and paras:
            title = "Dentist" if nm.startswith("Dr.") and niche in ("dental",) else (role_word or N["role"])
            person = dict(heading=N["person"], name=nm, title=title, photo="",
                          bio=[sentences(x, 330) for x in paras[:2]], creds=[])
            notes.append(f"Person: picked {nm} ({title}) from their site; confirm the name and role.")
            break

    # intro, years
    intro = ""
    if 60 <= len(clean(home["desc"])) <= 260 and not re.search(r"welcome to|home page|(\.\.\.|…)\s*$", home["desc"], re.I):
        intro = clean(home["desc"])
    if not intro:
        long = [x for x in home["paras"] + [h["next"] for h in home["heads"]] if len(x) > 100]
        if not long:
            long = [x for p in pages[1:] for x in p["paras"] if len(x) > 100]
        intro = sentences(long[0], 230) if long else ""
    intro = sentences(intro, 240)
    others = [x for x in home["paras"] + [h["next"] for h in home["heads"]] + [x for p in pages[1:] for x in p["paras"]]
              if len(x) > 90 and intro[:50] not in x and x[:50] not in intro]
    band_text = sentences(others[0], 170) if others else ""
    years = ""
    m2 = re.search(r"\b(?:since|established|est\.?|founded in|in operation[\w ]{0,20} since)\s+((?:19|20)\d\d)\b", alltext, re.I)
    if m2: years = f"Since {m2.group(1)}"
    for m in re.finditer(r"(.{0,60})\b(\d{1,2})\+?\s+years\b(.{0,40})", alltext, re.I):
        ctx = (m.group(1) + " " + m.group(3)).lower()
        if years or re.search(r"combined|staff|team|our (foremen|technicians|employees)|experience of|warranty|guarantee|old|age", ctx): continue
        if 3 <= int(m.group(2)) <= 80 and re.search(r"serv|business|in operation|been (providing|helping|in)|for (over|more than)|proudly", ctx + m.group(0).lower()):
            years = f"Over {m.group(2)} years"

    # affiliations (only explicit "member" / "association" lines)
    aff = []
    for p in pages:
        for li in p["lis"]:
            if re.search(r"association|college of|society|better business bureau|bbb|chamber of commerce|accredited", li, re.I) and len(li) < 80:
                if li not in aff: aff.append(clean(li))
    aff = aff[:4]

    trust = []
    if len(locations) > 1: trust.append(f"{len(locations)} locations: " + " & ".join(l["name"] for l in locations[:2]))
    elif city: trust.append(f"Local to {city}")
    if years: trust.append(("In business since " + years[6:]) if years.startswith("Since") else years + " in business")
    if re.search(r"locally owned|family[- ]owned", alltext, re.I): trust.append(re.search(r"locally owned|family[- ]owned", alltext, re.I).group(0).capitalize())
    if re.search(r"home visit|in-home|house call|mobile service|we come to you", alltext, re.I): trust.append("We come to you")
    if re.search(r"direct bill", alltext, re.I): trust.append("Direct billing")
    if re.search(r"emergenc", alltext, re.I): trust.append("Emergency appointments")
    if re.search(r"free (estimate|quote|consult)", alltext, re.I): trust.append("Free " + re.search(r"free (estimate|quote|consult\w*)", alltext, re.I).group(1).lower())
    if re.search(r"evening|weekend|saturday", alltext, re.I) and any("sat" in h[0].lower() and "closed" not in h[1].lower() for l in locations for h in l["hours"]):
        trust.append("Open Saturdays")
    if any("bbb" in a.lower() or "better business" in a.lower() for a in aff): trust.append("BBB accredited")
    trust = trust[:4]

    trade = ""
    if niche == "trades":
        tm = re.search(r"(plumb\w*|hvac|furnace|heating|roofing|electrical|electrician\w*|landscap\w*|concrete|painting|renovation\w*)", blob)
        trade = {"plumb": "plumbing", "electrician": "electricians"}.get(tm.group(1)[:5] if tm else "", tm.group(1) if tm else "service")
    fmt = dict(city=city or "your area", name=name, trade=trade)
    headline = N["headline"].format(**fmt)
    if niche in ("trades", "generic", "auto") and descriptor and not re.search(re.escape(city), descriptor, re.I) if city else False:
        headline = f"{descriptor} in {city}." if city else descriptor
    if "{city}" in N["headline"] and not city:
        headline = NICHES["generic"]["headline"].format(**fmt)
        notes.append("No city found; headline falls back to the business name.")

    site = dict(
        name=name, title=f"{name}" + (f" | {city}" if city else ""), metaDescription=sentences(intro, 155),
        banner=f"Homepage concept made for {name} by Veronos Studio",
        eyebrow=" · ".join(x for x in [" & ".join(l["name"] for l in locations[:2]) if len(locations) > 1 else city, years] if x),
        headline=headline, intro=intro, secondaryCta=N["secondary"], ctaShort=N["short"],
        trust=trust, servicesHeading=N["services"], servicesIntro="", services=services,
        person=person, stepsHeading="", steps=[],
        reviewsSlot=f"Your Google reviews go here once the site goes live.", reviewsHeading=f"What {N['reviews']} say",
        visitHeading=("Two locations, one phone number" if len(locations) == 2 else ("Visit us" if locations else "Get in touch")),
        visitIntro=f"Call {phone_disp} to book." if phone_disp else "",
        phone=phone_disp, phoneTel=digits and ("+1" + digits) or phone, email=email,
        locations=locations, affiliations=aff, niche=niche, city=city, url=home["url"], _band_text=band_text,
    )
    if not phone_disp: notes.append("No phone number found; add one before sending.")
    if not intro: notes.append("No intro sentence found on their site; write one.")
    if not locations: notes.append("No address found; the visit section shows phone/email only.")
    if locations and not any(l["hours"] for l in locations): notes.append("No hours found on their site.")
    return site, notes


# ---------------------------------------------------------------- images & colour
async def images_and_colour(pages, site, work, notes):
    os.makedirs(work, exist_ok=True)
    home = pages[0]
    imgs = [i for p in pages for i in p["imgs"]]
    # logo: header image or anything called logo; prefer the biggest
    droot = re.sub(r"[^a-z0-9]", "", urllib.parse.urlparse(home["url"]).netloc.lower().replace("www.", "").rsplit(".", 1)[0])
    nameword = re.sub(r"[^a-z0-9]", "", site["name"].lower())[:6]
    def own_logo(i):
        t = re.sub(r"[^a-z0-9]", "", (i["src"].rsplit("/", 1)[-1] + i["alt"]).lower())
        return (droot[:6] and droot[:6] in t) or (nameword and nameword in t)
    logos = [i for i in imgs if i["w"] >= 60 and i["h"] >= 20 and i["w"] / max(i["h"], 1) < 5 and i["top"] < 400
             and (own_logo(i) or (re.search(r"logo", i["src"] + i["alt"] + i["cls"], re.I) and not re.search(r"partner|supplier|brand|client|member|badge|award|bbb|cert", i["src"] + i["alt"] + i["cls"], re.I)))]
    logos.sort(key=lambda i: (not own_logo(i), i["top"], -i["w"] * i["h"]))
    photos = []
    seen = set()
    for i in imgs:
        if i["src"] in seen or re.search(r"logo|icon|badge|bbb|seal|award|sprite|avatar|map|facebook|google|instagram|svg", i["src"] + i["alt"], re.I): continue
        if i["w"] >= 900 and i["h"] >= 450: seen.add(i["src"]); photos.append(dict(src=i["src"], w=i["w"], h=i["h"], alt=i["alt"]))
    for p in pages:
        for b in p["bgs"]:
            if b["src"] in seen or re.search(r"logo|icon|pattern|texture|svg|overlay|gradient", b["src"], re.I): continue
            if b["ew"] >= 900 and b["eh"] >= 250: seen.add(b["src"]); photos.append(dict(src=b["src"], w=0, h=0, alt=""))

    async with async_playwright() as p:
        b = await p.chromium.launch(); rq = (await b.new_context()).request

        async def fetch(u):
            try:
                r = await rq.get(u, timeout=30000)
                return await r.body() if r.ok else None
            except Exception:
                return None

        site["logo"] = ""
        for lg in logos[:3]:
            raw = await fetch(lg["src"])
            if not raw: continue
            try:
                im = Image.open(io.BytesIO(raw)).convert("RGBA")
            except Exception:
                continue
            px = [c for c in im.resize((80, max(1, int(80 * im.height / im.width)))).get_flattened_data() if c[3] > 200]
            if not px: continue
            avg = sum(lum(c[:3]) for c in px) / len(px)
            if avg > 0.8:
                notes.append("Their logo is white/light (made for a dark background); showing the name as text instead."); break
            im.thumbnail((600, 240)); im.save(os.path.join(work, "logo.png"))
            site["logo"] = "logo.png"; site["logoH"] = 44; site["logoW"] = int(44 * im.width / im.height)
            site["_logo_px"] = [c[:3] for c in px]
            break
        if not site["logo"] and logos == []:
            notes.append("No logo found; the header shows their name as text.")

        # brand colour: saturated colours in the logo first, then the site's buttons/headers
        votes = Counter()
        for c in site.pop("_logo_px", []):
            if saturated(c): votes[tuple(v // 12 * 12 for v in c)] += 3
        for p_ in pages[:3]:
            for css, w in p_["colors"].items():
                c = rgb_of(css)
                if c and saturated(c): votes[tuple(v // 12 * 12 for v in c)] += w * 4
        tc = rgb_of(home["theme"])
        if tc and saturated(tc): votes[tc] += 200
        base = votes.most_common(1)[0][0] if votes else (17, 67, 94)
        if not votes: notes.append("No clear brand colour on their site; used Veronos navy.")
        site.update(palette(base)); site["brandFrom"] = hexc(base)

        # photos: their own first
        got = []
        for ph in photos[:10]:
            raw = await fetch(ph["src"])
            if not raw: continue
            try:
                im = Image.open(io.BytesIO(raw)).convert("RGB")
            except Exception:
                continue
            if im.width < 1000 or im.height < 380 or im.width / im.height > 3.6: continue
            got.append((im.width * im.height, im, ph))
        got.sort(key=lambda x: -x[0])
        hero_mode = site.pop("_hero", "auto")
        own = [g for g in got if g[1].width >= 1400 and not (hero_mode == "auto" and STOCK_RX.search(g[2]["src"]))]
        if hero_mode == "city": own = []
        site["heroImage"] = site["heroCredit"] = ""
        if own:
            im = own[0][1]; im.thumbnail((2400, 2400)); im.save(os.path.join(work, "hero.webp"), quality=82)
            site.update(heroImage="hero.webp", heroAlt=own[0][2]["alt"] or "", heroPos="50% 40%")
            notes.append("Hero photo is from their own site; if it looks like dated stock, rebuild with hero=city for a photo of their city.")
        rest = [g for g in got if not own or g[2]["src"] != own[0][2]["src"]]
        rest.sort(key=lambda g: (g[1].width / g[1].height < 2, -g[0]))  # wide photos suit the strip
        if rest:
            im = rest[0][1]; im.thumbnail((2400, 2400)); im.save(os.path.join(work, "band.webp"), quality=82)
            site["band"] = dict(image="band.webp", alt=rest[0][2]["alt"] or "", pos="50% 35%",
                                heading=f"Visit us in {site['city']}" if site["city"] else f"Get in touch with {site['name']}",
                                text=site.get("_band_text") or (f"Call {site['phone']} to book." if site["phone"] else ""))
            notes.append("Photo strip uses a second photo from their site; check it (don't let a stock person read as their staff).")
        if not site["heroImage"] and site["city"]:
            cred = await city_photo(rq, site["city"], work)
            if cred:
                site.update(heroImage="hero.webp", heroAlt=f"{site['city']}", heroPos="50% 55%")
                site["credits"] = f"Hero photo: {cred}"
                notes.append(f"Hero is a free-licensed photo of {site['city']} ({cred}); swap for their own photo when they send one.")
        if not site["heroImage"]:
            notes.append("No hero photo found (theirs or a city photo); the hero is a plain brand-colour block.")
        await b.close()


async def city_photo(rq, city, work):
    for q in (f"{city} skyline", f"downtown {city}", f"{city}"):
        u = ("https://commons.wikimedia.org/w/api.php?action=query&format=json&generator=search&gsrnamespace=6&gsrlimit=30"
             f"&gsrsearch={urllib.parse.quote(q)}&prop=imageinfo&iiprop=url|size|extmetadata&iiurlwidth=2400")
        try:
            d = await (await rq.get(u, timeout=30000)).json()
        except Exception:
            continue
        best = []
        for v in (d.get("query") or {}).get("pages", {}).values():
            ii = (v.get("imageinfo") or [{}])[0]; m = ii.get("extmetadata", {})
            lic = (m.get("LicenseShortName") or {}).get("value", "")
            t = v.get("title", "")
            if not re.match(r"^(CC0|CC BY(-SA)? [234]\.0|Public domain)", lic): continue
            if ii.get("width", 0) < 2400 or ii.get("width", 0) / max(ii.get("height", 1), 1) < 1.3: continue
            if re.search(r"map|logo|flag|coat of arms|seal|diagram|\.svg|\.png|\.tif|night.*long exposure|crop", t, re.I): continue
            if city.split()[0].lower() not in t.lower(): continue
            score = ii["width"] * (2 if re.search(r"skyline|downtown|panorama", t, re.I) else 1)
            art = re.sub("<[^>]+>", "", (m.get("Artist") or {}).get("value", "")).strip()
            best.append((score, ii.get("thumburl"), art, lic, t))
        best.sort(reverse=True)
        for score, turl, art, lic, t in best[:3]:
            try:
                r = await rq.get(turl, timeout=60000)
                im = Image.open(io.BytesIO(await r.body())).convert("RGB")
            except Exception:
                continue
            im.thumbnail((2400, 2400)); im.save(os.path.join(work, "hero.webp"), quality=82)
            return f"{art or 'Wikimedia Commons'}, {lic}, via Wikimedia Commons"
    return ""


# ---------------------------------------------------------------- build
def build(site, work, slug, out_dir):
    data = os.path.join(TEMPLATE, "src", "data", "site.json")
    imgdir = os.path.join(TEMPLATE, "public", "img")
    shutil.rmtree(imgdir, ignore_errors=True); os.makedirs(imgdir)
    for f in os.listdir(work):
        if f.endswith((".webp", ".png", ".jpg")) and f != "their-site.png":
            shutil.copy(os.path.join(work, f), imgdir)
    json.dump(site, open(data, "w"), indent=2, ensure_ascii=False)
    env = dict(os.environ, SITE_BASE=f"/{slug}")
    shutil.rmtree(os.path.join(TEMPLATE, "dist"), ignore_errors=True)
    r = subprocess.run(["pnpm", "build"], cwd=TEMPLATE, env=env, capture_output=True, text=True)
    if r.returncode != 0:
        print(r.stdout[-3000:], r.stderr[-3000:]); raise SystemExit("build failed")
    shutil.rmtree(out_dir, ignore_errors=True)
    shutil.copytree(os.path.join(TEMPLATE, "dist"), out_dir)


def slugify(s):
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", s.lower())).strip("-")[:48]


def main():
    args = dict(a.split("=", 1) for a in sys.argv[2:] if "=" in a)
    url = sys.argv[1]
    if not url.startswith("http"): url = "https://" + url
    print("Reading", url)
    pages = asyncio.run(crawl(url, "/tmp/vb_shot"))
    site, notes = extract(pages, url, args.get("niche"))
    slug = args.get("slug") or slugify(site["name"])
    work = os.path.join(ROOT, "builder", "out", slug)
    shutil.rmtree(work, ignore_errors=True); os.makedirs(work)
    shutil.copy("/tmp/vb_shot/their-site.png", work)
    site["_hero"] = args.get("hero", "auto")
    asyncio.run(images_and_colour(pages, site, work, notes))
    site["slug"] = slug
    site.pop("_band_text", None)
    json.dump(site, open(os.path.join(work, "site.json"), "w"), indent=2, ensure_ascii=False)
    json.dump([{k: p[k] for k in ("url", "title", "desc", "text")} for p in pages], open(os.path.join(work, "raw.json"), "w"), indent=1, ensure_ascii=False)
    build(site, work, slug, os.path.join(ROOT, "docs", slug))
    link = f"https://preview.veronosstudio.com/{slug}/"
    review = [f"# {site['name']}", "", f"Their site: {site['url']}", f"New homepage: {link}", f"Niche: {site['niche']} · Brand colour from their site: {site['brandFrom']}", "",
              f"Found: {len(site['services'])} services, {len(site['locations'])} location(s), "
              f"{sum(len(l['hours']) for l in site['locations'])} hours lines, person: {(site['person'] or {}).get('name', 'none')}, "
              f"logo: {'yes' if site['logo'] else 'no'}, hero: {(site.get('credits') or '').replace('Hero photo: ', '') or ('their photo' if site['heroImage'] else 'none')}", "",
              "## Check before sending"] + [f"- {n}" for n in notes] + ["- Read the headline and intro once; they're built from their own words."]
    open(os.path.join(work, "review.md"), "w").write("\n".join(review) + "\n")
    print("\n".join(review))
    print("SLUG=" + slug)


if __name__ == "__main__":
    main()
