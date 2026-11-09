"""Parse raw/ -> matchrace.db (SQLite).

Conventions du site matchracingresults.com :
  - cellule <td id="r{N}{S|P}"> = match n°N de l'event, entrée Starboard ou Port.
  - RRS Appendix C : le bateau à gauche de la liste de paires = entrée bâbord = pavillon BLEU,
    l'autre = entrée tribord = pavillon JAUNE.  Le schedule "A -vs- B" met A en P (vérifié).
  - valeur = points du match : 1 victoire, 0 défaite, fractions/négatifs = pénalités
    (points retirés), codes DNF/DSQ/... = défaite.
"""
import re, sqlite3, pathlib, unicodedata, html, datetime, collections

ROOT = pathlib.Path(__file__).parent
RAW = ROOT / "raw"
DB = ROOT / "matchrace.db"

LOSS_CODES = {"DNF", "DSQ", "RET", "DNC", "BFD", "DNS", "NSC", "RTD", "OCS", "DNE", "UFD"}
BOATS = ["J/80", "J/70", "J/22", "J/24", "Elliott 6m", "Elliott 7", "Elliott 6", "DS37", "M32", "RS Elite",
         "Match 28", "Ultimate 20", "Sonar", "Viper", "Foiling", "Melges 24", "Melges 20", "SB20", "Tom 28",
         "Beneteau First 7.5", "First 7.5", "Bavaria", "Swedish Match 40", "F18", "Diam 24", "Etchells",
         "J/105", "Catalina 37", "Sabre", "420", "Laser Pico", "RS Feva", "Hansa 303", "2.4", "Starling",
         "Magic", "Nordic Folkboat", "Sonata", "Grand Prix", "Waszp", "WASZP", "Club Swan 36", "GC32",
         "Platu 25", "Skud", "Tom 28 Max", "Elan", "Farr 30", "Zoom 8", "Colgate 26"]


def fix(s):
    """Décodage robuste (pages mi-utf8 mi-cp1252) + mojibake + entités."""
    b = s.encode("utf-8", "surrogateescape")
    try:
        s = b.decode("utf-8")
    except UnicodeDecodeError:
        s = b.decode("cp1252", "replace")
    if "Ã" in s or "Å" in s:
        try:
            s = s.encode("cp1252").decode("utf-8")
        except Exception:
            pass
    s = html.unescape(re.sub(r"<[^>]+>", " ", s))
    return re.sub(r"\s+", " ", s).strip()


CLUB_RE = re.compile(r"^\s*([A-Za-z][A-Za-z/.]{1,10})\s+-\s+(?=\S)")
CLUB_SUF = re.compile(r"\s*/\s*([A-Za-z][A-Za-z.]{1,9})\s*$")
NICK = {"chris": "christopher", "harry": "harrison", "will": "william", "bill": "william", "matt": "matthew",
        "dave": "david", "tom": "thomas", "steph": "stephanie", "ben": "benjamin", "don": "donald",
        "steve": "steven", "stephen": "steven", "ali": "alison", "sam": "samuel", "lachy": "lachlan",
        "jules": "juliet", "tim": "timothee", "nick": "nicholas", "nicolas": "nicholas", "mike": "michael",
        "rob": "robert", "robbie": "robert", "bob": "robert", "jim": "james", "jamie": "james", "pete": "peter", "andy": "andrew",
        "alex": "alexander", "dan": "daniel", "danny": "daniel", "joe": "joseph", "josh": "joshua",
        "jon": "jonathan", "johnny": "john", "kate": "katherine", "katie": "katherine", "liz": "elizabeth",
        "maddy": "madeleine", "max": "maximilian", "nat": "nathan", "rick": "richard", "rich": "richard",
        "ed": "edward", "ted": "edward", "fred": "frederick", "greg": "gregory", "jeff": "jeffrey",
        "jeffery": "jeffrey", "theo": "theodore", "zach": "zachary", "zack": "zachary"}


