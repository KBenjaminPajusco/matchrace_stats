CREATE TABLE events(id INTEGER PRIMARY KEY, year INT, slug TEXT, title TEXT, url TEXT,
  date_start TEXT, date_end TEXT, boat TEXT, description TEXT, women INT, youth INT);
CREATE TABLE entries(event_id INT REFERENCES events(id), name TEXT, name_key TEXT, club TEXT, country TEXT, final_rank INT, crew TEXT);
-- port = entrée bâbord = pavillon BLEU ; stbd = entrée tribord = pavillon JAUNE (RRS App. C)
CREATE TABLE matches(id INTEGER PRIMARY KEY, event_id INT REFERENCES events(id), match_no INT,
  stage TEXT, stage_kind TEXT, date TEXT, flight INT,
  port_name TEXT, port_key TEXT, stbd_name TEXT, stbd_key TEXT,
  port_raw TEXT, stbd_raw TEXT, port_pts REAL, stbd_pts REAL,
  winner TEXT,  -- port | stbd | draw | unknown
  pen_port INT, pen_stbd INT,
  ts TEXT, tz TEXT);  -- horodatage local du résultat (fil live feed.php) + décalage UTC
CREATE INDEX ix_m_ev ON matches(event_id); CREATE INDEX ix_m_p ON matches(port_key); CREATE INDEX ix_m_s ON matches(stbd_key);
CREATE INDEX ix_e_k ON entries(name_key);
