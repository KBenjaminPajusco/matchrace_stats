import re, pathlib, collections
RAW = pathlib.Path(__file__).parent.parent / "raw"
NEWS = re.compile(r"add_news\('((?:[^'\\]|\\.)*)',\s*'[^']*',\s*'<abbr class=\"timeago\" title=\"([^\"]+)\"")
BEAT = re.compile(r"^\s*([A-Za-z]*\s*\d+\s*[A-Za-z]*\s*\d*)\s*:\s*(.+?) beat (.+?)\s*$")
tot = beat = 0; fmt = collections.Counter(); nof = []; tzs = collections.Counter(); per = collections.Counter()
for f in RAW.glob("*__feed.js"):
    t = f.read_bytes().decode("utf-8", "replace")
    for txt, ts in NEWS.findall(t):
        tot += 1
        if " beat " in txt:
            beat += 1; per[f.name] += 1
            m = BEAT.match(txt)
            if m: fmt[re.sub(r"\d+", "N", m.group(1))] += 1
            else: nof.append(txt[:110])
            tzs[ts[-6:]] += 1
print(tot, beat, "events avec beat:", len(per))
print(fmt.most_common(15)); print(len(nof), nof[:10]); print(tzs.most_common(12))
