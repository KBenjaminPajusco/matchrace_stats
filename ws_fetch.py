"""World Sailing (API publique datafeed.sailing.org) -> ws/*.json (cache).

- events match race (grade W..5, type Open/Women/Youth, dates, lieu, classe si renseignée)
- classements match race Open + Women : dernière release + dernière release de chaque année
"""
import json, time, sys, pathlib, urllib.request, urllib.parse

ROOT = pathlib.Path(__file__).parent
WS = ROOT / "ws"
API = "https://datafeed.sailing.org/stats/api/"
FEED = "https://www.sailing.org/_feed/rankings"
MR = "4f9fa0bb-45e0-40f4-b013-e0c174e703d7"
TYPES = {"open": "8aed8987-6f02-4d38-b668-f5235d945fe6", "women": "178b0c8c-49f4-4e99-9e4c-3ba2ede13cd7"}
UA = {"User-Agent": "Mozilla/5.0 (matchrace-stats)"}


def get(url, params):
    u = url + ("&" if "?" in url else "?") + urllib.parse.urlencode(params)
    for i in range(3):
        try:
            with urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=60) as r:
                time.sleep(0.4)
                return json.loads(r.read().decode("utf-8", "replace"))
        except Exception as e:
            err = e; time.sleep(3 * (i + 1))
    raise RuntimeError(f"{u}: {err}")


def paged(url, params, size=1000):
    out, p = [], 1
    while True:
        d = get(url, {**params, "page": p, "paginate": size})
        out += d.get("data", [])
        m = d.get("meta") or {}
        last = m.get("last_page") or m.get("lastPage") or 1
        if p >= last: return out
        p += 1


def events(force):
    f = WS / "events.json"
    if f.exists() and not force: return
    rows = []
    for g in ["W", "1", "2", "3", "4", "5"]:
        rows += paged(API + "event", {"include": "grade,regatta.venue,type,boatClass",
                                       "filter[discipline.id]": MR, "filter[grade.name]": g})
        print("grade", g, len(rows))
    keep = []
    for e in rows:
        r = e.get("regatta") or {}
        if not r or (r.get("startDate") or "") < "2010-06": continue
        keep.append({"id": e["id"], "grade": (e.get("grade") or {}).get("name"), "type": (e.get("type") or {}).get("name"),
                     "multiplier": e.get("multiplier"), "name": r.get("name"), "start": (r.get("startDate") or "")[:10],
                     "end": (r.get("endDate") or "")[:10], "ws_id": r.get("worldSailingId"),
                     "venue": (r.get("venue") or {}).get("name"), "website": r.get("website"),
                     "boat": (e.get("boatClass") or {}).get("name")})
    f.write_text(json.dumps(keep, ensure_ascii=False, indent=0), "utf-8")
    print(len(keep), "events WS >= 2010-06")


def rankings(force):
    for t, tid in TYPES.items():
        ref = get(API + "rankingReference", {"filter[discipline.id]": MR, "filter[type.id]": tid,
                                             "filter[status]": "final", "distinct": "rankDate"})
        dates = sorted({(x.get("distinctRankDate") or x.get("rankDate") if isinstance(x, dict) else x) for x in ref.get("data", ref)} - {None})
        by_year = {}
        for d in dates:
            if d[:4] >= "2011": by_year[d[:4]] = d          # dernière release de l'année
        want = sorted(set(by_year.values()) | {dates[-1]})
        for d in want:
            f = WS / f"rank_{t}_{d[:10]}.json"
            if f.exists() and not (force and d == dates[-1]): continue
            rows = paged(FEED, {"date": d, "discipline": MR, "typeId": tid, "boatClassId": "",
                                "sort": "rankPosition", "dir": "asc"}, size=100)
            f.write_text(json.dumps([{"pos": r["rankPosition"], "best": r.get("rankBest"), "pts": r.get("rankPoints"),
                                      "n": r.get("rankEventsNumber"), "name": r["sailor"]["name"],
                                      "ws_id": r["sailor"]["worldSailingId"],
                                      "country": ((r["sailor"].get("primaryCountry") or {}).get("countryCode"))}
                                     for r in rows if r.get("sailor")], ensure_ascii=False), "utf-8")
            print(t, d, len(rows))


if __name__ == "__main__":
    WS.mkdir(exist_ok=True)
    force = "--refresh" in sys.argv
    events(force)
    rankings(force)
