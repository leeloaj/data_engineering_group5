-- ============================================================================
-- BUSINESS QUESTIONS AND KPIs
-- Run against the gold schema. Change the artist name in each query.
-- Popularity is measured with chart_points from gold.fact_track_daily_popularity:
-- 200 points for #1 down to 1 point for #200, summed over all country charts.
-- ============================================================================

SET search_path = gold;

-- BQ1: Which of an artist's tracks receive the most streams?
SELECT
    t.track_id,
    t.track_title,
    SUM(f.streams) AS total_streams
FROM fact_track_performance f
JOIN dim_track t ON f.track_key = t.track_key
JOIN dim_artist a ON f.artist_key = a.artist_key
JOIN dim_country c ON f.country_key = c.country_key
WHERE a.artist_name = 'Arctic Monkeys'
  AND c.country_code <> 'GLOBAL'   -- avoid double counting global + country rows
GROUP BY t.track_id, t.track_title
ORDER BY total_streams DESC
LIMIT 10;

-- BQ2: How does an artist's track popularity change over time?
SELECT
    d.year,
    d.month,
    t.track_title,
    ROUND(AVG(p.chart_points), 1)   AS avg_daily_chart_points,
    MAX(p.countries_charted)        AS max_countries_charted,
    MIN(p.global_chart_position)    AS best_global_position,
    SUM(p.country_streams)          AS monthly_streams
FROM fact_track_daily_popularity p
JOIN bridge_track_artist b ON p.track_key = b.track_key
JOIN dim_artist a ON b.artist_key = a.artist_key
JOIN dim_track t ON p.track_key = t.track_key
JOIN dim_date d ON p.date_key = d.date_key
WHERE a.artist_name = 'Arctic Monkeys'
GROUP BY d.year, d.month, t.track_id, t.track_title
ORDER BY t.track_title, d.year, d.month;

-- BQ3: Which audio characteristics are associated with higher popularity?
-- Popularity per track = average daily chart points over the days it charted.
WITH track_popularity AS (
    SELECT track_key, AVG(chart_points) AS popularity
    FROM fact_track_daily_popularity
    GROUP BY track_key
),
track_features AS (
    SELECT
        tp.popularity,
        (t.audio_features->>'danceability')::FLOAT  AS danceability,
        (t.audio_features->>'energy')::FLOAT        AS energy,
        (t.audio_features->>'valence')::FLOAT       AS valence,
        (t.audio_features->>'tempo')::FLOAT         AS tempo,
        (t.audio_features->>'loudness')::FLOAT      AS loudness,
        (t.audio_features->>'acousticness')::FLOAT  AS acousticness
    FROM dim_track t
    JOIN track_popularity tp ON t.track_key = tp.track_key
    WHERE t.audio_features IS NOT NULL
)
SELECT
    COUNT(*)                                                AS tracks_used,
    ROUND(CORR(popularity, danceability)::NUMERIC, 3)       AS corr_danceability,
    ROUND(CORR(popularity, energy)::NUMERIC, 3)             AS corr_energy,
    ROUND(CORR(popularity, valence)::NUMERIC, 3)            AS corr_valence,
    ROUND(CORR(popularity, tempo)::NUMERIC, 3)              AS corr_tempo,
    ROUND(CORR(popularity, loudness)::NUMERIC, 3)           AS corr_loudness,
    ROUND(CORR(popularity, acousticness)::NUMERIC, 3)       AS corr_acousticness
FROM track_features;

-- BQ4: Which countries have the highest streaming activity for an artist?
SELECT
    c.country_name,
    c.region,
    SUM(f.streams) AS total_streams,
    ROUND(100.0 * SUM(f.streams) / SUM(SUM(f.streams)) OVER (), 1) AS pct_of_total
FROM fact_track_performance f
JOIN dim_artist a ON f.artist_key = a.artist_key
JOIN dim_country c ON f.country_key = c.country_key
WHERE a.artist_name = 'Arctic Monkeys'
  AND c.country_code <> 'GLOBAL'
GROUP BY c.country_name, c.region
ORDER BY total_streams DESC;

-- BQ5: How do an artist's new releases compare with their previous releases?
-- First 30 days after release; "new" = released in the last 12 months of data.
WITH artist_window AS (
    SELECT MAX(d.full_date) AS latest_date
    FROM fact_track_performance f
    JOIN dim_artist a ON f.artist_key = a.artist_key
    JOIN dim_date d ON f.date_key = d.date_key
    WHERE a.artist_name = 'Arctic Monkeys'
),
first_30_days AS (
    SELECT
        t.track_id,
        t.release_date,
        SUM(f.streams)                  AS streams_first_30d,
        ROUND(AVG(f.chart_position), 1) AS avg_position_first_30d
    FROM fact_track_performance f
    JOIN dim_track t ON f.track_key = t.track_key
    JOIN dim_artist a ON f.artist_key = a.artist_key
    JOIN dim_date d ON f.date_key = d.date_key
    WHERE a.artist_name = 'Arctic Monkeys'
      AND d.full_date BETWEEN t.release_date AND t.release_date + 29
    GROUP BY t.track_id, t.release_date
)
SELECT
    CASE WHEN s.release_date > w.latest_date - INTERVAL '12 months'
         THEN 'new release' ELSE 'historical' END AS release_group,
    COUNT(*)                                     AS tracks,
    ROUND(AVG(s.streams_first_30d))              AS avg_streams_first_30d,
    ROUND(AVG(s.avg_position_first_30d), 1)      AS avg_chart_position
FROM first_30_days s
CROSS JOIN artist_window w
GROUP BY release_group
ORDER BY release_group DESC;

-- KPI 1: Total streams for an artist over a date range.
SELECT SUM(f.streams) AS total_streams
FROM fact_track_performance f
JOIN dim_artist a ON f.artist_key = a.artist_key
JOIN dim_country c ON f.country_key = c.country_key
WHERE a.artist_name = 'Arctic Monkeys'
  AND c.country_code <> 'GLOBAL'
  AND f.date_key BETWEEN 20170101 AND 20211231;

-- KPI 2: Average track popularity across an artist's catalog
-- (average daily chart points per track, then averaged over the tracks).
WITH track_popularity AS (
    SELECT p.track_key, AVG(p.chart_points) AS popularity
    FROM fact_track_daily_popularity p
    JOIN bridge_track_artist b ON p.track_key = b.track_key
    JOIN dim_artist a ON b.artist_key = a.artist_key
    WHERE a.artist_name = 'Arctic Monkeys'
    GROUP BY p.track_key
)
SELECT
    COUNT(*)                     AS tracks,
    ROUND(AVG(popularity), 1)    AS avg_track_popularity
FROM track_popularity;

-- KPI 3: Stream growth rate, month over month, for an artist.
WITH monthly AS (
    SELECT d.year, d.month, SUM(f.streams) AS streams
    FROM fact_track_performance f
    JOIN dim_artist a ON f.artist_key = a.artist_key
    JOIN dim_country c ON f.country_key = c.country_key
    JOIN dim_date d ON f.date_key = d.date_key
    WHERE a.artist_name = 'Arctic Monkeys'
      AND c.country_code <> 'GLOBAL'
    GROUP BY d.year, d.month
)
SELECT
    year,
    month,
    streams,
    ROUND(100.0 * (streams - LAG(streams) OVER (ORDER BY year, month))
          / NULLIF(LAG(streams) OVER (ORDER BY year, month), 0), 1) AS growth_pct
FROM monthly
ORDER BY year, month;
