-- Run once as DB owner through a private, TLS-verified admin session.
-- Create ecoroute_writer using a locally generated password, stored in Secrets Manager.
-- Do not put a password in this file, shell history or chat.
CREATE TABLE IF NOT EXISTS route_reports (
    report_id TEXT PRIMARY KEY,
    report_date DATE NOT NULL,
    mode TEXT NOT NULL,
    provider TEXT NOT NULL,
    candidate_count INTEGER NOT NULL CHECK (candidate_count BETWEEN 1 AND 6),
    report_json TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS route_reports_date ON route_reports (report_date);
REVOKE ALL ON SCHEMA public FROM PUBLIC;
GRANT USAGE ON SCHEMA public TO ecoroute_writer;
GRANT SELECT, INSERT, DELETE ON route_reports TO ecoroute_writer;
-- Writer cannot UPDATE reports, create tables/users, or access other application stores.
