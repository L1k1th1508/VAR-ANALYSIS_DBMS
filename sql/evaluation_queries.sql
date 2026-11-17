-- Read-only examples for psql. Run with the reader credential.
-- 1. JOIN: a match's season and participants.
SELECT m.match_date, l.name AS league, s.label AS season,
       h.name AS home, a.name AS away, m.home_score, m.away_score
FROM var.football_match m
JOIN var.season s USING (season_id)
JOIN var.league l USING (league_id)
JOIN var.team h ON h.team_id=m.home_team_id
JOIN var.team a ON a.team_id=m.away_team_id
ORDER BY m.match_date LIMIT 10;

-- 2. Correlated subquery: count decisions for each match, including zero.
SELECT m.match_id,
       (SELECT count(*) FROM var.decision d WHERE d.match_id=m.match_id) AS decisions
FROM var.football_match m ORDER BY decisions DESC LIMIT 10;

-- 3. Nested subquery: referees with above-average match responsibilities.
SELECT r.name, x.matches FROM var.referee r
JOIN (SELECT referee_id,count(*) matches FROM var.match_official
      WHERE role_code='MAIN_REFEREE' GROUP BY referee_id) x USING(referee_id)
WHERE x.matches > (SELECT avg(matches) FROM
  (SELECT count(*) matches FROM var.match_official WHERE role_code='MAIN_REFEREE'
   GROUP BY referee_id) counts)
ORDER BY x.matches DESC;

-- 4. CTE and window function: ranking within each season, preserving ties.
WITH responsibilities AS (
  SELECT referee_id,m.season_id,count(*) matches
  FROM var.match_official mo JOIN var.football_match m USING(match_id)
  WHERE role_code='MAIN_REFEREE' GROUP BY referee_id,m.season_id
)
SELECT r.name,s.label,x.matches,
       dense_rank() OVER (PARTITION BY x.season_id ORDER BY x.matches DESC) rank
FROM responsibilities x JOIN var.referee r USING(referee_id)
JOIN var.season s USING(season_id) ORDER BY s.label,rank;

-- 5. Known-outcome denominator. Unknowns excluded; no known reviews returns NULL.
SELECT count(*) FILTER(WHERE outcome_code='OVERTURNED') AS overturned,
       count(*) FILTER(WHERE outcome_code IN ('UPHELD','OVERTURNED')) AS known,
       count(*) FILTER(WHERE outcome_code IS NULL) AS unknown,
       100.0*count(*) FILTER(WHERE outcome_code='OVERTURNED') /
       nullif(count(*) FILTER(WHERE outcome_code IN ('UPHELD','OVERTURNED')),0) AS percent
FROM var.var_involvement WHERE review_kind='review';

-- 6. Catalog introspection: show actual enforced constraints rather than a picture.
SELECT conrelid::regclass AS table_name,conname,pg_get_constraintdef(oid)
FROM pg_constraint WHERE connamespace='var'::regnamespace ORDER BY 1,2;

-- 7. Plan evidence. ANALYZE executes this SELECT but never changes source records.
EXPLAIN (ANALYZE,BUFFERS)
SELECT * FROM var.decision
WHERE match_id=(SELECT match_id FROM var.football_match ORDER BY match_id LIMIT 1);
