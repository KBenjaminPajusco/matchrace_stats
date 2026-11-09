-- une ligne par skipper et par match
CREATE VIEW sides AS
SELECT m.id match_id, m.event_id, e.year, COALESCE(m.date,e.date_start) date, m.stage, m.stage_kind, m.flight,
  m.port_key key, m.port_name name, 'blue' colour, 'port' entry, m.stbd_key opp_key, m.stbd_name opp_name,
  CASE m.winner WHEN 'port' THEN 'W' WHEN 'stbd' THEN 'L' WHEN 'draw' THEN 'D' ELSE '?' END res,
  m.port_raw raw, m.pen_port penalty, m.pen_stbd opp_penalty
FROM matches m JOIN events e ON e.id=m.event_id
UNION ALL
SELECT m.id, m.event_id, e.year, COALESCE(m.date,e.date_start), m.stage, m.stage_kind, m.flight,
  m.stbd_key, m.stbd_name, 'yellow', 'stbd', m.port_key, m.port_name,
  CASE m.winner WHEN 'stbd' THEN 'W' WHEN 'port' THEN 'L' WHEN 'draw' THEN 'D' ELSE '?' END,
  m.stbd_raw, m.pen_stbd, m.pen_port
FROM matches m JOIN events e ON e.id=m.event_id;

CREATE VIEW skipper_names AS
SELECT key, name, n FROM (SELECT key, name, COUNT(*) n,
  ROW_NUMBER() OVER (PARTITION BY key ORDER BY COUNT(*) DESC) rn FROM sides GROUP BY key, name) WHERE rn=1;

CREATE VIEW skipper_country AS
SELECT name_key key, country FROM (SELECT name_key, country, ROW_NUMBER() OVER (PARTITION BY name_key ORDER BY COUNT(*) DESC) rn
  FROM entries WHERE country IS NOT NULL GROUP BY name_key, country) WHERE rn=1;

CREATE VIEW skippers AS
SELECT s.key, n.name, c.country,
  COUNT(DISTINCT s.event_id) events, COUNT(*) matches,
  SUM(res='W') wins, SUM(res='L') losses, SUM(res='D') draws,
  ROUND(100.0*SUM(res='W')/NULLIF(SUM(res IN ('W','L')),0),1) win_pct,
  SUM(colour='yellow') yellow_m, SUM(colour='yellow' AND res='W') yellow_w,
  ROUND(100.0*SUM(colour='yellow' AND res='W')/NULLIF(SUM(colour='yellow' AND res IN ('W','L')),0),1) yellow_pct,
  SUM(colour='blue') blue_m, SUM(colour='blue' AND res='W') blue_w,
  ROUND(100.0*SUM(colour='blue' AND res='W')/NULLIF(SUM(colour='blue' AND res IN ('W','L')),0),1) blue_pct,
  SUM(stage_kind='round_robin') rr_m, SUM(stage_kind='round_robin' AND res='W') rr_w,
  SUM(stage_kind<>'round_robin') ko_m, SUM(stage_kind<>'round_robin' AND res='W') ko_w,
  SUM(penalty) penalised, SUM(opp_penalty) opp_penalised,
  (SELECT COUNT(*) FROM entries x WHERE x.name_key=s.key AND x.final_rank=1) titles,
  (SELECT COUNT(*) FROM entries x WHERE x.name_key=s.key AND x.final_rank<=3) podiums,
  (SELECT MIN(final_rank) FROM entries x WHERE x.name_key=s.key) best_rank,
  MIN(s.year) first_year, MAX(s.year) last_year
FROM sides s JOIN skipper_names n ON n.key=s.key LEFT JOIN skipper_country c ON c.key=s.key
GROUP BY s.key;
