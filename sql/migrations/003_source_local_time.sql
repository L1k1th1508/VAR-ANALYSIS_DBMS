-- Approved source-precision amendment: date/clock are not an assumed UTC instant.
ALTER TABLE var.football_match ADD COLUMN match_date date;
ALTER TABLE var.football_match ADD COLUMN kickoff_local time;
ALTER TABLE var.football_match ADD COLUMN timezone_name text;
ALTER TABLE var.football_match ADD CONSTRAINT timezone_requires_local_time
    CHECK(timezone_name IS NULL OR (match_date IS NOT NULL AND kickoff_local IS NOT NULL));
ALTER TABLE var.football_match ADD CONSTRAINT no_assumed_kickoff_timezone
    CHECK(kickoff_at IS NULL OR timezone_name IS NOT NULL);
CREATE FUNCTION var.validate_match_timezone() RETURNS trigger LANGUAGE plpgsql SET search_path=var,pg_temp AS $$
BEGIN
    IF NEW.timezone_name IS NOT NULL AND NOT EXISTS(
        SELECT 1 FROM pg_catalog.pg_timezone_names WHERE name=NEW.timezone_name) THEN
        RAISE EXCEPTION 'Unknown timezone name' USING ERRCODE='23514';
    END IF;
    IF NEW.kickoff_at IS NOT NULL AND NEW.kickoff_at IS DISTINCT FROM
       ((NEW.match_date+NEW.kickoff_local) AT TIME ZONE NEW.timezone_name) THEN
        RAISE EXCEPTION 'Kickoff instant differs from verified local date/time/zone' USING ERRCODE='23514';
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER validate_timezone BEFORE INSERT OR UPDATE ON var.football_match
    FOR EACH ROW EXECUTE FUNCTION var.validate_match_timezone();
REVOKE EXECUTE ON FUNCTION var.validate_match_timezone() FROM PUBLIC;
CREATE INDEX ON var.football_match(season_id,match_date);
-- Explicit projection retains view compatibility; these fields are appended at the end.
CREATE OR REPLACE VIEW var.v_match_catalog AS
SELECT m.match_id,m.season_id,m.venue_id,m.home_team_id,m.away_team_id,m.kickoff_at,m.status,
       m.home_score,m.away_score,m.home_shootout_score,m.away_shootout_score,m.source_record_id,
       h.name home_team,a.name away_team,s.label season,l.league_id,l.name league,
       v.name venue,r.name main_referee,m.match_date,m.kickoff_local,m.timezone_name
FROM var.football_match m JOIN var.team h ON h.team_id=m.home_team_id JOIN var.team a ON a.team_id=m.away_team_id
JOIN var.season s USING(season_id) JOIN var.league l USING(league_id)
LEFT JOIN var.venue v USING(venue_id)
LEFT JOIN var.match_official mo ON mo.match_id=m.match_id AND mo.role_code='MAIN_REFEREE'
LEFT JOIN var.referee r USING(referee_id);
