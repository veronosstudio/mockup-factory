"""Mockup factory v2: six premium layouts, each with its own signature element.

Everything shown comes from the business's own website (or the facts we already hold: name, town, phone, email).
The only outside material is a small no-logo stock set used for service tiles when a site has no usable photos.
"""
import html, re

E = lambda s: html.escape(s or "")

FONTS = [  # (google css families, display stack, body stack)
    ("family=Archivo+Black&family=Archivo:wght@400;500;600", "'Archivo Black'", "Archivo"),
    ("family=Fraunces:opsz,wght@9..144,500;9..144,700&family=Manrope:wght@400;500;700", "Fraunces", "Manrope"),
    ("family=Oswald:wght@500;700&family=Source+Sans+3:wght@400;600", "Oswald", "'Source Sans 3'"),
    ("family=DM+Serif+Display&family=DM+Sans:wght@400;500;700", "'DM Serif Display'", "'DM Sans'"),
    ("family=Sora:wght@600;800&family=Inter:wght@400;500;600", "Sora", "Inter"),
    ("family=Bricolage+Grotesque:opsz,wght@12..96,600;12..96,800&family=Figtree:wght@400;500;600", "'Bricolage Grotesque'", "Figtree"),
    ("family=Zilla+Slab:wght@600;700&family=Rubik:wght@400;500", "'Zilla Slab'", "Rubik"),
    ("family=Playfair+Display:wght@700;900&family=Karla:wght@400;500;700", "'Playfair Display'", "Karla"),
]
LAYOUTS = ["slab", "heritage", "mosaic", "night", "ledger", "pop"]
NEEDS_OWN_PHOTO = {"slab", "night"}

BASE = """
*{box-sizing:border-box;margin:0;padding:0}html{-webkit-text-size-adjust:100%}
body{font-family:BODY,system-ui,sans-serif;color:var(--ink);background:var(--bg);font-size:18px;line-height:1.6}
a{color:inherit;text-decoration:none}img{display:block;max-width:100%}
.d{font-family:DISP,serif;letter-spacing:-.015em;line-height:1}
.concept{background:#0d0f12;color:#a6acb6;font-size:12px;text-align:center;padding:6px 10px}
.wrap{max-width:1200px;margin:0 auto;padding:0 40px}
header .wrap{display:flex;align-items:center;gap:26px;height:88px}
.logo{max-height:58px;max-width:230px;object-fit:contain}.word{font-size:25px}
nav{margin-left:auto;display:flex;gap:26px;font-size:15px;font-weight:500;opacity:.85}
.call{padding:12px 20px;border-radius:999px;font-weight:600;font-size:15px;white-space:nowrap;background:var(--brand);color:var(--on)}
.kick{font-size:13px;letter-spacing:.16em;text-transform:uppercase;font-weight:600}
.btn{display:inline-block;padding:16px 26px;border-radius:999px;font-weight:600;font-size:16px}
.btns{display:flex;gap:12px;flex-wrap:wrap;margin-top:30px}
section{padding:100px 0}
h2.d{font-size:clamp(36px,4vw,60px);margin-bottom:14px}
.lead{font-size:19px;max-width:34em;opacity:.88}
.cta{background:var(--brand);color:var(--on);text-align:center;padding:90px 0}
.cta .big{font-size:clamp(46px,7vw,104px);margin:14px 0 10px}
footer{padding:26px 0;font-size:13px;opacity:.7}footer .wrap{display:flex;justify-content:space-between;flex-wrap:wrap;gap:10px}
.hours{display:grid;gap:2px;margin-top:20px}.hours div{display:flex;justify-content:space-between;gap:20px;padding:10px 0;border-bottom:1px solid var(--line);font-size:16px}
@media(max-width:880px){.wrap{padding:0 18px}nav{display:none}.call{margin-left:auto;padding:10px 14px;font-size:14px}header .wrap{height:70px}
 .logo{max-height:42px;max-width:150px}.word{font-size:19px}section{padding:64px 0}.g2,.g3,.g4{grid-template-columns:1fr!important}.hero-grid{grid-template-columns:1fr!important}
 .hide-m{display:none!important}}
"""

