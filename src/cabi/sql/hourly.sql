-- Average trips per hour of the day, separately for weekdays and weekends and for each rider type.
-- Dividing by the number of days of that kind makes weekdays and weekends comparable.
WITH days AS (
    SELECT CASE WHEN start_dow >= 5 THEN 'weekend' ELSE 'weekday' END AS day_type,
           COUNT(DISTINCT start_date) AS n_days
    FROM analysis_trips
    GROUP BY day_type
)
SELECT d.day_type, t.member_type, t.start_hour AS hour,
       COUNT(*) AS trips, d.n_days, 1.0 * COUNT(*) / d.n_days AS trips_per_day
FROM analysis_trips t
JOIN days d ON d.day_type = CASE WHEN t.start_dow >= 5 THEN 'weekend' ELSE 'weekday' END
GROUP BY d.day_type, t.member_type, t.start_hour
ORDER BY d.day_type, t.member_type, t.start_hour;
