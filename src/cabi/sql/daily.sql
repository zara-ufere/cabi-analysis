SELECT start_date                                     AS date,
       start_dow                                      AS dow,            -- 0 = Monday
       COUNT(*)                                       AS trips,
       SUM(member_type = 'member')                    AS member_trips,
       SUM(member_type = 'casual')                    AS casual_trips
FROM analysis_trips
GROUP BY start_date
ORDER BY start_date;
