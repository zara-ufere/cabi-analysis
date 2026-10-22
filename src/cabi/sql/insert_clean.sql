INSERT INTO trips (ride_id, rideable_type, member_type, started_at, ended_at, duration_s,
                   start_date, start_hour, start_dow, end_date, end_hour, end_dow,
                   start_station_id, end_station_id, start_lat, start_lng, end_lat, end_lng, source_file)
SELECT ride_id, rideable_type, member_casual, started_at, ended_at, duration_s,
       substr(started_at, 1, 10), CAST(substr(started_at, 12, 2) AS INTEGER),
       (CAST(strftime('%w', started_at) AS INTEGER) + 6) % 7,
       substr(ended_at, 1, 10), CAST(substr(ended_at, 12, 2) AS INTEGER),
       (CAST(strftime('%w', ended_at) AS INTEGER) + 6) % 7,
       start_station_id, end_station_id, start_lat, start_lng, end_lat, end_lng, :source_file
FROM classified
WHERE reason IS NULL;
