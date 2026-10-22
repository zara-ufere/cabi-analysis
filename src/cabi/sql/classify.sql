-- Give every staged row at most one reason to be rejected, checked in this order.
-- A NULL reason means the row is clean. Names beginning with ':' are bound parameters.
CREATE TEMP TABLE classified AS
WITH base AS (
    SELECT
        s.rowid AS rid,
        s.ride_id, s.rideable_type, s.member_casual, s.started_at, s.ended_at,
        s.start_station_id, s.end_station_id,
        CAST(s.start_lat AS REAL) AS start_lat, CAST(s.start_lng AS REAL) AS start_lng,
        CAST(s.end_lat   AS REAL) AS end_lat,   CAST(s.end_lng   AS REAL) AS end_lng,
        ROUND((julianday(s.ended_at) - julianday(s.started_at)) * 86400.0, 3) AS duration_s,
        ROW_NUMBER() OVER (PARTITION BY s.ride_id ORDER BY s.rowid) AS nth
    FROM stg s
)
SELECT
    base.*,
    CASE
        WHEN ride_id IS NULL                                              THEN 'missing_ride_id'
        WHEN nth > 1
          OR EXISTS (SELECT 1 FROM trips t WHERE t.ride_id = base.ride_id) THEN 'duplicate_ride_id'
        WHEN duration_s IS NULL                                           THEN 'bad_timestamp'
        WHEN member_casual IS NULL OR member_casual NOT IN ('member', 'casual') THEN 'unknown_member_type'
        WHEN duration_s < 0                                               THEN 'ended_before_started'
        WHEN duration_s < 60                                              THEN 'under_60_seconds'
        WHEN duration_s > 86400                                           THEN 'over_24_hours'
        WHEN start_lat IS NULL OR start_lng IS NULL
          OR end_lat   IS NULL OR end_lng   IS NULL                       THEN 'missing_coordinates'
        WHEN start_lat NOT BETWEEN :lat_min AND :lat_max
          OR end_lat   NOT BETWEEN :lat_min AND :lat_max
          OR start_lng NOT BETWEEN :lng_min AND :lng_max
          OR end_lng   NOT BETWEEN :lng_min AND :lng_max                  THEN 'outside_service_area'
    END AS reason
FROM base;
