-- Clean trips. The CHECK constraints are the cleaning rules written down as database invariants:
-- a row that violates one cannot get in, so every analysis can rely on them.
CREATE TABLE IF NOT EXISTS trips (
    ride_id          TEXT PRIMARY KEY,
    rideable_type    TEXT NOT NULL,
    member_type      TEXT NOT NULL CHECK (member_type IN ('member', 'casual')),
    started_at       TEXT NOT NULL,                 -- local Eastern time, 'YYYY-MM-DD HH:MM:SS.fff'
    ended_at         TEXT NOT NULL,
    duration_s       REAL NOT NULL CHECK (duration_s >= 60 AND duration_s <= 86400),
    start_date       TEXT NOT NULL,
    start_hour       INTEGER NOT NULL CHECK (start_hour BETWEEN 0 AND 23),
    start_dow        INTEGER NOT NULL CHECK (start_dow BETWEEN 0 AND 6),   -- 0 = Monday
    end_date         TEXT NOT NULL,
    end_hour         INTEGER NOT NULL CHECK (end_hour BETWEEN 0 AND 23),
    end_dow          INTEGER NOT NULL CHECK (end_dow BETWEEN 0 AND 6),
    start_station_id TEXT,                           -- NULL when the bike was not taken from a dock
    end_station_id   TEXT,                           -- NULL when the bike was not returned to a dock
    start_lat        REAL NOT NULL,
    start_lng        REAL NOT NULL,
    end_lat          REAL NOT NULL,
    end_lng          REAL NOT NULL,
    source_file      TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_trips_start_date ON trips (start_date);
CREATE INDEX IF NOT EXISTS ix_trips_start_station ON trips (start_station_id);
CREATE INDEX IF NOT EXISTS ix_trips_end_station ON trips (end_station_id);
CREATE INDEX IF NOT EXISTS ix_trips_source ON trips (source_file);

-- Rows that failed a cleaning rule, kept so nothing disappears without a reason.
CREATE TABLE IF NOT EXISTS rejected_trips (
    ride_id          TEXT,
    reason           TEXT NOT NULL,
    rideable_type    TEXT,
    member_casual    TEXT,
    started_at       TEXT,
    ended_at         TEXT,
    duration_s       REAL,
    start_station_id TEXT,
    end_station_id   TEXT,
    source_file      TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_rejected_source ON rejected_trips (source_file);

CREATE TABLE IF NOT EXISTS cleaning_log (
    source_file TEXT NOT NULL,
    reason      TEXT NOT NULL,
    rows        INTEGER NOT NULL,
    PRIMARY KEY (source_file, reason)
);

CREATE TABLE IF NOT EXISTS loads (
    source_file TEXT PRIMARY KEY,
    rows_read   INTEGER NOT NULL,
    rows_kept   INTEGER NOT NULL,
    loaded_at   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS station_names (
    station_id TEXT PRIMARY KEY,
    name       TEXT NOT NULL,
    last_seen  TEXT NOT NULL
);