def split_club(n):
    m = CLUB_RE.match(n)
    if m:
        return n[m.end():].strip(), m.group(1)
    m = CLUB_SUF.search(n)
    if m and len(n[:m.start()].split()) >= 2:
        return n[:m.start()].strip(), m.group(1)
    return n, None


def name_key(n):
    n = split_club(n)[0]
    n = unicodedata.normalize("NFKD", n)
    n = "".join(c for c in n if not unicodedata.combining(c))
    n = re.sub(r"[’'`]", "", n.lower())
    n = re.sub(r"[^a-z0-9 ]", " ", n)
    t = re.sub(r"\s+", " ", n).strip().split()
    if len(t) > 1 and t[0] in NICK:
        t[0] = NICK[t[0]]
    return " ".join(t)


def lev(a, b):
    p = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        c = [i]
        for j, cb in enumerate(b, 1):
            c.append(min(p[j] + 1, c[j - 1] + 1, p[j - 1] + (ca != cb)))
        p = c
    return p[-1]


def merge_keys(con):
    """Fusionne les variantes orthographiques : même nom de famille + même pays, prénom à distance <= 2
    (prénoms >= 5 lettres, même initiale) ; puis aliases.csv (manuel, prioritaire)."""
    rows = con.execute("""SELECT k, MAX(c), COUNT(*) FROM (
        SELECT port_key k, NULL c FROM matches UNION ALL SELECT stbd_key, NULL FROM matches
        UNION ALL SELECT name_key, country FROM entries) GROUP BY k""").fetchall()
    n = {k: cnt for k, _, cnt in rows}
    ctry = {k: c for k, c, _ in rows}
    groups = collections.defaultdict(list)
    for k in n:
        t = k.split()
        if len(t) >= 2:
            groups[(" ".join(t[1:]), ctry[k])].append(k)
    alias = {}
    for g in groups.values():
        g.sort(key=lambda k: -n[k])
        for i, k in enumerate(g):
            if k in alias:
                continue
            for k2 in g[i + 1:]:
                f1, f2 = k.split()[0], k2.split()[0]
                if k2 not in alias and f1[0] == f2[0] and min(len(f1), len(f2)) >= 5 and lev(f1, f2) <= 2:
                    alias[k2] = k
    af = ROOT / "aliases.csv"
    if af.exists():
        for line in af.read_text("utf-8").splitlines():
            if "," in line and not line.startswith("#"):
                a, b = [name_key(x) for x in line.split(",", 1)]
                if a and b: alias[a] = b
    for a, b in alias.items():
        while b in alias and alias[b] != a and alias[b] != b:
            b = alias[b]
        for col in ("port_key", "stbd_key"):
            con.execute(f"UPDATE matches SET {col}=? WHERE {col}=?", (b, a))
        con.execute("UPDATE entries SET name_key=? WHERE name_key=?", (b, a))
    return len(alias)


def read(p):
    return p.read_bytes().decode("utf-8", "surrogateescape")


def parse_val(v):
    v = v.strip()
    if v in ("", "-", "&nbsp;"):
        return None, None
    if v.lower() == "draw":
        return 0.5, "Draw"
    u = v.upper()
    if u in LOSS_CODES or u == "RDG":
        return (0.0 if u != "RDG" else None), u
    try:
        return float(v), None
    except ValueError:
        return None, v


def stage_kind(name):
    n = name.lower()
    if re.search(r"round robin|\brr\b|rr\d|group|stage|gold|silver|league|top \d|super|consolation", n) and "final" not in n:
        return "round_robin"
    if re.search(r"semi|sf\d|\bsf\b", n): return "semi_final"
    if re.search(r"quarter|\bqf|qf\d", n): return "quarter_final"
    if re.search(r"petit|bronze", n): return "petit_final"
    if re.search(r"repechage", n): return "repechage"
    if re.search(r"\bfinal", n): return "final"
    if re.search(r"\d+(st|nd|rd|th)", n): return "placing"
    return "other"


