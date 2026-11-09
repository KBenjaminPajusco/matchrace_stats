"""Croise ws/*.json (World Sailing) avec matchrace.db.

events  : + grade, ws_type, venue, venue_country, ws_event_id, ws_boat (et boat complété si vide)
ws_sailors(key, ws_id, ws_name)            : skipper -> identifiant World Sailing
ws_ranks(key, type, date, pos, pts, n)     : classement mondial (fin de chaque année + dernier)
"""
import json, re, sqlite3, pathlib, datetime, collections, sys
sys.path.insert(0, str(pathlib.Path(__file__).parent))
from parse import name_key

ROOT = pathlib.Path(__file__).parent
WS = ROOT / "ws"
STOP = {"the", "of", "and", "de", "la", "le", "du", "des", "cup", "match", "race", "racing", "regatta", "international",
        "championship", "championships", "open", "womens", "women", "s", "mr", "event", "trophy", "series", "world",
        "sailing", "yacht", "club", "national", "invitational", "grade", "nd", "st", "th", "rd",
        "january", "february", "march", "april", "may", "june", "july", "august", "september", "october",
        "november", "december", "spring", "summer", "autumn", "fall", "winter"}


def toks(s):
    s = re.sub(r"[^a-z0-9 ]", " ", name_key(s or "").replace("'", ""))
    return {t for t in s.split() if t not in STOP and not re.fullmatch(r"(19|20)\d\d|\d+", t) and len(t) > 1}


def toks_all(s):
    s = re.sub(r"[^a-z0-9 ]", " ", name_key(s or ""))
    return {t for t in s.split() if not re.fullmatch(r"(19|20)\d\d|\d+", t) and len(t) > 1}


def sim(a, b):
    A, B = toks(a), toks(b)
    if not A or not B:
        A, B = toks_all(a), toks_all(b)
    if not A or not B: return 0
    return len(A & B) / min(len(A), len(B)) * 0.7 + len(A & B) / len(A | B) * 0.3


def d(s):
    try: return datetime.date.fromisoformat(s[:10])
    except Exception: return None


def join_events(con):
    for col in ("grade TEXT", "ws_type TEXT", "venue TEXT", "venue_country TEXT", "ws_event_id TEXT", "ws_boat TEXT", "ws_name TEXT", "ws_score REAL"):
        try: con.execute(f"ALTER TABLE events ADD COLUMN {col}")
        except sqlite3.OperationalError: pass
    wse = json.loads((WS / "events.json").read_text("utf-8"))
    by_year = collections.defaultdict(list)
    for w in wse:
        if w["start"]: by_year[int(w["start"][:4])].append(w)
    ctry = collections.defaultdict(collections.Counter)
    for e, c in con.execute("SELECT event_id, country FROM entries WHERE country IS NOT NULL"):
        ctry[e][c] += 1
    n = 0
    for eid, year, title, slug, ds, de, women, youth in con.execute(
            "SELECT id,year,title,slug,date_start,date_end,women,youth FROM events").fetchall():
        best, bs = None, 0
        our = d(ds) if ds else None
        for y in (year - 1, year, year + 1):
            for w in by_year.get(y, []):
                ws, we = d(w["start"]), d(w["end"]) or d(w["start"])
                if our:
                    gap = 0 if ws <= our <= we + datetime.timedelta(days=1) else min(abs((our - ws).days), abs((our - we).days))
                    if gap > 4: continue
                    s = sim(title + " " + slug.replace("-", " "), w["name"]) + (0.25 if gap <= 1 else 0)
                else:
                    if ws.year != year: continue
                    s = sim(title + " " + slug.replace("-", " "), w["name"]) - 0.1
                t = (w["type"] or "").lower()
                if women and t == "women": s += 0.2
                elif not women and t == "women": s -= 0.3
                if youth and t.startswith("youth"): s += 0.1
                vc = (w["ws_id"] or "")[:3]
                if ctry[eid] and vc:
                    share = ctry[eid][vc] / sum(ctry[eid].values())
                    s += -0.35 if share == 0 else (0.15 if share >= 0.2 else -0.15 if share < 0.1 else 0)
                if s > bs: best, bs = w, s
        if best and bs >= 0.55:
            vc = (best["ws_id"] or "")[:3] or None
            con.execute("""UPDATE events SET grade=?,ws_type=?,venue=?,venue_country=?,ws_event_id=?,ws_boat=?,ws_name=?,ws_score=?,
                           boat=COALESCE(boat,?) WHERE id=?""",
                        (best["grade"], best["type"], best["venue"], vc, best["ws_id"], best["boat"], best["name"], round(bs, 2),
                         best["boat"], eid))
            n += 1
    return n