def header(c, style=""):
    logo = f'<img class="logo" src="{c["logo"]}" alt="{E(c["name"])}">' if c["logo"] else f'<span class="word d">{E(c["name"])}</span>'
    return f'<header style="{style}"><div class="wrap">{logo}<nav><a href="#">Services</a><a href="#">About</a><a href="#">Contact</a></nav><a class="call" href="#">{E(c["phone"]) or "Contact us"}</a></div></header>'

def hours_html(c):
    if not c["hours"]: return ""
    rows = "".join(f'<div><span>{E(a)}</span><b>{E(b)}</b></div>' for a, b in c["hours"][:7])
    return f'<div class="hours">{rows}</div>'

def tiles(c, n=6):
    """Service tiles: each gets a photo (their own first, then stock) when the layout wants images."""
    imgs = c["photos"][1:] + c["photos"][:1] + c["stock"]
    out = []
    for i, s in enumerate(c["services"][:n]):
        out.append((s, imgs[i % len(imgs)] if imgs else ""))
    return out

def cta(c):
    return f'''<section class="cta"><div class="wrap"><div class="kick">Call or email</div><div class="big d">{E(c["phone"]) or "Get in touch"}</div>
<p style="opacity:.85">{E(c["email"])}{" · " + E(c["place"]) if c["place"] else ""}</p></div></section>'''

def footer(c):
    return f'<footer><div class="wrap"><span>{E(c["name"])}{", " + E(c["place"]) if c["place"] else ""}</span><span>Concept design by Veronos Studio</span></div></footer>'

def points_html(c, cls):
    if not c["points"]: return ""
    return "".join(f'<div class="{cls}"><span class="d">0{i+1}</span><p>{E(p)}</p></div>' for i, p in enumerate(c["points"][:3]))

# ---------------- layouts ----------------
def slab(c):
    hero = c["photos"][0]
    since = f'<div class="badge d"><small>Since</small>{c["since"]}</div>' if c["since"] else ""
    tl = "".join(f'<div class="t"><img src="{img}" alt=""><h3 class="d">{E(s)}</h3></div>' for s, img in tiles(c, 6))
    css = """
.hero{display:grid;grid-template-columns:1fr 1fr;min-height:620px;background:var(--paper)}
.hero .l{padding:80px 60px 80px max(40px,calc((100vw - 1200px)/2 + 40px));display:flex;flex-direction:column;justify-content:center}
.hero .r{position:relative;background:url(HERO) center/cover;clip-path:polygon(14% 0,100% 0,100% 100%,0 100%)}
.hero .r:before{content:"";position:absolute;inset:0 auto 0 0;width:22%;background:var(--brand);clip-path:polygon(64% 0,100% 0,36% 100%,0 100%);opacity:.92}
.hero h1{font-size:clamp(46px,5.4vw,84px);color:var(--dark);margin:16px 0 18px}
.badge{position:absolute;right:40px;bottom:40px;width:140px;height:140px;border-radius:50%;background:var(--accent);color:var(--onacc);display:flex;flex-direction:column;align-items:center;justify-content:center;font-size:40px;box-shadow:0 20px 40px -20px #000}
.badge small{font-size:13px;letter-spacing:.14em;text-transform:uppercase}
.tg{display:grid;grid-template-columns:repeat(3,1fr);gap:20px;margin-top:40px}.t{background:#fff;border-bottom:5px solid var(--brand)}
.t img{aspect-ratio:3/2;object-fit:cover;width:100%}.t h3{font-size:24px;padding:20px 22px 24px;color:var(--dark)}
.why{background:var(--dark);color:#fff}.why .g3{display:grid;grid-template-columns:repeat(3,1fr);gap:30px;margin-top:30px}
.pt span{font-size:44px;color:var(--accent)}.pt p{margin-top:8px;opacity:.9}
@media(max-width:880px){.hero{grid-template-columns:1fr}.hero .l{padding:40px 18px}.hero .r{min-height:300px;clip-path:none}.tg{grid-template-columns:1fr}}
""".replace("HERO", hero)
    body = f'''{header(c)}
<section class="hero" style="padding:0"><div class="l"><div class="kick" style="color:var(--brand)">{E(c["kicker"])}</div>
<h1 class="d">{E(c["name"])}</h1><p class="lead">{E(c["lead"])}</p>
<div class="btns"><a class="btn" style="background:var(--brand);color:var(--on)" href="#">Get a quote</a><a class="btn" style="border:2px solid var(--dark);color:var(--dark)" href="#">{E(c["phone"]) or "Contact us"}</a></div></div>
<div class="r">{since}</div></section>
<section style="background:var(--paper2)"><div class="wrap"><div class="kick" style="color:var(--brand)">What we do</div><h2 class="d" style="color:var(--dark)">{E(c["svc_title"])}</h2><div class="tg">{tl}</div></div></section>
{f'<section class="why"><div class="wrap"><h2 class="d">Why {E(c["name"])}</h2><div class="g3">{points_html(c, "pt")}</div></div></section>' if c["points"] else ""}
{cta(c)}{footer(c)}'''
    return css, body

