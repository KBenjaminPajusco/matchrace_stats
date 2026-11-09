import sqlite3, pathlib, re, sys, collections, random
ROOT = pathlib.Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
from parse import parse_feed, read, name_key
con = sqlite3.connect(ROOT / "matchrace.db")
# 1) cohérence : on relit le fil et on compare le vainqueur
agree = dis = 0; unres = collections.Counter(); ex = []
for eid, url in con.execute("SELECT id, url FROM events"):
    stem = url.split(".com/")[1].strip("/").replace("/", "__")
    f = ROOT / "raw" / (stem + "__feed.js")
    if not f.exists(): continue
    rows = con.execute("SELECT port_key, stbd_key, winner, ts FROM matches WHERE event_id=? AND ts IS NOT NULL", (eid,)).fetchall()
    byts = {r[3]: r for r in rows}
    keys = {k for r in con.execute("SELECT port_key, stbd_key FROM matches WHERE event_id=?", (eid,)) for k in r}
    for label, fl, a, b, ts in parse_feed(read(f)):
        r = byts.get(ts[:19])
        if r:
            wk = r[0] if r[2] == "port" else r[1] if r[2] == "stbd" else None
            ka = name_key(a)
            if wk is None: continue
            if ka == wk or (ka.split() and ka.split()[-1] in wk.split()): agree += 1
            else: dis += 1
        else:
            for n in (a, b):
                if name_key(n) not in keys:
                    unres[(stem[:40], n)] += 1
print(f"vainqueur fil = vainqueur tableau : {agree} / {agree + dis} ({100 * agree / max(1, agree + dis):.1f} %)")
random.seed(4)
items = list(unres.items())
for (ev, n), c in random.sample(items, min(25, len(items))):
    keys = sorted({k for r in con.execute("SELECT port_key, stbd_key FROM matches m JOIN events e ON e.id=m.event_id WHERE e.url LIKE ?", ("%" + ev.replace("__", "/") + "%",)) for k in r})
    print(ev, "|", repr(n), "| ex keys:", keys[:4])