def join_sailors(con):
    con.executescript("""DROP TABLE IF EXISTS ws_sailors; DROP TABLE IF EXISTS ws_ranks;
        CREATE TABLE ws_sailors(key TEXT PRIMARY KEY, ws_id TEXT, ws_name TEXT);
        CREATE TABLE ws_ranks(key TEXT, type TEXT, date TEXT, pos INT, pts REAL, n INT);""")
    ours = {k: c for k, c in con.execute("SELECT key, country FROM skipper_country")}
    for (k,) in con.execute("SELECT key FROM skipper_names"):
        ours.setdefault(k, None)
    by_sur = collections.defaultdict(list)
    for k, c in ours.items():
        t = k.split()
        if len(t) >= 2: by_sur[(t[-1], c)].append(k)
    keycount = collections.Counter(k for k in ours)
    first_last = collections.defaultdict(list)
    for k in ours:
        t = k.split()
        if len(t) >= 2: first_last[(t[0], t[-1])].append(k)
    def deumlaut(k):
        return k.replace("oe", "o").replace("ae", "a").replace("ue", "u")
    def find(name, ctry):
        k = name_key(name)
        for kk in (k, deumlaut(k)):
            if kk in ours and ours[kk] in (None, ctry):
                return kk
        for kk in (k, deumlaut(k)):           # même nom, autre nationalité (ISV/USA, AUS/FRA...)
            if kk in ours and keycount[kk] == 1:
                return kk
        t = k.split()
        if len(t) >= 2:
            g = [x for x in by_sur.get((t[-1], ctry), []) if x.split()[0][0] == t[0][0]]
            if len(g) == 1: return g[0]
            # "Tamara Echegoyen Dominguez" -> prénom + un des noms
            for sur in t[1:]:
                g = first_last.get((t[0], sur), [])
                if len(g) == 1: return g[0]
        return None
    link = {}
    rank_rows = []
    for f in sorted(WS.glob("rank_*.json")):
        _, typ, date = f.stem.split("_", 2)
        for r in json.loads(f.read_text("utf-8")):
            wid = r["ws_id"]
            if wid not in link:
                link[wid] = (find(r["name"], r["country"]), r["name"])
            k = link[wid][0]
            if k: rank_rows.append((k, typ, date, r["pos"], r["pts"], r["n"]))
    seen = {}
    for wid, (k, nm) in link.items():
        if k and k not in seen:
            seen[k] = 1
            con.execute("INSERT INTO ws_sailors VALUES(?,?,?)", (k, wid, nm))
    con.executemany("INSERT INTO ws_ranks VALUES(?,?,?,?,?,?)", rank_rows)
    # historique mensuel complet (ws_history.py) quand il existe : remplace les relevés de fin d'année
    nh = 0
    for k, wid in con.execute("SELECT key, ws_id FROM ws_sailors").fetchall():
        f = WS / "hist" / f"{wid}.json"
        if not f.exists(): continue
        rows = [(k, t, d, pos, pts, n) for t, d, pos, pts, n in json.loads(f.read_text("utf-8")) if t in ("open", "women") and d]
        if rows:
            con.execute("DELETE FROM ws_ranks WHERE key=?", (k,))
            con.executemany("INSERT INTO ws_ranks VALUES(?,?,?,?,?,?)", rows); nh += 1
    print("historique mensuel :", nh, "skippers")
    return len(seen), len(link)


if __name__ == "__main__":
    con = sqlite3.connect(ROOT / "matchrace.db")
    print("events reliés :", join_events(con), "/", con.execute("SELECT COUNT(*) FROM events").fetchone()[0])
    if list(WS.glob("rank_*.json")):
        a, b = join_sailors(con)
        print(f"skippers reliés : {a} (sur {b} sailors classés WS)")
    con.commit()
