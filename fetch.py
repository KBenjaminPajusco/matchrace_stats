"""Télécharge toutes les pages brutes de matchracingresults.com dans raw/ (cache, ré-exécutable)."""
import re, time, sys, pathlib, urllib.request
from concurrent.futures import ThreadPoolExecutor
BASE = "https://www.matchracingresults.com"
RAW = pathlib.Path(__file__).parent / "raw"
UA = {"User-Agent": "Mozilla/5.0 (matchrace-stats research scraper)"}
PAGES = ["", "schedule.php", "competitors.php", "event.php", "feed.php?news=0&result=-1"]

def get(url):
    for i in range(3):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30) as r:
                return r.read()
        except Exception as e:
            err = e; time.sleep(2 * (i + 1))
    print("FAIL", url, err, file=sys.stderr); return None

def events(force_home=False):
    home = RAW / "home.html"
    if force_home or not home.exists():
        RAW.mkdir(exist_ok=True); home.write_bytes(get(BASE + "/"))
    t = home.read_text("utf-8", "replace")
    out = []
    for h in re.findall(r'href="(/20\d\d/[^"]+)"', t):
        h = h if h.endswith("/") or h.endswith(".php") else h + "/"
        if h not in out: out.append(h)
    return out

def job(args):
    ev, page, force = args
    if ev.endswith(".php"):  # sous-page (ex: /2013/isaf-nations-cup/women.php)
        if page: return
        url, dest = BASE + ev, RAW / (ev.strip("/").replace("/", "__"))
    else:
        fname = "feed.js" if page.startswith("feed.php") else (page or "index.html")
        url, dest = BASE + ev + page, RAW / (ev.strip("/").replace("/", "__") + "__" + fname)
    if dest.exists() and not force: return
    b = get(url)
    if b is not None: dest.write_bytes(b)
    time.sleep(0.25)

if __name__ == "__main__":
    # --recent N : re-télécharge les events des N dernières années (résultats live)
    force_years = set()
    if "--recent" in sys.argv:
        import datetime; n = int(sys.argv[sys.argv.index("--recent") + 1])
        y = datetime.date.today().year; force_years = {str(y - i) for i in range(n)}
    evs = events(force_home=bool(force_years) or "--refresh" in sys.argv)
    jobs = [(e, p, e[1:5] in force_years) for e in evs for p in PAGES]
    with ThreadPoolExecutor(4) as ex: list(ex.map(job, jobs))
    print(len(evs), "events,", len(list(RAW.glob("*"))), "fichiers")
