-- Safe privilege rollback: preserve tables and evidence; leave owner maintenance available.
REVOKE ALL ON ALL TABLES IN SCHEMA var FROM app_reader,app_admin;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA var FROM app_reader,app_admin;
REVOKE USAGE ON SCHEMA var FROM app_reader,app_admin;
