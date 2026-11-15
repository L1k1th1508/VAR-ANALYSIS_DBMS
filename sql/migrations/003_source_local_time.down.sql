-- Destructive field removal: requires explicit approval outside a disposable test database.
DROP VIEW var.v_match_catalog;
DROP TRIGGER validate_timezone ON var.football_match;
DROP FUNCTION var.validate_match_timezone();
ALTER TABLE var.football_match DROP COLUMN match_date, DROP COLUMN kickoff_local, DROP COLUMN timezone_name;
CREATE VIEW var.v_match_catalog AS
SELECT m.*,h.name home_team,a.name away_team,s.label season,l.league_id,l.name league,
       v.name venue,r.name main_referee
FROM var.football_match m JOIN var.team h ON h.team_id=m.home_team_id JOIN var.team a ON a.team_id=m.away_team_id
JOIN var.season s USING(season_id) JOIN var.league l USING(league_id)
LEFT JOIN var.venue v USING(venue_id)
LEFT JOIN var.match_official mo ON mo.match_id=m.match_id AND mo.role_code='MAIN_REFEREE'
LEFT JOIN var.referee r USING(referee_id);
GRANT SELECT ON var.v_match_catalog TO app_reader,app_admin;
