SELECT t.start_station_id, s1.name AS from_station, t.end_station_id, s2.name AS to_station,
       COUNT(*) AS trips,
       1.0 * SUM(t.member_type = 'member') / COUNT(*) AS member_share,
       AVG(t.duration_s) / 60.0 AS mean_minutes
FROM analysis_trips t
JOIN stations s1 ON s1.station_id = t.start_station_id
JOIN stations s2 ON s2.station_id = t.end_station_id
WHERE t.start_station_id <> t.end_station_id
GROUP BY t.start_station_id, t.end_station_id
ORDER BY trips DESC, t.start_station_id, t.end_station_id
LIMIT :n;
