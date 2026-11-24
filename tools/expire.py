"""Take down homepage previews 7 days after they were sent.

Each live preview the Veronos reply engine sends gets docs/<business>/expires.txt (a date, YYYY-MM-DD).
Once that date has passed (Edmonton time), the preview is swapped for a short "this preview has expired" page
and the original is kept in archive/<business>/ (not published), so it can be brought back.

  python tools/expire.py                 take down everything past its date
  python tools/expire.py revive <slug> [days=7]   put a preview back up for another N days
"""
import datetime as dt, os, shutil, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOCS, ARCH = os.path.join(ROOT, "docs"), os.path.join(ROOT, "archive")
TODAY = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=7)).date()

PAGE = """<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex,nofollow"><title>Preview expired | Veronos Studio</title>
<style>body{margin:0;min-height:100vh;display:grid;place-items:center;font-family:system-ui,-apple-system,Segoe UI,Roboto,sans-serif;background:#f6f5f1;color:#1f2a24}
.c{max-width:440px;padding:40px 28px;text-align:center}h1{font-size:24px;margin:0 0 12px}p{font-size:17px;line-height:1.5;color:#45524b;margin:0 0 10px}
.b{display:inline-block;margin-top:14px;font-weight:600;color:#1f3d2b}</style></head><body><div class="c">
<h1>This preview has expired</h1><p>Homepage previews from Veronos Studio stay up for 7 days.</p>
<p>Want it back? Just reply to Kash's email and he'll put it back up.</p><a class="b" href="https://veronosstudio.com">veronosstudio.com</a></div></body></html>"""

def expire():
    gone = []
    for slug in sorted(os.listdir(DOCS)):
        d = os.path.join(DOCS, slug)
        f = os.path.join(d, "expires.txt")
        if not os.path.isfile(f):
            continue
        try:
            when = dt.date.fromisoformat(open(f).read().strip())
        except ValueError:
            continue
        if TODAY <= when:
            continue
        os.makedirs(ARCH, exist_ok=True)
        dest = os.path.join(ARCH, slug)
        if os.path.exists(dest):
            shutil.rmtree(dest)
        shutil.copytree(d, dest)
        for name in os.listdir(d):
            p = os.path.join(d, name)
            shutil.rmtree(p) if os.path.isdir(p) else os.remove(p)
        open(os.path.join(d, "index.html"), "w").write(PAGE)
        open(os.path.join(d, "expired.txt"), "w").write(TODAY.isoformat())
        gone.append(slug)
    print(f"expired {len(gone)}: {', '.join(gone) or '-'}")

def revive(slug, days=7):
    src, d = os.path.join(ARCH, slug), os.path.join(DOCS, slug)
    if not os.path.isdir(src):
        sys.exit(f"no archived preview for {slug}")
    if os.path.exists(d):
        shutil.rmtree(d)
    shutil.copytree(src, d)
    open(os.path.join(d, "expires.txt"), "w").write((TODAY + dt.timedelta(days=days)).isoformat())
    print(f"revived {slug} until {TODAY + dt.timedelta(days=days)}")

if __name__ == "__main__":
    if len(sys.argv) > 2 and sys.argv[1] == "revive":
        revive(sys.argv[2], int(sys.argv[3].split("=")[-1]) if len(sys.argv) > 3 else 7)
    else:
        expire()
