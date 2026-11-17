# Technology Justification: PostgreSQL vs. MongoDB in VAR Decision Analytics

## 1. System Overview
The **FIFA World Cup 2022 VAR & Decision Analytics System** handles two distinct tiers of database storage:
1. **Relational Tier (PostgreSQL 16)**: Strict relational facts, schema integrity, and official records.
2. **Document / NoSQL Tier (MongoDB 7.0)**: Semi-structured telemetry, sensor data, and video review annotations.

---

## 2. Relational Database: PostgreSQL 16

### Why PostgreSQL?
- **Third Normal Form (3NF) & Referential Integrity**: Football matches, official appointments, team participation, and disciplinary cards share strict relational dependencies. Foreign keys (`match_id`, `referee_id`, `player_id`) prevent orphaned or fabricated records.
- **ACID Transaction Guarantees**: When a match official is updated or a decision is modified by an administrator, PostgreSQL ensures transactional consistency using row-level locking (`FOR SHARE` / `FOR UPDATE`).
- **Complex Analytical Joins & Triggers**:
  - Multi-table joins across 20 relational entities.
  - PL/pgSQL triggers (`assert_participant`, `assert_var`, `guard_decision`) guarantee that decisions, cards, and video reviews strictly correspond to registered players and eligible officials assigned to that specific match.
  - Materialized views (`mv_referee_stat_summary`) provide pre-computed analytics over large join graphs with index-backed freshness.

---

## 3. NoSQL Database: MongoDB 7.0

### Why MongoDB?
- **Semi-Structured VAR Telemetry**: High-resolution video review logs include variable metadata:
  - Ball sensor frequencies (e.g., 500 Hz inertial measurement units in Adidas Al Rihla).
  - Multi-angle camera coordinates, review stoppage timestamps, and referee headset audio confirmation tags.
  - Rigid relational tables would require dozens of sparse, nullable columns or frequent schema alterations (`ALTER TABLE`) to adapt to new camera/sensor vendors.
- **Flexible Tagging & Hierarchical Indexing**:
  - Sub-document fields like `telemetry.ball_curvature_margin_mm` and multi-key array indexes on `tags: ["goal", "sensor_check", "overturned"]` allow instant filtering without schema restructuring.
- **High-Throughput Ingestion**:
  - Live in-game telemetry events arrive in bursts. MongoDB's document model natively ingests JSON objects with minimal serialization overhead.

---

## 4. Comparison Summary

| Metric / Requirement | PostgreSQL 16 (Relational) | MongoDB 7.0 (NoSQL) |
| :--- | :--- | :--- |
| **Primary Role** | Core operational facts, official appointments, 3NF schema | Sensor telemetry, VAR review metadata, flexible event logs |
| **Schema Paradigm** | Fixed schema with declarative constraints & triggers | Dynamic schema, JSON/BSON document store |
| **Integrity Rules** | Composite PKs, foreign keys, CHECK constraints, triggers | Document schema validation, unique indexes on composite keys |
| **Query Pattern** | Multi-table JOINs, CTEs, window functions, aggregates | Key-value search, tag filtering, aggregation pipelines |
| **Transaction Model** | Full ACID with multi-table atomic transactions | Document-level ACID atomicity |
| **RUD Feature Support** | Admin service via SQLAlchemy (Create, Edit, Confirmed Delete) | `nosql_service.py` (`find`, `aggregate`, `$set`, `$addToSet`, `delete_one`) |
