-- One row per month: volume, who rides, what they ride, and how often a bike is taken from a dock.
SELECT substr(start_date, 1, 7)                       AS month,
       COUNT(*)                                       AS trips,
       SUM(member_type = 'member')                    AS member_trips,
       SUM(member_type = 'casual')                    AS casual_trips,
       SUM(rideable_type = 'electric_bike')           AS ebike_trips,
       SUM(start_station_id IS NULL)                  AS dockless_starts,
       COUNT(DISTINCT start_date)                     AS days
FROM analysis_trips
GROUP BY month
ORDER BY month;
