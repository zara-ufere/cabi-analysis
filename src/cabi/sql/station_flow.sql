-- Which stations empty out or fill up during the commute peaks?
-- Every dock departure is -1 and every arrival is +1 (view station_events). For each station and
-- weekday we add those up inside the morning and evening windows. A negative net means more bikes
-- left than arrived. Stations are averaged over ALL weekdays, so a day with no trips counts as zero.
-- :am_start/:am_end and :pm_start/:pm_end are hours (end exclusive); :gap is the daily net swing
-- (in bikes) that counts as a drain or a fill day.
WITH weekdays AS (
    SELECT COUNT(DISTINCT event_date) AS n FROM station_events WHERE event_dow < 5
),
daily AS (
    SELECT station_id, event_date,
        SUM(CASE WHEN event_hour >= :am_start AND event_hour < :am_end THEN delta ELSE 0 END)                  AS am_net,
        SUM(CASE WHEN event_hour >= :am_start AND event_hour < :am_end AND delta = -1 THEN 1 ELSE 0 END)       AS am_out,
        SUM(CASE WHEN event_hour >= :am_start AND event_hour < :am_end AND delta =  1 THEN 1 ELSE 0 END)       AS am_in,
        SUM(CASE WHEN event_hour >= :pm_start AND event_hour < :pm_end THEN delta ELSE 0 END)                  AS pm_net,
        SUM(CASE WHEN event_hour >= :pm_start AND event_hour < :pm_end AND delta = -1 THEN 1 ELSE 0 END)       AS pm_out,
        SUM(CASE WHEN event_hour >= :pm_start AND event_hour < :pm_end AND delta =  1 THEN 1 ELSE 0 END)       AS pm_in,
        COUNT(*) AS events
    FROM station_events
    WHERE event_dow < 5
    GROUP BY station_id, event_date
)
SELECT d.station_id, s.name, s.lat, s.lng, w.n AS weekdays,
       SUM(d.events) * 1.0 / w.n                  AS events_per_day,
       SUM(d.am_out) * 1.0 / w.n                  AS am_out_per_day,
       SUM(d.am_in)  * 1.0 / w.n                  AS am_in_per_day,
       SUM(d.am_net) * 1.0 / w.n                  AS am_net_per_day,
       SUM(d.am_net <= -:gap) * 1.0 / w.n         AS am_drain_share,
       SUM(d.am_net >=  :gap) * 1.0 / w.n         AS am_fill_share,
       SUM(d.pm_out) * 1.0 / w.n                  AS pm_out_per_day,
       SUM(d.pm_in)  * 1.0 / w.n                  AS pm_in_per_day,
       SUM(d.pm_net) * 1.0 / w.n                  AS pm_net_per_day,
       SUM(d.pm_net <= -:gap) * 1.0 / w.n         AS pm_drain_share,
       SUM(d.pm_net >=  :gap) * 1.0 / w.n         AS pm_fill_share
FROM daily d
JOIN stations s ON s.station_id = d.station_id
CROSS JOIN weekdays w
GROUP BY d.station_id
ORDER BY d.station_id;
