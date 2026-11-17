-- ============================================================================
-- DATA QUALITY CHECKS
-- Component: Bronze & Warehouse Validation (Step 5)
-- Author: Johannes
-- Description: Automated SQL checks for grain uniqueness, null keys, and metric bounds.
--              Every query must return 0 rows for the pipeline check to pass.
-- ============================================================================

-- CHECK 1: Duplicate grain check in bronze.chart_entries
-- Objective: Ensure compliance with primary grain (1 source x 1 track x 1 region x 1 chart_type x 1 date).
-- Expected result: 0 rows.
SELECT
    source,
    spotify_track_id,
    region,
    chart_type,
    chart_date,
    COUNT(*) AS record_count
FROM bronze.chart_entries
GROUP BY source, spotify_track_id, region, chart_type, chart_date
HAVING COUNT(*) > 1;


-- CHECK 2: Required identity fields verification in bronze.chart_entries
-- Objective: Capture any anomalous records missing critical identity identifiers.
-- Expected result: 0 rows.
SELECT
    source,
    input_file,
    spotify_track_id,
    region,
    chart_date
FROM bronze.chart_entries
WHERE spotify_track_id IS NULL
   OR TRIM(spotify_track_id) = ''
   OR chart_date IS NULL
   OR region IS NULL
   OR TRIM(region) = '';


-- CHECK 3: Non-negative streams and valid chart rank enforcement
-- Objective: Validate that incoming stream counts are non-negative and rank is within 1..200.
-- Expected result: 0 rows.
SELECT
    source,
    spotify_track_id,
    region,
    chart_type,
    chart_date,
    rank,
    streams
FROM bronze.chart_entries
WHERE streams < 0
   OR rank < 1
   OR rank > 200;


-- CHECK 4: Track enrichment integrity check
-- Objective: Ensure track enrichment records have valid track IDs and statuses.
-- Expected result: 0 rows.
SELECT
    source,
    input_date,
    market,
    spotify_track_id,
    status
FROM bronze.track_enrichment
WHERE spotify_track_id IS NULL
   OR TRIM(spotify_track_id) = ''
   OR status NOT IN ('found', 'missing');
