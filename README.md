# Match Race Stats

En ligne : https://benjamin.pajusco.fr/matchrace_stats/ (GitHub Pages, publie `site/` à chaque push sur main).

Stats de match race : https://www.matchracingresults.com (684 events depuis 2011) croisé avec l'API publique World Sailing.

```
PY=/c/Users/BenjaminPajusco/AppData/Local/Programs/Python/Python312/python   # (le python MinGW n'a pas de certificats SSL)
$PY fetch.py --recent 1   # pages matchracingresults + fil live feed.php (cache raw/, re-télécharge l'année en cours)
$PY ws_fetch.py           # World Sailing : events gradés + classements Open/Women (cache ws/, --refresh pour le dernier)
$PY parse.py              # raw/ -> matchrace.db (+ horodatage du fil live)
$PY ws_join.py            # + grade / lieu / pays hôte des events, id World Sailing des skippers
$PY ws_history.py         # historique mensuel du classement WS, 1 appel par skipper relié (cache ws/hist/)
$PY ws_join.py            # (relancé) intègre l'historique mensuel
$PY wmrt_photos.py        # photos officielles WMRT -> site/photos/ (liste dans wmrt_photos.txt)
$PY export.py             # -> site/data.json
$PY serve.py             # http://localhost:8830 — sert site/ (statique) avec les .json pré-compressés (.gz) et plusieurs requêtes à la fois
# data.json (0,4 Mo gzip) au chargement ; ranks.json (historiques WS) chargé à l'ouverture d'une fiche skipper
```

## Conventions
- Horodatage : `feed.php?news=0&result=-1` de chaque event = fil live « F4M2: A (CTY) beat B (CTY) » avec l'heure locale + fuseau → `matches.ts/tz` (93,6 % des matchs, vainqueur concordant à 99,2 %). Ordre dans la journée = heure du résultat.
- Séries et momentum : uniquement à l'intérieur d'une même journée ; momentum testé en round robin (test des runs, attendu = ordre aléatoire de la journée).
- Cellule `r{N}P` / `r{N}S` du site = match N, entrée bâbord / tribord. **P = bleu, S = jaune** (RRS Annexe C ; validé 99 % via le schedule).
- Classement final « Skipper, équipier, … Club » → rattaché au skipper des matchs du même event, équipage dans `entries.crew`.
- Noms : préfixes/suffixes de club, diminutifs, fautes (Levenshtein ≤ 2, même nom + pays) ; corrections dans `aliases.csv`.
- World Sailing : `datafeed.sailing.org/stats/api` (events, grade W→5, lieu) et `sailing.org/_feed/rankings` (pagination max 100).
  Classe de bateau quasi jamais renseignée chez WS, photos = placeholder → avatars à initiales.

- Photos : wmrt.com/skippers (page rendue en JS, liste relevée au navigateur dans wmrt_photos.txt). Crédit WMRT affiché ; demander l'accord du WMRT avant toute publication.
