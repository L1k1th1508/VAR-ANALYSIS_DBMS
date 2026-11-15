CREATE SCHEMA IF NOT EXISTS var AUTHORIZATION db_owner;
SET search_path TO var, public;

CREATE TABLE schema_migration (
    version text PRIMARY KEY, checksum text NOT NULL, applied_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE data_source (
    data_source_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    source_code text NOT NULL UNIQUE, name text NOT NULL, reference_url text NOT NULL,
    license_reference text, attribution_text text,
    source_kind text NOT NULL CHECK (source_kind IN ('provider','manual'))
);
CREATE TABLE import_batch (
    import_batch_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    data_source_id bigint NOT NULL REFERENCES data_source,
    input_fingerprint text NOT NULL, transform_version text NOT NULL,
    started_at timestamptz NOT NULL DEFAULT now(), finished_at timestamptz,
    status text NOT NULL CHECK (status IN ('pending','success','failed')),
    extracted_count integer NOT NULL DEFAULT 0 CHECK (extracted_count >= 0),
    accepted_count integer NOT NULL DEFAULT 0 CHECK (accepted_count >= 0),
    rejected_count integer NOT NULL DEFAULT 0 CHECK (rejected_count >= 0), error_summary text,
    UNIQUE(data_source_id,input_fingerprint,transform_version),
    CHECK (finished_at IS NULL OR finished_at >= started_at)
);
CREATE TABLE source_record (
    source_record_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    import_batch_id bigint NOT NULL REFERENCES import_batch,
    entity_kind text NOT NULL, external_key text, record_locator text NOT NULL,
    payload_sha256 text NOT NULL CHECK (length(payload_sha256)=64), raw_payload jsonb NOT NULL,
    captured_at timestamptz NOT NULL DEFAULT now(),
    validation_status text NOT NULL CHECK (validation_status IN ('pending','accepted','rejected','unmapped')),
    validation_errors jsonb,
    UNIQUE(import_batch_id, record_locator)
);
CREATE TABLE country (
    country_id uuid PRIMARY KEY, name text NOT NULL, iso_code text UNIQUE,
    source_record_id bigint NOT NULL REFERENCES source_record
);
CREATE TABLE league (
    league_id uuid PRIMARY KEY, country_id uuid REFERENCES country, name text NOT NULL,
    competition_kind text NOT NULL,
    source_record_id bigint NOT NULL REFERENCES source_record
);
CREATE TABLE season (
    season_id uuid PRIMARY KEY, league_id uuid NOT NULL REFERENCES league, label text NOT NULL,
    starts_on date, ends_on date, source_record_id bigint NOT NULL REFERENCES source_record,
    UNIQUE(league_id,label), CHECK(starts_on IS NULL OR ends_on IS NULL OR starts_on <= ends_on)
);
CREATE TABLE team (
    team_id uuid PRIMARY KEY, country_id uuid REFERENCES country, name text NOT NULL,
    source_record_id bigint NOT NULL REFERENCES source_record
);
CREATE TABLE venue (
    venue_id uuid PRIMARY KEY, country_id uuid REFERENCES country, name text NOT NULL, city text,
    source_record_id bigint NOT NULL REFERENCES source_record
);
CREATE TABLE referee (
    referee_id uuid PRIMARY KEY, country_id uuid REFERENCES country, name text NOT NULL,
    source_record_id bigint NOT NULL REFERENCES source_record
);
CREATE TABLE official_role (
    role_code text PRIMARY KEY, label text NOT NULL, var_eligible boolean NOT NULL DEFAULT false
);
CREATE TABLE football_match (
    match_id uuid PRIMARY KEY, season_id uuid NOT NULL REFERENCES season, venue_id uuid REFERENCES venue,
    home_team_id uuid NOT NULL REFERENCES team, away_team_id uuid NOT NULL REFERENCES team,
    kickoff_at timestamptz,
    status text NOT NULL CHECK(status IN ('scheduled','live','completed','postponed','cancelled','abandoned')),
    home_score smallint CHECK(home_score>=0), away_score smallint CHECK(away_score>=0),
    home_shootout_score smallint CHECK(home_shootout_score>=0),
    away_shootout_score smallint CHECK(away_shootout_score>=0),
    source_record_id bigint NOT NULL REFERENCES source_record,
    CHECK(home_team_id<>away_team_id),
    CHECK((home_score IS NULL)=(away_score IS NULL)),
    CHECK((home_shootout_score IS NULL)=(away_shootout_score IS NULL)),
    CHECK(status<>'completed' OR (home_score IS NOT NULL AND away_score IS NOT NULL))
);
CREATE TABLE match_official (
    match_id uuid NOT NULL REFERENCES football_match,
    role_code text NOT NULL REFERENCES official_role, slot_no smallint NOT NULL CHECK(slot_no>0),
    referee_id uuid NOT NULL REFERENCES referee,
    source_record_id bigint NOT NULL REFERENCES source_record,
    PRIMARY KEY(match_id,role_code,slot_no)
);
CREATE UNIQUE INDEX one_main_referee ON match_official(match_id) WHERE role_code='MAIN_REFEREE';
CREATE TABLE decision_type (decision_type_code text PRIMARY KEY, label text NOT NULL);
CREATE TABLE decision_outcome (
    outcome_code text PRIMARY KEY, label text NOT NULL,
    outcome_scope text NOT NULL CHECK(outcome_scope IN ('decision','var'))
);
CREATE TABLE decision (
    decision_id uuid PRIMARY KEY, match_id uuid NOT NULL REFERENCES football_match,
    decision_type_code text NOT NULL REFERENCES decision_type,
    outcome_code text REFERENCES decision_outcome,
    period_code smallint NOT NULL CHECK(period_code BETWEEN 1 AND 5),
    minute integer CHECK(minute>=0), second smallint CHECK(second BETWEEN 0 AND 59),
    stoppage_minute integer CHECK(stoppage_minute>=0), source_order integer CHECK(source_order>=0),
    official_role_code text, official_slot_no smallint, description text,
    source_record_id bigint NOT NULL REFERENCES source_record,
    CHECK((official_role_code IS NULL)=(official_slot_no IS NULL)),
    FOREIGN KEY(match_id,official_role_code,official_slot_no)
        REFERENCES match_official(match_id,role_code,slot_no)
);
CREATE TABLE decision_team (
    decision_id uuid NOT NULL REFERENCES decision, team_id uuid NOT NULL REFERENCES team,
    involvement_code text NOT NULL CHECK(involvement_code IN ('recorded_team','opponent','beneficiary','penalized')),
    source_record_id bigint NOT NULL REFERENCES source_record,
    PRIMARY KEY(decision_id,team_id)
);
CREATE TABLE var_involvement (
    var_involvement_id uuid PRIMARY KEY, decision_id uuid NOT NULL REFERENCES decision,
    review_kind text NOT NULL CHECK(review_kind IN ('check','review')),
    outcome_code text REFERENCES decision_outcome,
    official_role_code text REFERENCES official_role, official_slot_no smallint,
    duration_seconds numeric CHECK(duration_seconds>=0),
    period_code smallint CHECK(period_code BETWEEN 1 AND 5),
    minute integer CHECK(minute>=0), second smallint CHECK(second BETWEEN 0 AND 59),
    stoppage_minute integer CHECK(stoppage_minute>=0), source_order integer CHECK(source_order>=0),
    description text, source_record_id bigint NOT NULL REFERENCES source_record,
    CHECK((official_role_code IS NULL)=(official_slot_no IS NULL)),
    CHECK(official_slot_no IS NULL OR official_slot_no>0)
);
CREATE TABLE player (
    player_id uuid PRIMARY KEY, country_id uuid REFERENCES country, name text NOT NULL, date_of_birth date,
    source_record_id bigint NOT NULL REFERENCES source_record
);
CREATE TABLE match_player (
    match_id uuid NOT NULL REFERENCES football_match, player_id uuid NOT NULL REFERENCES player,
    team_id uuid NOT NULL REFERENCES team, source_record_id bigint NOT NULL REFERENCES source_record,
    PRIMARY KEY(match_id,player_id)
);
CREATE TABLE card_issued (
    card_id uuid PRIMARY KEY, match_id uuid NOT NULL, player_id uuid NOT NULL,
    card_type text NOT NULL CHECK(card_type IN ('yellow','second_yellow','red')),
    period_code smallint NOT NULL CHECK(period_code BETWEEN 1 AND 5),
    minute integer CHECK(minute>=0), second smallint CHECK(second BETWEEN 0 AND 59),
    stoppage_minute integer CHECK(stoppage_minute>=0), source_order integer CHECK(source_order>=0),
    official_role_code text, official_slot_no smallint,
    source_record_id bigint NOT NULL REFERENCES source_record,
    CHECK((official_role_code IS NULL)=(official_slot_no IS NULL)),
    FOREIGN KEY(match_id,player_id) REFERENCES match_player(match_id,player_id),
    FOREIGN KEY(match_id,official_role_code,official_slot_no)
        REFERENCES match_official(match_id,role_code,slot_no)
);
CREATE TABLE added_time (
    match_id uuid NOT NULL REFERENCES football_match, period_code smallint NOT NULL CHECK(period_code BETWEEN 1 AND 4),
    announced_minutes integer NOT NULL CHECK(announced_minutes>=0),
    announced_seconds smallint CHECK(announced_seconds BETWEEN 0 AND 59),
    source_record_id bigint NOT NULL REFERENCES source_record,
    PRIMARY KEY(match_id,period_code)
);

CREATE FUNCTION assert_participant() RETURNS trigger LANGUAGE plpgsql SET search_path=var,pg_temp AS $$
DECLARE m football_match; mid uuid;
BEGIN
    IF TG_TABLE_NAME='decision_team' THEN
        SELECT match_id INTO mid FROM decision WHERE decision_id=NEW.decision_id FOR SHARE;
    ELSE mid:=NEW.match_id; END IF;
    SELECT * INTO m FROM football_match WHERE match_id=mid FOR SHARE;
    IF m.match_id IS NULL OR NEW.team_id NOT IN (m.home_team_id,m.away_team_id) THEN
        RAISE EXCEPTION 'Team does not participate in the match' USING ERRCODE='23514';
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER validate_match_player BEFORE INSERT OR UPDATE ON match_player
    FOR EACH ROW EXECUTE FUNCTION assert_participant();
CREATE TRIGGER validate_decision_team BEFORE INSERT OR UPDATE ON decision_team
    FOR EACH ROW EXECUTE FUNCTION assert_participant();

CREATE FUNCTION assert_var() RETURNS trigger LANGUAGE plpgsql SET search_path=var,pg_temp AS $$
DECLARE mid uuid; eligible boolean; scope text;
BEGIN
    SELECT match_id INTO mid FROM decision WHERE decision_id=NEW.decision_id FOR SHARE;
    IF NEW.official_role_code IS NOT NULL THEN
        SELECT r.var_eligible INTO eligible FROM match_official mo JOIN official_role r USING(role_code)
        WHERE mo.match_id=mid AND mo.role_code=NEW.official_role_code AND mo.slot_no=NEW.official_slot_no
        FOR SHARE OF mo,r;
        IF eligible IS DISTINCT FROM true THEN
            RAISE EXCEPTION 'VAR attribution requires a VAR-eligible appointment in the same match'
                USING ERRCODE='23514';
        END IF;
    END IF;
    IF NEW.outcome_code IS NOT NULL THEN
        SELECT outcome_scope INTO scope FROM decision_outcome WHERE outcome_code=NEW.outcome_code FOR SHARE;
        IF scope IS DISTINCT FROM 'var' THEN
            RAISE EXCEPTION 'Expected a VAR outcome' USING ERRCODE='23514';
        END IF;
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER validate_var BEFORE INSERT OR UPDATE ON var_involvement FOR EACH ROW EXECUTE FUNCTION assert_var();

CREATE FUNCTION guard_decision() RETURNS trigger LANGUAGE plpgsql SET search_path=var,pg_temp AS $$
DECLARE scope text; m football_match;
BEGIN
    SELECT * INTO m FROM football_match WHERE match_id=NEW.match_id FOR SHARE;
    IF NEW.outcome_code IS NOT NULL THEN
        SELECT outcome_scope INTO scope FROM decision_outcome WHERE outcome_code=NEW.outcome_code FOR SHARE;
        IF scope IS DISTINCT FROM 'decision' THEN
            RAISE EXCEPTION 'Expected a decision outcome' USING ERRCODE='23514';
        END IF;
    END IF;
    IF TG_OP='UPDATE' AND NEW.match_id<>OLD.match_id THEN
        IF EXISTS(SELECT 1 FROM decision_team WHERE decision_id=OLD.decision_id
                  AND team_id NOT IN (m.home_team_id,m.away_team_id))
           OR EXISTS(SELECT 1 FROM var_involvement v WHERE v.decision_id=OLD.decision_id
                     AND v.official_role_code IS NOT NULL AND NOT EXISTS(
                         SELECT 1 FROM match_official mo WHERE mo.match_id=NEW.match_id
                         AND mo.role_code=v.official_role_code AND mo.slot_no=v.official_slot_no)) THEN
            RAISE EXCEPTION 'Decision move invalidates existing relationships' USING ERRCODE='23514';
        END IF;
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER validate_decision BEFORE INSERT OR UPDATE ON decision FOR EACH ROW EXECUTE FUNCTION guard_decision();

CREATE FUNCTION guard_match() RETURNS trigger LANGUAGE plpgsql SET search_path=var,pg_temp AS $$
BEGIN
    IF EXISTS(SELECT 1 FROM match_player WHERE match_id=OLD.match_id
              AND team_id NOT IN (NEW.home_team_id,NEW.away_team_id))
       OR EXISTS(SELECT 1 FROM decision_team dt JOIN decision d USING(decision_id)
                 WHERE d.match_id=OLD.match_id AND dt.team_id NOT IN (NEW.home_team_id,NEW.away_team_id)) THEN
        RAISE EXCEPTION 'Match team change invalidates recorded participants' USING ERRCODE='23514';
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER protect_match_participants BEFORE UPDATE OF home_team_id,away_team_id ON football_match
    FOR EACH ROW EXECUTE FUNCTION guard_match();

CREATE FUNCTION guard_appointment() RETURNS trigger LANGUAGE plpgsql SET search_path=var,pg_temp AS $$
BEGIN
    IF EXISTS(SELECT 1 FROM var_involvement v JOIN decision d USING(decision_id)
              WHERE d.match_id=OLD.match_id AND v.official_role_code=OLD.role_code
              AND v.official_slot_no=OLD.slot_no) THEN
        IF TG_OP='DELETE' THEN
            RAISE EXCEPTION 'Appointment is referenced by a VAR record' USING ERRCODE='23503';
        ELSIF (NEW.match_id,NEW.role_code,NEW.slot_no) IS DISTINCT FROM (OLD.match_id,OLD.role_code,OLD.slot_no) THEN
            RAISE EXCEPTION 'Appointment change invalidates VAR attribution' USING ERRCODE='23514';
        END IF;
    END IF;
    IF TG_OP='DELETE' THEN RETURN OLD; END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER protect_appointment BEFORE DELETE OR UPDATE ON match_official
    FOR EACH ROW EXECUTE FUNCTION guard_appointment();
CREATE FUNCTION guard_role() RETURNS trigger LANGUAGE plpgsql SET search_path=var,pg_temp AS $$
BEGIN
    IF NOT NEW.var_eligible AND EXISTS(SELECT 1 FROM var_involvement WHERE official_role_code=OLD.role_code) THEN
        RAISE EXCEPTION 'Role is in use by VAR records' USING ERRCODE='23514';
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER protect_role BEFORE UPDATE ON official_role FOR EACH ROW EXECUTE FUNCTION guard_role();
CREATE FUNCTION guard_outcome() RETURNS trigger LANGUAGE plpgsql SET search_path=var,pg_temp AS $$
BEGIN
    IF NEW.outcome_scope<>OLD.outcome_scope AND (
        EXISTS(SELECT 1 FROM decision WHERE outcome_code=OLD.outcome_code) OR
        EXISTS(SELECT 1 FROM var_involvement WHERE outcome_code=OLD.outcome_code)) THEN
        RAISE EXCEPTION 'Outcome scope is already in use' USING ERRCODE='23514';
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER protect_outcome BEFORE UPDATE ON decision_outcome FOR EACH ROW EXECUTE FUNCTION guard_outcome();
CREATE FUNCTION immutable_evidence() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF (NEW.import_batch_id,NEW.entity_kind,NEW.external_key,NEW.record_locator,NEW.payload_sha256,
        NEW.raw_payload,NEW.captured_at) IS DISTINCT FROM
       (OLD.import_batch_id,OLD.entity_kind,OLD.external_key,OLD.record_locator,OLD.payload_sha256,
        OLD.raw_payload,OLD.captured_at) THEN
        RAISE EXCEPTION 'Original source evidence is immutable' USING ERRCODE='23514';
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER protect_raw_evidence BEFORE UPDATE ON source_record FOR EACH ROW EXECUTE FUNCTION immutable_evidence();

INSERT INTO official_role VALUES
('MAIN_REFEREE','Main referee',false),('ASSISTANT_1','Assistant referee 1',false),
('ASSISTANT_2','Assistant referee 2',false),('FOURTH_OFFICIAL','Fourth official',false),
('VAR','Video assistant referee',true),('AVAR','Assistant VAR',true);
INSERT INTO decision_type VALUES ('GOAL','Recorded goal'),('PENALTY','Penalty shot'),('FOUL','Recorded foul');
INSERT INTO decision_outcome VALUES ('GOAL','Goal','decision'),('NO_GOAL','No goal','decision'),
('UPHELD','Upheld','var'),('OVERTURNED','Overturned','var');

CREATE INDEX ON season(league_id);
CREATE INDEX ON football_match(season_id,kickoff_at);
CREATE INDEX ON football_match(home_team_id);
CREATE INDEX ON football_match(away_team_id);
CREATE INDEX ON match_official(referee_id,match_id);
CREATE INDEX ON decision(match_id,decision_type_code,period_code,minute,second);
CREATE INDEX ON decision_team(team_id);
CREATE INDEX ON var_involvement(decision_id,outcome_code);
CREATE INDEX ON match_player(player_id);
CREATE INDEX ON match_player(team_id);
CREATE INDEX ON card_issued(match_id,player_id,card_type);
CREATE INDEX ON import_batch(data_source_id,started_at);
CREATE INDEX ON source_record(import_batch_id,external_key);

CREATE VIEW v_match_catalog AS
SELECT m.*, h.name home_team, a.name away_team, s.label season, l.league_id, l.name league,
       v.name venue, r.name main_referee
FROM football_match m JOIN team h ON h.team_id=m.home_team_id JOIN team a ON a.team_id=m.away_team_id
JOIN season s USING(season_id) JOIN league l USING(league_id)
LEFT JOIN venue v USING(venue_id)
LEFT JOIN match_official mo ON mo.match_id=m.match_id AND mo.role_code='MAIN_REFEREE'
LEFT JOIN referee r USING(referee_id);
CREATE VIEW v_import_quality AS
SELECT b.*,ds.name source,ds.reference_url FROM import_batch b JOIN data_source ds USING(data_source_id);

CREATE MATERIALIZED VIEW mv_referee_stat_summary AS
WITH decisions AS (
    SELECT match_id,count(*) decision_count,count(*) FILTER(WHERE decision_type_code='PENALTY') penalties
    FROM decision GROUP BY match_id
), cards AS (
    SELECT match_id,count(*) FILTER(WHERE card_type='yellow') yellow_cards,
        count(*) FILTER(WHERE card_type='second_yellow') second_yellow_dismissals,
        count(*) FILTER(WHERE card_type='red') direct_red_cards FROM card_issued GROUP BY match_id
), reviews AS (
    SELECT d.match_id,count(*) FILTER(WHERE v.review_kind='review') reviews,
        count(*) FILTER(WHERE v.review_kind='check') checks,
        count(*) FILTER(WHERE v.review_kind='review' AND v.outcome_code IN ('UPHELD','OVERTURNED')) known_outcomes,
        count(*) FILTER(WHERE v.review_kind='review' AND v.outcome_code='OVERTURNED') overturned
    FROM var_involvement v JOIN decision d USING(decision_id) GROUP BY d.match_id
)
SELECT mo.referee_id,m.season_id,count(*) matches,
    sum(coalesce(d.decision_count,0)) decisions,sum(coalesce(d.penalties,0)) penalties,
    sum(coalesce(c.yellow_cards,0)) yellow_cards,sum(coalesce(c.second_yellow_dismissals,0)) second_yellow_dismissals,
    sum(coalesce(c.direct_red_cards,0)) direct_red_cards,sum(coalesce(v.reviews,0)) reviews,
    sum(coalesce(v.checks,0)) checks,sum(coalesce(v.known_outcomes,0)) known_outcomes,
    sum(coalesce(v.overturned,0)) overturned,now() refreshed_at
FROM match_official mo JOIN football_match m USING(match_id)
LEFT JOIN decisions d USING(match_id) LEFT JOIN cards c USING(match_id) LEFT JOIN reviews v USING(match_id)
WHERE mo.role_code='MAIN_REFEREE' GROUP BY mo.referee_id,m.season_id;
CREATE UNIQUE INDEX ON mv_referee_stat_summary(referee_id,season_id);
