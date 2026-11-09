"""Historique complet (toutes les releases mensuelles) du classement match race World Sailing,
un appel par skipper relié : /ranking?filter[sailor.worldSailingId]=X -> ws/hist/<id>.json"""
import json, sqlite3, pathlib, time, urllib.request, urllib.parse, sys
from concurrent.futures import ThreadPoolExecutor
ROOT = pathlib.Path(__file__).parent
H = ROOT / "ws" / "hist"; H.mkdir(parents=True, exist_ok=True)
API = "https://datafeed.sailing.org/stats/api/ranking?"
MR = "Match racing"

def one(wid):
    f = H / f"{wid}.json"
    if f.exists() and "--refresh" not in sys.argv: return 0
    out, p = [], 1
    while True:
        u = API + urllib.parse.urlencode({"filter[sailor.worldSailingId]": wid, "include": "rankingReference.type,rankingReference.discipline",
                                          "page": p, "paginate": 500})
        for i in range(3):
            try:
                d = json.loads(urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0 (matchrace-stats)"}), timeout=90).read()); break
            except Exception as e:
                if i == 2: print("FAIL", wid, e); return 0
                time.sleep(4 * (i + 1))
        for r in d.get("data", []):
            ref = r.get("rankingReference") or {}
            if (ref.get("discipline") or {}).get("name") != MR or ref.get("status") != "final": continue
            out.append([((ref.get("type") or {}).get("name") or "").lower(), ref.get("rankDate"), r["rankPosition"], r.get("rankPoints"), r.get("rankEventsNumber")])
        if p >= (d.get("meta") or {}).get("last_page", 1): break
        p += 1
    f.write_text(json.dumps(sorted(out, key=lambda x: (x[0], x[1] or ""))), "utf-8")
    time.sleep(0.3)
    return 1

if __name__ == "__main__":
    con = sqlite3.connect(ROOT / "matchrace.db")
    ids = [r[0] for r in con.execute("SELECT w.ws_id FROM ws_sailors w JOIN skippers s ON s.key=w.key ORDER BY s.matches DESC")]
    print(len(ids), "skippers")
    with ThreadPoolExecutor(2) as ex:
        n = sum(ex.map(one, ids))
    print("téléchargés :", n)
