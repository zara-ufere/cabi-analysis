-- Among trips that start and end at a dock, how many come back to the same dock?
SELECT member_type, COUNT(*) AS docked_trips,
       SUM(start_station_id = end_station_id) AS round_trips,
       1.0 * SUM(start_station_id = end_station_id) / COUNT(*) AS round_trip_share
FROM analysis_trips
WHERE start_station_id IS NOT NULL AND end_station_id IS NOT NULL
GROUP BY member_type
ORDER BY member_type;
