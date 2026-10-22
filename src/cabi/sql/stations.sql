-- Trip coordinates are the bike's GPS position, not the dock's, so a station's location is the
-- coordinate pair seen most often at that station. Classic bikes always report the dock position.
DROP TABLE IF EXISTS stations;
CREATE TABLE stations AS
WITH points AS (
    SELECT start_station_id AS station_id, start_lat AS lat, start_lng AS lng FROM trips WHERE start_station_id IS NOT NULL
    UNION ALL
    SELECT end_station_id, end_lat, end_lng FROM trips WHERE end_station_id IS NOT NULL
),
counted AS (
    SELECT station_id, lat, lng, COUNT(*) AS n FROM points GROUP BY station_id, lat, lng
),
ranked AS (
    SELECT station_id, lat, lng,
           ROW_NUMBER() OVER (PARTITION BY station_id ORDER BY n DESC, lat, lng) AS rk,
           SUM(n) OVER (PARTITION BY station_id) AS n_events
    FROM counted
)
SELECT r.station_id, COALESCE(nm.name, r.station_id) AS name, r.lat, r.lng, r.n_events
FROM ranked r
LEFT JOIN station_names nm ON nm.station_id = r.station_id
WHERE r.rk = 1;
CREATE UNIQUE INDEX ix_stations_id ON stations (station_id);

-- Trips to analyse: skip rides that started before the first loaded month. Files are split by the
-- month a ride ENDED, so a ride that crosses midnight at the start of the range has no partner file.
DROP VIEW IF EXISTS analysis_trips;
CREATE VIEW analysis_trips AS
SELECT * FROM trips
WHERE start_date >= (SELECT MIN(substr(ended_at, 1, 7)) || '-01' FROM trips);

-- Every dock departure (-1) and arrival (+1) as one event stream, for station flow analysis.
DROP VIEW IF EXISTS station_events;
CREATE VIEW station_events AS
SELECT start_station_id AS station_id, start_date AS event_date, start_hour AS event_hour,
       start_dow AS event_dow, -1 AS delta, member_type, rideable_type
FROM analysis_trips WHERE start_station_id IS NOT NULL
UNION ALL
SELECT end_station_id, end_date, end_hour, end_dow, 1, member_type, rideable_type
FROM analysis_trips WHERE end_station_id IS NOT NULL;