MONTHS = {m: i for i, m in enumerate(["january", "february", "march", "april", "may", "june", "july",
                                      "august", "september", "october", "november", "december"], 1)}


def parse_schedule(t, year):
    """Retourne liste ordonnée [(date, flight, stage, nameA, nameB)] + toutes les dates vues."""
    out, dates, cur = [], [], None
    tok = re.finditer(r"<h2>(.*?)</h2>|<p>\s*F(\d+)M\d+\s*\(([^)]*)\)\s*:?(.*?)</p>", t, re.S | re.I)
    for m in tok:
        if m.group(1) is not None:
            h = fix(m.group(1)).lower()
            dm = re.search(r"(\d{1,2})(?:st|nd|rd|th)?\s+([a-z]+)", h)
            if dm and dm.group(2) in MONTHS:
                try:
                    cur = datetime.date(year, MONTHS[dm.group(2)], int(dm.group(1))).isoformat()
                    dates.append(cur)
                except ValueError:
                    pass
            continue
        pair = fix(m.group(4))
        ab = re.split(r"\s+-?vs?\.?-?\s+", pair, maxsplit=1, flags=re.I)
        a, b = (ab + [""])[:2]
        out.append((cur, int(m.group(2)), fix(m.group(3)), a.strip(), b.strip()))
    return out, dates


NEWS_RE = re.compile(r"add_news\('((?:[^'\\]|\\.)*)',\s*'[^']*',\s*'<abbr class=\"timeago\" title=\"([^\"]+)\"")
BEAT_RE = re.compile(r"^\s*([A-Za-z]*\s*\d+\s*[A-Za-z]*\s*\d*)\s*:\s*(.+?) beat (.+?)\s*$")


def parse_feed(t):
    """Fil live 'F4M2: A (CTY) beat B (CTY)' horodaté -> [(label, flight, nomA, nomB, iso)] dédupliqué par label (la dernière entrée gagne)."""
    out = {}
    for txt, ts in NEWS_RE.findall(t):
        m = BEAT_RE.match(fix(txt.replace("\\'", "'")))
        if not m:
            continue
        label = re.sub(r"\s+", "", m.group(1)).upper()
        fl = re.match(r"[A-Z]*(\d+)", label)
        strip = lambda n: re.sub(r"\s*\([^()]*\)\s*$", "", n).strip(" !.")   # "(SWE)" ou "(CYCA)"
        out.pop(label, None)
        out[label] = (label, int(fl.group(1)) if fl else None, strip(m.group(2)), strip(m.group(3)), ts)
    return list(out.values())


def link_feed(con, eid, ins, feed, stats):
    """ins = [(match_id, match_no, port_key, stbd_key, flight)] ; écrit ts + tz (+ date/flight si absents)."""
    keys = {k for _, _, p, s_, _ in ins for k in (p, s_)}
    def resolve(n):
        k = name_key(n)
        if k in keys: return k
        t = k.split()
        c = [x for x in keys if t and (x.split()[-1] == t[-1] or t[-1] in x.split())]
        return c[0] if len(c) == 1 else None
    free = {mid: (no, p, s_, fl) for mid, no, p, s_, fl in ins}
    for label, fl, a, b, ts in sorted(feed, key=lambda x: x[4]):
        ka, kb = resolve(a), resolve(b)
        if not ka or not kb:
            stats["feed_unresolved"] += 1; continue
        cand = sorted((v[0], mid, v[3]) for mid, v in free.items() if {v[1], v[2]} == {ka, kb})
        if not cand:
            stats["feed_nomatch"] += 1; continue
        pick = next((c for c in cand if c[2] == fl), cand[0])
        mid = pick[1]; free.pop(mid)
        con.execute("UPDATE matches SET ts=?, tz=?, date=COALESCE(date, ?), flight=COALESCE(flight, ?) WHERE id=?",
                    (ts[:19], ts[19:] or None, ts[:10], fl, mid))
        stats["feed_linked"] += 1


def surname_ok(sched_name, full):
    s, f = name_key(sched_name), name_key(full)
    return bool(s) and bool(f) and (s in f or s.split()[-1] in f.split() or f.split()[-1] in s.split())