def heritage(c):
    big = c["since"] or c["name"][:1]
    lst = "".join(f'<li><span class="d">{i+1:02d}</span>{E(s)}</li>' for i, s in enumerate(c["services"][:8]))
    band = c["photos"][0] if c["photos"] else (c["stock"][0] if c["stock"] else "")
    css = """
.hero{position:relative;overflow:hidden;text-align:center;padding:110px 0 90px;background:var(--paper)}
.ghost{position:absolute;left:50%;top:50%;transform:translate(-50%,-52%);font-size:clamp(220px,34vw,460px);color:transparent;-webkit-text-stroke:2px var(--brand);opacity:.16;white-space:nowrap;pointer-events:none}
.hero h1{font-size:clamp(50px,6.6vw,104px);color:var(--dark);position:relative;margin:18px auto 20px;max-width:12em}
.hero .lead{margin:0 auto;position:relative}.hero .btns{justify-content:center;position:relative}
.rule{display:flex;align-items:center;gap:16px;justify-content:center;color:var(--brand)}.rule:before,.rule:after{content:"";height:1px;width:70px;background:currentColor}
.band{height:420px;background:url(BAND) center/cover}
.list{columns:2;column-gap:60px;margin-top:30px;list-style:none}.list li{break-inside:avoid;display:flex;gap:18px;align-items:baseline;padding:18px 0;border-top:1px solid var(--line);font-size:22px}
.list span{color:var(--brand);font-size:20px}
.story{background:var(--dark);color:#fff}.story .wrap{display:grid;grid-template-columns:1fr 1.2fr;gap:70px;align-items:center}
.story p{font-size:20px;opacity:.9}
@media(max-width:880px){.list{columns:1}.story .wrap{grid-template-columns:1fr}.band{height:240px}}
""".replace("BAND", band)
    body = f'''{header(c)}
<section class="hero"><div class="ghost d">{E(big)}</div><div class="wrap"><div class="rule kick">{E(c["kicker"])}</div>
<h1 class="d">{E(c["name"])}</h1><p class="lead">{E(c["lead"])}</p>
<div class="btns"><a class="btn" style="background:var(--brand);color:var(--on)" href="#">Get in touch</a><a class="btn" style="border:2px solid var(--dark);color:var(--dark)" href="#">{E(c["phone"]) or "Contact us"}</a></div></div></section>
{f'<div class="band"></div>' if band else ''}
<section><div class="wrap"><div class="kick" style="color:var(--brand)">Services</div><h2 class="d" style="color:var(--dark)">{E(c["svc_title"])}</h2><ul class="list">{lst}</ul></div></section>
{f'<section class="story"><div class="wrap"><h2 class="d">{"Since " + c["since"] if c["since"] else "About us"}</h2><div><p>{E(c["about"])}</p>{hours_html(c)}</div></div></section>' if c["about"] else ""}
{cta(c)}{footer(c)}'''
    return css, body

