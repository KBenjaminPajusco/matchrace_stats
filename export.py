"""matchrace.db -> site/data.json (compact, tout est recalculé côté navigateur)."""
import sqlite3, json, pathlib, gzip, collections
from countries import IOC
ROOT = pathlib.Path(__file__).parent
con = sqlite3.connect(ROOT / "matchrace.db")
q = lambda s: con.execute(s).fetchall()
KINDS = ["round_robin", "quarter_final", "semi_final", "final", "petit_final", "repechage", "placing", "other"]
skeys = [r[0] for r in q("SELECT key FROM skipper_names ORDER BY n DESC")]
si = {k: i for i, k in enumerate(skeys)}
names = dict(q("SELECT key,name FROM skipper_names")); ctry = dict(q("SELECT key,country FROM skipper_country"))
events = q("SELECT id,year,title,url,date_start,boat,women,youth,grade,venue,venue_country,ws_type FROM events ORDER BY id")
ei = {e[0]: i for i, e in enumerate(events)}
stages = sorted({r[0] for r in q("SELECT DISTINCT stage FROM matches")})
st = {s: i for i, s in enumerate(stages)}
W = {"port": 1, "stbd": 2, "draw": 3, "unknown": 0}
import datetime as _dt
D0 = _dt.date(2010, 1, 1)
def _day(d):
    try: return (_dt.date.fromisoformat(d[:10]) - D0).days
    except Exception: return 0
def _std(w, pr, sr):  # score standard 1-0 cohérent avec le vainqueur -> omis
    return (w == "port" and pr == "1" and sr == "0") or (w == "stbd" and pr == "0" and sr == "1")
# match compact : [event, bleu, jaune, vainqueur, phase, libellé phase, jour (depuis 2010-01-01, 0 = inconnu),
#                  flight, score bleu, score jaune ("" = 1-0 standard), pénalités, minute du résultat (-1 = inconnue)]
m = [[ei[e], si[p], si[s], W[w], KINDS.index(k), st[stg], _day(d) if d else 0, fl or 0,
      "" if _std(w, pr, sr) else (pr or ""), "" if _std(w, pr, sr) else (sr or ""),
      (1 if pp else 0) + (2 if ps else 0), int(ts[11:13]) * 60 + int(ts[14:16]) if ts else -1]
     for e, p, s, w, k, stg, d, fl, pr, sr, pp, ps, ts in
     q("SELECT event_id,port_key,stbd_key,winner,stage_kind,stage,date,flight,port_raw,stbd_raw,pen_port,pen_stbd,ts FROM matches ORDER BY event_id,match_no")]
ent = [[ei[e], si[k], r] for e, k, r in q("SELECT event_id,name_key,final_rank FROM entries WHERE final_rank IS NOT NULL") if k in si]
wsid = dict(q("SELECT key, ws_id FROM ws_sailors")) if q("SELECT name FROM sqlite_master WHERE name='ws_sailors'") else {}
ranks = collections.defaultdict(list)
if wsid:
    for k, t, d, pos, pts, n in q("SELECT key,type,date,pos,pts,n FROM ws_ranks ORDER BY date"):
        if k in si: ranks[si[k]].append([t[0], d, pos, pts])
dates = {t: q(f"SELECT MAX(date) FROM ws_ranks WHERE type='{t}'")[0][0] for t in ("open", "women")} if wsid else {}
# stats World Sailing par pays : dernier classement complet (tous les classés, pas seulement nos skippers)
wsc = {}
for t in ("open", "women"):
    fs = sorted((ROOT / "ws").glob(f"rank_{t}_*.json"))
    if not fs: continue
    agg = collections.defaultdict(list)
    for r in json.loads(fs[-1].read_text("utf-8")):
        if r.get("country"): agg[r["country"]].append(r["pos"])
    for c, ps in agg.items():
        wsc.setdefault(c, {})[t[0]] = [len(ps), round(sum(ps) / len(ps), 1), min(ps), sum(p <= 50 for p in ps)]
ph = ROOT / "site" / "photos.json"
photos = {si[k]: f for k, f in json.loads(ph.read_text("utf-8")).items() if k in si} if ph.exists() else {}
data = {"generated": q("SELECT date('now')")[0][0], "kinds": KINDS, "stages": stages,
        "skippers": [[k, names[k], ctry.get(k) or "", wsid.get(k) or ""] for k in skeys],
        "rank_dates": dates, "countries": IOC, "ws_country": wsc, "photos": photos,
        "events": [list(e[1:]) for e in events], "matches": m, "entries": ent}
s = json.dumps(data, separators=(",", ":"), ensure_ascii=False)
def _write(name, txt):
    (ROOT / "site" / name).write_text(txt, "utf-8")
    gz = gzip.compress(txt.encode(), 9)
    (ROOT / "site" / (name + ".gz")).write_bytes(gz)   # servi tel quel par serve.py (Content-Encoding: gzip)
    print(f"{name}: {len(txt)/1e6:.2f} Mo, gzip {len(gz)/1e6:.2f} Mo")
_write("data.json", s)
_write("ranks.json", json.dumps(ranks, separators=(",", ":")))
