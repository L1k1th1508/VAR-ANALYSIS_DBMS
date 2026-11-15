REVOKE ALL ON SCHEMA public FROM PUBLIC;
REVOKE ALL ON SCHEMA var FROM PUBLIC;
GRANT USAGE ON SCHEMA var TO app_reader,app_admin;
REVOKE ALL ON ALL TABLES IN SCHEMA var FROM PUBLIC,app_reader,app_admin;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA var FROM PUBLIC,app_reader,app_admin;
REVOKE EXECUTE ON ALL FUNCTIONS IN SCHEMA var FROM PUBLIC;
GRANT SELECT ON var.country,var.league,var.season,var.team,var.venue,var.referee,var.official_role,
    var.football_match,var.match_official,var.decision_type,var.decision_outcome,var.decision,
    var.decision_team,var.var_involvement,var.player,var.match_player,var.card_issued,var.added_time,
    var.v_match_catalog,var.v_import_quality,var.mv_referee_stat_summary TO app_reader;
GRANT SELECT,INSERT,UPDATE,DELETE ON var.country,var.league,var.season,var.team,var.venue,var.referee,
    var.football_match,var.match_official,var.decision,var.decision_team,var.var_involvement,
    var.player,var.match_player,var.card_issued,var.added_time TO app_admin;
GRANT SELECT ON var.official_role,var.decision_type,var.decision_outcome,var.v_match_catalog,
    var.v_import_quality,var.mv_referee_stat_summary TO app_admin;
GRANT SELECT,INSERT ON var.data_source,var.import_batch,var.source_record TO app_admin;
GRANT UPDATE(status,finished_at,extracted_count,accepted_count,rejected_count,error_summary) ON var.import_batch TO app_admin;
GRANT UPDATE(validation_status,validation_errors) ON var.source_record TO app_admin;
GRANT USAGE,SELECT ON ALL SEQUENCES IN SCHEMA var TO app_admin;
ALTER DEFAULT PRIVILEGES FOR ROLE db_owner IN SCHEMA var REVOKE ALL ON TABLES FROM PUBLIC;
ALTER DEFAULT PRIVILEGES FOR ROLE db_owner IN SCHEMA var REVOKE ALL ON SEQUENCES FROM PUBLIC;
ALTER DEFAULT PRIVILEGES FOR ROLE db_owner IN SCHEMA var REVOKE EXECUTE ON FUNCTIONS FROM PUBLIC;
-- Future objects receive explicit migration grants; no blanket future reader access to raw evidence.