def mosaic(c):
    imgs = (c["photos"] + c["stock"])[:3]
    while len(imgs) < 3 and imgs: imgs.append(imgs[0])
    m = "".join(f'<div class="m m{i}" style="background-image:url({u})"></div>' for i, u in enumerate(imgs))
    cards = "".join(f'<div class="c"><span class="n d">{i+1:02d}</span><h3 class="d">{E(s)}</h3></div>' for i, s in enumerate(c["services"][:6]))
    css = """
.hero-grid{display:grid;grid-template-columns:1fr 1.05fr;gap:56px;align-items:center;padding-top:70px;padding-bottom:80px}
.hero h1{font-size:clamp(48px,5.8vw,90px);color:var(--dark);margin:16px 0 18px}
.ms{display:grid;grid-template-columns:1.2fr 1fr;grid-template-rows:240px 240px;gap:14px}
.m{background-size:cover;background-position:center;border-radius:18px}.m0{grid-row:span 2}
.ribbon{background:var(--brand);color:var(--on)}.ribbon .wrap{display:flex;justify-content:space-between;align-items:center;gap:20px;padding-top:22px;padding-bottom:22px;flex-wrap:wrap}
.ribbon b{font-size:28px}
.cg{display:grid;grid-template-columns:repeat(3,1fr);gap:18px;margin-top:34px}.c{border:1.5px solid var(--line);border-radius:18px;padding:30px 26px;background:#fff}
.c .n{color:var(--brand);font-size:22px}.c h3{font-size:26px;color:var(--dark);margin-top:22px}
.ab{display:grid;grid-template-columns:1fr 1fr;gap:60px;align-items:start}.ab p{font-size:19px;opacity:.88}
@media(max-width:880px){.ms{grid-template-rows:160px 160px}.cg,.ab{grid-template-columns:1fr}}
"""
    body = f'''{header(c)}
<section style="padding:0;background:var(--paper)"><div class="wrap hero-grid hero"><div><div class="kick" style="color:var(--brand)">{E(c["kicker"])}</div>
<h1 class="d">{E(c["name"])}</h1><p class="lead">{E(c["lead"])}</p>
<div class="btns"><a class="btn" style="background:var(--dark);color:#fff" href="#">Get in touch</a></div></div><div class="ms">{m}</div></div></section>
<div class="ribbon"><div class="wrap"><span>{E(c["kicker"])}</span><b class="d">{E(c["phone"])}</b></div></div>
<section><div class="wrap"><h2 class="d" style="color:var(--dark)">{E(c["svc_title"])}</h2><div class="cg">{cards}</div></div></section>
{f'<section style="background:var(--paper2)"><div class="wrap ab"><h2 class="d" style="color:var(--dark)">About {E(c["name"])}</h2><div><p>{E(c["about"])}</p>{hours_html(c)}</div></div></section>' if c["about"] else ""}
{cta(c)}{footer(c)}'''
    return css, body

def night(c):
    hero = c["photos"][0]
    info = "".join(f'<div><small>{E(a)}</small><b>{E(b)}</b></div>' for a, b in [("Call", c["phone"]), ("Where", c["place"]), ("Since", c["since"])] if b)
    tl = "".join(f'<div class="t" style="background-image:linear-gradient(transparent 35%,rgba(0,0,0,.85)),url({img})"><h3 class="d">{E(s)}</h3></div>' for s, img in tiles(c, 6))
    css = """
body{background:#0e1014;color:#e9ebef}
header{background:#0e1014;color:#fff}
.hero{min-height:660px;position:relative;display:flex;align-items:flex-end;background:linear-gradient(180deg,rgba(14,16,20,.2),rgba(14,16,20,.92)),url(HERO) center/cover;padding:0}
.hero .wrap{width:100%;padding-bottom:70px;display:grid;grid-template-columns:1.4fr .8fr;gap:40px;align-items:end}
.hero h1{font-size:clamp(52px,6.4vw,100px);color:#fff;margin:16px 0}.hero h1 u{text-decoration:none;box-shadow:inset 0 -.18em 0 var(--brand)}
.info{background:rgba(255,255,255,.08);backdrop-filter:blur(8px);border:1px solid rgba(255,255,255,.16);border-radius:16px;padding:8px 24px}
.info div{display:flex;justify-content:space-between;gap:16px;padding:14px 0;border-bottom:1px solid rgba(255,255,255,.12)}.info div:last-child{border:0}
.info small{opacity:.7}.info b{color:#fff}
.tg{display:grid;grid-template-columns:repeat(3,1fr);gap:14px;margin-top:34px}
.t{height:260px;border-radius:14px;background-size:cover;background-position:center;display:flex;align-items:flex-end;padding:22px}
.t h3{font-size:26px;color:#fff}
.why .g3{display:grid;grid-template-columns:repeat(3,1fr);gap:24px;margin-top:30px}.pt{border-top:2px solid var(--brand);padding-top:18px}
.pt span{color:var(--brand2);font-size:32px}.pt p{opacity:.85;margin-top:8px}
footer{color:#aaa}
@media(max-width:880px){.hero .wrap{grid-template-columns:1fr}.tg{grid-template-columns:1fr}.why .g3{grid-template-columns:1fr}}
""".replace("HERO", hero)
    body = f'''{header(c)}
<section class="hero"><div class="wrap"><div><div class="kick" style="color:var(--brand2)">{E(c["kicker"])}</div>
<h1 class="d"><u>{E(c["name"])}</u></h1><p class="lead">{E(c["lead"])}</p>
<div class="btns"><a class="btn" style="background:var(--brand);color:var(--on)" href="#">Get in touch</a></div></div><div class="info hide-m">{info}</div></div></section>
<section><div class="wrap"><div class="kick" style="color:var(--brand2)">What we do</div><h2 class="d" style="color:#fff">{E(c["svc_title"])}</h2><div class="tg">{tl}</div></div></section>
{f'<section class="why" style="padding-top:0"><div class="wrap"><h2 class="d" style="color:#fff">Why {E(c["name"])}</h2><div class="g3">{points_html(c, "pt")}</div></div></section>' if c["points"] else ""}
{cta(c)}{footer(c)}'''
    return css, body

