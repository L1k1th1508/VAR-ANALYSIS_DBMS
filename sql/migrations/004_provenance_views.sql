CREATE VIEW var.v_source_provenance AS
SELECT sr.source_record_id,sr.import_batch_id,sr.entity_kind,sr.external_key,sr.record_locator,
       sr.payload_sha256,sr.captured_at,sr.validation_status,ds.name source,ds.reference_url
FROM var.source_record sr JOIN var.import_batch b USING(import_batch_id)
JOIN var.data_source ds USING(data_source_id);
CREATE VIEW var.v_record_quality AS
SELECT source_record_id,import_batch_id,entity_kind,record_locator,validation_status,validation_errors
FROM var.source_record;
GRANT SELECT ON var.v_source_provenance,var.v_record_quality TO app_reader,app_admin;
