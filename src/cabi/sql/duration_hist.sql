-- Trip length in whole minutes; everything an hour or longer shares the last bin.
SELECT member_type, MIN(CAST(duration_s / 60 AS INTEGER), 60) AS minute_bin, COUNT(*) AS trips
FROM analysis_trips
GROUP BY member_type, minute_bin
ORDER BY member_type, minute_bin;