def ledger(c):
    rows = "".join(f'<a class="row" href="#"><span class="d">{E(s)}</span><i>→</i></a>' for s in c["services"][:8])
    quote = c["points"][0] if c["points"] else ""
    pic = (c["photos"] + c["stock"])[:1]
    css = """
body{background:var(--paper)}
.hero{padding:90px 0 70px;border-bottom:1px solid var(--line)}
.hero h1{font-size:clamp(58px,8.2vw,136px);color:var(--dark);line-height:.92;margin:18px 0 34px;max-width:10em}
.two{display:grid;grid-template-columns:1fr 1fr;gap:60px;align-items:end}.two .lead{font-size:21px}
.meta{display:grid;grid-template-columns:repeat(3,1fr);border-top:1px solid var(--line)}.meta div{padding:18px 0}.meta small{display:block;opacity:.6;font-size:13px;text-transform:uppercase;letter-spacing:.12em}.meta b{font-size:19px}
.svc{display:grid;grid-template-columns:.8fr 1.2fr;gap:70px}
.row{display:flex;justify-content:space-between;align-items:center;padding:22px 0;border-top:1px solid var(--line);font-size:30px;color:var(--dark)}.row:last-child{border-bottom:1px solid var(--line)}
.row i{font-style:normal;color:var(--brand);font-size:26px}
.pic{border-radius:4px;overflow:hidden;margin-top:30px}.pic img{width:100%;aspect-ratio:4/3;object-fit:cover}
.pull{background:var(--dark);color:#fff;text-align:center}.pull p{font-size:clamp(28px,3.2vw,46px);line-height:1.25;max-width:24em;margin:0 auto}
.pull small{display:block;margin-top:18px;opacity:.7}
@media(max-width:880px){.two,.svc{grid-template-columns:1fr}.meta{grid-template-columns:1fr}.row{font-size:22px}}
"""
    meta = "".join(f'<div><small>{a}</small><b>{E(b)}</b></div>' for a, b in [("Call", c["phone"]), ("Where", c["place"]), ("Since" if c["since"] else "Email", c["since"] or c["email"])] if b)
    body = f'''{header(c)}
<section class="hero"><div class="wrap"><div class="kick" style="color:var(--brand)">{E(c["kicker"])}</div><h1 class="d">{E(c["name"])}</h1>
<div class="two"><p class="lead">{E(c["lead"])}</p><div class="btns" style="justify-content:flex-end"><a class="btn" style="background:var(--brand);color:var(--on)" href="#">Get in touch</a></div></div></div></section>
<div class="wrap"><div class="meta">{meta}</div></div>
<section><div class="wrap svc"><div><div class="kick" style="color:var(--brand)">Services</div><h2 class="d" style="color:var(--dark)">{E(c["svc_title"])}</h2>{f'<div class="pic"><img src="{pic[0]}" alt=""></div>' if pic else ''}</div><div>{rows}</div></div></section>
{f'<section class="pull"><div class="wrap"><p class="d">“{E(quote)}”</p><small>{E(c["name"])}</small></div></section>' if quote else ""}
{cta(c)}{footer(c)}'''
    return css, body

