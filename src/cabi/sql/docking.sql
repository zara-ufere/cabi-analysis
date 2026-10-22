-- How often does each kind of bike start or end at a dock?
SELECT rideable_type, member_type, COUNT(*) AS trips,
       SUM(start_station_id IS NOT NULL) AS start_docked,
       SUM(end_station_id   IS NOT NULL) AS end_docked,
       SUM(start_station_id IS NOT NULL AND end_station_id IS NOT NULL) AS both_docked
FROM analysis_trips
GROUP BY rideable_type, member_type
ORDER BY rideable_type, member_type;