def main():
    if DB.exists():
        DB.unlink()
    con = sqlite3.connect(DB)
    con.executescript(open(ROOT / "schema.sql", encoding="utf-8").read())
    files = sorted(p for p in RAW.iterdir() if p.name.endswith("__index.html")
                   or (p.name.endswith(".php") and not re.search(r"__(schedule|competitors|event)\.php$", p.name)))
    stats = collections.Counter()
    for p in files:
        stem = p.name[:-len("__index.html")] if p.name.endswith("__index.html") else p.name[:-4]
        parts = stem.split("__")
        year, slug = int(parts[0]), "/".join(parts[1:])
        url = "https://www.matchracingresults.com/" + "/".join(parts) + ("/" if p.name.endswith("__index.html") else ".php")
        t = read(p)
        h1 = re.search(r"<h1>.*?<br\s*/?>(.*?)</h1>", t, re.S)
        title = fix(h1.group(1)) if h1 else slug
        base = ROOT / "raw" / ("__".join(parts[:2]))
        ev_txt = sched_t = comp_t = ""
        for suf, var in (("event.php", "ev"), ("schedule.php", "sc"), ("competitors.php", "co")):
            f = pathlib.Path(str(base) + "__" + suf)
            if f.exists():
                if var == "ev": ev_txt = read(f)
                elif var == "sc": sched_t = read(f)
                else: comp_t = read(f)
        desc_m = re.search(r'<div id="results">(.*?)</div>', ev_txt, re.S)
        desc = fix(desc_m.group(1)) if desc_m else ""
        if not desc:
            dm = re.search(r'<div id="results">(.*?)<table', t, re.S)
            desc = fix(dm.group(1)) if dm else ""
        blob = desc + " " + fix(comp_t)
        boat = next((b for b in BOATS if re.search(r"(?<![\w/])" + re.escape(b) + r"(?![\w])", blob, re.I)), None)
        sched, dates = parse_schedule(sched_t, year)
        women = bool(re.search(r"women|ladies|female|wimr", slug + " " + title, re.I))
        youth = bool(re.search(r"youth|junior|u2[1-5]|under", slug + " " + title, re.I))
        cur = con.execute(
            "INSERT INTO events(year,slug,title,url,date_start,date_end,boat,description,women,youth) VALUES(?,?,?,?,?,?,?,?,?,?)",
            (year, slug, title, url, min(dates) if dates else None, max(dates) if dates else None,
             boat, desc[:2000], women, youth))
        eid = cur.lastrowid

        # classement final ("Overall placings" = 1er tableau sans id)
        ov = re.search(r"<table>\s*<thead>.*?Overall.*?</thead>(.*?)</table>", t, re.S | re.I)
        ranks = {}
        if ov:
            for rk, flag, nm in re.findall(r'<td>\s*(\d+)\.?\s*</td>\s*<td class="country">(?:<img[^>]*alt="([A-Z]{3})")?.*?</td>\s*<td class="skipper">(.*?)</td>', ov.group(1), re.S):
                ranks[fix(nm)] = (int(rk), flag)

        # tableaux de phases
        cells = {}  # match_no -> {'S':(name,country,val,stage), 'P':...}
        countries = {}
        for tm in re.finditer(r'<table id="([^"]+)">(.*?)</table>', t, re.S):
            th = re.search(r'<th colspan="2"[^>]*>(.*?)</th>', tm.group(2), re.S)
            stage = fix(th.group(1)) if th else tm.group(1)
            for row in re.findall(r"<tr>(.*?)</tr>", tm.group(2), re.S):
                sk = re.search(r'<td class="skipper">(.*?)</td>', row, re.S)
                if not sk:
                    continue
                name = fix(sk.group(1))
                c = re.search(r'flags/([A-Z]{3})\.png', row)
                if c: countries[name] = c.group(1)
                for no, side, v in re.findall(r'<td id="r(\d+)([SP])"[^>]*>(.*?)</td>', row, re.S):
                    cells.setdefault(int(no), {})[side] = (name, fix(v), stage)

        # skippers des tableaux de matchs (référence) ; le classement final peut contenir
        # "Skipper, équipier, équipier ... Club" -> rattaché au skipper de l'event
        EK = {}
        for nm_ in countries:
            EK.setdefault(name_key(nm_), nm_)
        ent = {k: [split_club(n_)[0], split_club(n_)[1], countries[n_], None, None] for k, n_ in EK.items()}
        for name, (rk, flag) in ranks.items():
            first = re.split(r"\s*[,;]\s*", name)[0]
            k = name_key(first)
            if k not in EK:
                full = " " + name_key(name) + " "
                c_ = [x for x in EK if " " + x + " " in full]
                if c_:
                    k = max(c_, key=len)
            crew = name[len(first):].strip(" ,;") or None
            e_ = ent.setdefault(k, [split_club(first)[0], split_club(first)[1], flag, None, None])
            e_[3], e_[4] = rk, crew
            if not e_[2]: e_[2] = flag
            stats["rank_linked" if k in EK else "rank_unlinked"] += 1
        for k, (nm, club, ctry_, rk, crew) in ent.items():
            con.execute("INSERT INTO entries(event_id,name,name_key,club,country,final_rank,crew) VALUES(?,?,?,?,?,?,?)",
                        (eid, nm, k, club, ctry_, rk, crew))

        # appariement match -> schedule (ordre séquentiel, validé par nom)
        sched_ok = 0
        ins = []
        for no in sorted(cells):
            d = cells[no]
            if "S" not in d or "P" not in d:
                stats["half_match"] += 1
                continue
            (pn, pv_raw, stg), (sn, sv_raw, _) = d["P"], d["S"]
            pv, pc = parse_val(pv_raw)
            sv, sc = parse_val(sv_raw)
            if pv is None and sv is None and not pc and not sc:
                stats["unsailed"] += 1
                continue
            pv0 = pv if pv is not None else (-9 if pc else 0)
            sv0 = sv if sv is not None else (-9 if sc else 0)
            if pc == "Draw" or sc == "Draw" or pv0 == sv0:
                winner = "draw" if (pc == "Draw" or sc == "Draw") else "unknown"
            else:
                winner = "port" if pv0 > sv0 else "stbd"
            pen_p = (pv is not None and pv not in (0.0, 1.0)) or bool(pc and pc != "Draw")
            pen_s = (sv is not None and sv not in (0.0, 1.0)) or bool(sc and sc != "Draw")
            date = flight = None
            if 0 < no <= len(sched):
                sd, fl, _, a, b = sched[no - 1]
                if surname_ok(a, pn) and surname_ok(b, sn):
                    date, flight = sd, fl
                    sched_ok += 1
            con.execute("""INSERT INTO matches(event_id,match_no,stage,stage_kind,date,flight,
                port_name,port_key,stbd_name,stbd_key,port_raw,stbd_raw,port_pts,stbd_pts,winner,pen_port,pen_stbd)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                        (eid, no, stg, stage_kind(stg), date, flight, split_club(pn)[0], name_key(pn),
                         split_club(sn)[0], name_key(sn),
                         pv_raw, sv_raw, pv, sv, winner, pen_p, pen_s))
            ins.append((con.execute("SELECT last_insert_rowid()").fetchone()[0], no, name_key(pn), name_key(sn), flight))
            stats["matches"] += 1
            stats["winner_" + winner] += 1
        stats["sched_matched"] += sched_ok
        ff = pathlib.Path(str(base) + "__feed.js")
        if ff.exists() and ins:
            link_feed(con, eid, ins, parse_feed(read(ff)), stats)
        stats["events"] += 1
    stats["aliases"] = merge_keys(con)
    con.commit()
    con.executescript(open(ROOT / "views.sql", encoding="utf-8").read())
    con.commit()
    print(dict(stats))


if __name__ == "__main__":
    main()
