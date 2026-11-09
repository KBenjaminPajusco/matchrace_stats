"""Photos officielles des skippers WMRT (wmrt.com/skippers) -> site/photos/<slug>.jpg (portrait 360x450)
+ photos.json {name_key: fichier}. Liste dans wmrt_photos.txt (page rendue en JS, relevée au navigateur)."""
import io, json, pathlib, re, sqlite3, time, urllib.request, sys
from PIL import Image, ImageOps
sys.path.insert(0, str(pathlib.Path(__file__).parent))
from parse import name_key
ROOT = pathlib.Path(__file__).parent
OUT = ROOT / "site" / "photos"; OUT.mkdir(parents=True, exist_ok=True)
con = sqlite3.connect(ROOT / "matchrace.db")
keys = {k for (k,) in con.execute("SELECT key FROM skipper_names")}
alias = {"bjorn hansen": "bjorn hansen", "daniel bjornholt": "daniel christiansen"}
res, miss = {}, []
for line in (ROOT / "wmrt_photos.txt").read_text("utf-8").splitlines():
    if not line or line.startswith("#"): continue
    name, path = line.split("|")
    k = name_key(name.title())
    k = k.replace("oe", "o") if k not in keys and k.replace("oe", "o") in keys else k
    if k not in keys:
        cand = [x for x in keys if x.split()[-1] == k.split()[-1] and x.split()[0][:3] == k.split()[0][:3]]
        k = cand[0] if len(cand) == 1 else k
    if k not in keys:
        miss.append(name); continue
    slug = re.sub(r"[^a-z0-9]+", "-", k).strip("-")
    f = OUT / f"{slug}.jpg"
    if not f.exists():
        b = urllib.request.urlopen(urllib.request.Request("https://wmrt.com/wp-content/uploads/" + path,
                                                          headers={"User-Agent": "Mozilla/5.0"}), timeout=60).read()
        im = Image.open(io.BytesIO(b)).convert("RGB")
        im = ImageOps.fit(im, (360, 450), Image.LANCZOS, centering=(0.5, 0.3))
        im.save(f, "JPEG", quality=84, optimize=True, progressive=True)
        time.sleep(0.3)
    res[k] = f.name
(ROOT / "site" / "photos.json").write_text(json.dumps(res, ensure_ascii=False, indent=0), "utf-8")
print(len(res), "photos ;", "non reliés :", miss)
