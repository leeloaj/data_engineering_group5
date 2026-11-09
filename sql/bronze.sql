CREATE SCHEMA IF NOT EXISTS bronze;

CREATE TABLE IF NOT EXISTS bronze.chart_entries (
    source text NOT NULL,
    ingested_at timestamptz NOT NULL,
    input_file text NOT NULL,
    input_sha256 text NOT NULL,
    chart_date date NOT NULL,
    region text NOT NULL,
    chart_type text NOT NULL,
    spotify_track_id text NOT NULL,
    rank integer NOT NULL CHECK (rank > 0),
    streams bigint CHECK (streams >= 0),
    raw_row jsonb NOT NULL,
    PRIMARY KEY (source, chart_date, region, chart_type, spotify_track_id)
);

CREATE INDEX IF NOT EXISTS chart_entries_track_idx
    ON bronze.chart_entries (spotify_track_id);

CREATE TABLE IF NOT EXISTS bronze.track_enrichment (
    source text NOT NULL,
    ingested_at timestamptz NOT NULL,
    input_date date NOT NULL,
    spotify_track_id text NOT NULL,
    market text NOT NULL,
    status text NOT NULL CHECK (status IN ('found', 'missing')),
    raw_json jsonb,
    PRIMARY KEY (source, input_date, market, spotify_track_id)
);

CREATE INDEX IF NOT EXISTS track_enrichment_lookup_idx
    ON bronze.track_enrichment (source, market, spotify_track_id);
