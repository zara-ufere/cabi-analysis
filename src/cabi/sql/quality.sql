SELECT reason, SUM(rows) AS rows FROM cleaning_log GROUP BY reason ORDER BY rows DESC, reason;
