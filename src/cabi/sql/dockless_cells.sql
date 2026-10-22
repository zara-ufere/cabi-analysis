-- Where bikes are picked up or left away from a dock. For these trips the data rounds coordinates to
-- two decimals (about 1 km), so we count them per 0.01 degree cell instead of pretending to precision.
SELECT 'start' AS end_kind, ROUND(start_lat, 2) AS lat, ROUND(start_lng, 2) AS lng, COUNT(*) AS trips
FROM analysis_trips WHERE start_station_id IS NULL GROUP BY 2, 3
UNION ALL
SELECT 'end', ROUND(end_lat, 2), ROUND(end_lng, 2), COUNT(*)
FROM analysis_trips WHERE end_station_id IS NULL GROUP BY 2, 3;