def pop(c):
    blob = (c["photos"] + c["stock"])[:1]
    tl = "".join(f'<div class="t" style="--h:{(i*47)%360}"><span class="d">{i+1}</span><h3 class="d">{E(s)}</h3></div>' for i, s in enumerate(c["services"][:6]))
    css = """
.hero{background:var(--brand);color:var(--on);padding:80px 0 110px;position:relative;overflow:hidden}
.hero:after{content:"";position:absolute;right:-120px;bottom:-160px;width:520px;height:520px;border-radius:50%;background:var(--accent);opacity:.5}
.hero-grid{display:grid;grid-template-columns:1.15fr .85fr;gap:50px;align-items:center;position:relative;z-index:1}
.hero h1{font-size:clamp(52px,6.4vw,104px);margin:16px 0 18px}
.blob{aspect-ratio:1;border-radius:46% 54% 42% 58%/50% 44% 56% 50%;background-size:cover;background-position:center;border:8px solid rgba(255,255,255,.9);box-shadow:0 40px 70px -30px rgba(0,0,0,.45)}
.stamp{display:inline-block;background:var(--accent);color:var(--onacc);padding:8px 16px;border-radius:999px;font-weight:700;font-size:14px;transform:rotate(-3deg)}
.tg{display:grid;grid-template-columns:repeat(3,1fr);gap:18px;margin-top:36px}
.t{border-radius:24px;padding:30px;background:var(--paper);position:relative;min-height:170px}.t span{font-size:46px;color:var(--brand);opacity:.35}
.t h3{font-size:26px;color:var(--dark);margin-top:10px}
.ab{background:var(--paper2)}.ab .wrap{max-width:860px;text-align:center}.ab p{font-size:22px;opacity:.88}
@media(max-width:880px){.hero-grid{grid-template-columns:1fr}.tg{grid-template-columns:1fr}.blob{max-width:320px;margin:0 auto}}
"""
    body = f'''{header(c)}
<section class="hero"><div class="wrap hero-grid"><div>{f'<span class="stamp">Since {c["since"]}</span>' if c["since"] else f'<span class="stamp">{E(c["place"])}</span>' if c["place"] else ""}
<h1 class="d">{E(c["name"])}</h1><p class="lead">{E(c["lead"])}</p>
<div class="btns"><a class="btn" style="background:#fff;color:var(--dark)" href="#">Get in touch</a><a class="btn" style="border:2px solid currentColor" href="#">{E(c["phone"]) or "Contact us"}</a></div></div>
{f'<div class="blob" style="background-image:url({blob[0]})"></div>' if blob else ''}</div></section>
<section><div class="wrap"><div class="kick" style="color:var(--brand)">What we do</div><h2 class="d" style="color:var(--dark)">{E(c["svc_title"])}</h2><div class="tg">{tl}</div></div></section>
{f'<section class="ab"><div class="wrap"><h2 class="d" style="color:var(--dark)">About us</h2><p>{E(c["about"])}</p></div></section>' if c["about"] else ""}
{cta(c)}{footer(c)}'''
    return css, body

RENDER = {"slab": slab, "heritage": heritage, "mosaic": mosaic, "night": night, "ledger": ledger, "pop": pop}

def choose(c, seed):
    own = bool(c["photos"])
    opts = [l for l in LAYOUTS if own or l not in NEEDS_OWN_PHOTO]
    if c["since"] and "heritage" in opts and seed % 3 == 0: return "heritage"
    return opts[seed % len(opts)]

def render(c, seed):
    layout = choose(c, seed)
    fam, disp, body_font = FONTS[(seed // 11) % len(FONTS)]
    T = c["theme"]
    css, body = RENDER[layout](c)
    root = (f":root{{--brand:{T['brand']};--brand2:{T['brand2']};--dark:{T['dark']};--accent:{T['accent']};--on:{T['on']};"
            f"--onacc:{T['on_accent']};--paper:{T['paper']};--paper2:{T['paper2']};--ink:#16181d;--bg:#fff;--line:{T['line']}}}")
    base = BASE.replace("BODY", body_font).replace("DISP", disp)
    doc = f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex,nofollow"><title>{E(c['name'])}: concept by Veronos Studio</title>
<link rel="preconnect" href="https://fonts.googleapis.com"><link href="https://fonts.googleapis.com/css2?{fam}&display=swap" rel="stylesheet">
<style>{root}{base}{css}</style></head><body>
<div class="concept"><b>Concept preview</b> by Veronos Studio, not the official {E(c['name'])} website</div>
{body}</body></html>"""
    return doc, layout, disp
