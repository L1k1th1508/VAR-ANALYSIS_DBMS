-- Row locks require UPDATE privilege, but lookup vocabularies must remain read-only
-- to app_admin. Only these existing validation triggers execute as their owner.
-- Both have a fixed trusted search_path, contain no dynamic SQL and expose no
-- callable mutation API. PUBLIC EXECUTE remains revoked by migration 002.
ALTER FUNCTION var.guard_decision() SECURITY DEFINER;
ALTER FUNCTION var.assert_var() SECURITY DEFINER;
