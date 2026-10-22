SELECT (SELECT COUNT(*) FROM analysis_trips)                           AS trips,
       (SELECT MIN(start_date) FROM analysis_trips)                    AS first_date,
       (SELECT MAX(start_date) FROM analysis_trips)                    AS last_date,
       (SELECT COUNT(DISTINCT start_date) FROM analysis_trips)         AS days,
       (SELECT COUNT(*) FROM stations)                                 AS stations,
       (SELECT COALESCE(SUM(rows_read), 0) FROM loads)                 AS rows_read,
       (SELECT COALESCE(SUM(rows_kept), 0) FROM loads)                 AS rows_kept,
       (SELECT COUNT(*) FROM loads)                                    AS files;
