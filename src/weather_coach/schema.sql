PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    email TEXT NOT NULL UNIQUE,
    created_at_utc TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS locations (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    label TEXT NOT NULL,
    latitude REAL NOT NULL CHECK(latitude BETWEEN -90 AND 90),
    longitude REAL NOT NULL CHECK(longitude BETWEEN -180 AND 180),
    timezone TEXT NOT NULL,
    created_at_utc TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS routines (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    origin_location_id TEXT NOT NULL REFERENCES locations(id) ON DELETE RESTRICT,
    destination_location_id TEXT NOT NULL REFERENCES locations(id) ON DELETE RESTRICT,
    days_of_week TEXT NOT NULL,
    departure_local_time TEXT NOT NULL,
    return_local_time TEXT,
    timezone TEXT NOT NULL,
    travel_mode TEXT NOT NULL CHECK(travel_mode IN ('walk', 'drive', 'transit')),
    estimated_duration_minutes INTEGER NOT NULL CHECK(estimated_duration_minutes > 0),
    rain_probability_threshold REAL NOT NULL CHECK(rain_probability_threshold BETWEEN 0 AND 1),
    precipitation_mm_threshold REAL NOT NULL CHECK(precipitation_mm_threshold >= 0),
    cold_apparent_temperature_c REAL,
    pre_alert_minutes INTEGER NOT NULL CHECK(pre_alert_minutes >= 0),
    active INTEGER NOT NULL CHECK(active IN (0, 1)),
    created_at_utc TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS forecast_points (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    location_id TEXT NOT NULL REFERENCES locations(id) ON DELETE CASCADE,
    valid_at_utc TEXT NOT NULL,
    source TEXT NOT NULL,
    retrieved_at_utc TEXT NOT NULL,
    precipitation_probability REAL NOT NULL CHECK(precipitation_probability BETWEEN 0 AND 1),
    precipitation_mm REAL NOT NULL CHECK(precipitation_mm >= 0),
    temperature_c REAL NOT NULL,
    apparent_temperature_c REAL NOT NULL,
    weather_code TEXT NOT NULL,
    UNIQUE(location_id, valid_at_utc, source)
);

CREATE TABLE IF NOT EXISTS evaluations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    routine_id TEXT NOT NULL REFERENCES routines(id) ON DELETE CASCADE,
    leg TEXT NOT NULL CHECK(leg IN ('departure', 'return')),
    occurrence_at_utc TEXT NOT NULL,
    evaluation_key TEXT NOT NULL UNIQUE,
    decision_type TEXT NOT NULL,
    should_notify INTEGER NOT NULL CHECK(should_notify IN (0, 1)),
    message TEXT NOT NULL,
    reasons_json TEXT NOT NULL,
    evaluated_at_utc TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS alerts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    evaluation_id INTEGER NOT NULL UNIQUE REFERENCES evaluations(id) ON DELETE CASCADE,
    status TEXT NOT NULL CHECK(status IN ('pending', 'accepted', 'delivered', 'opened', 'failed', 'expired')),
    created_at_utc TEXT NOT NULL,
    sent_at_utc TEXT,
    opened_at_utc TEXT
);

CREATE TABLE IF NOT EXISTS feedback (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    alert_id INTEGER NOT NULL REFERENCES alerts(id) ON DELETE CASCADE,
    helpful INTEGER CHECK(helpful IN (0, 1) OR helpful IS NULL),
    actual_condition TEXT,
    notes TEXT,
    created_at_utc TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS notification_outbox (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    alert_id INTEGER NOT NULL UNIQUE REFERENCES alerts(id) ON DELETE CASCADE,
    channel TEXT NOT NULL CHECK(channel IN ('test', 'email', 'web_push')),
    payload_json TEXT NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('queued', 'processing', 'sent', 'failed')),
    attempts INTEGER NOT NULL CHECK(attempts >= 0),
    created_at_utc TEXT NOT NULL,
    available_at_utc TEXT NOT NULL,
    sent_at_utc TEXT,
    last_error TEXT
);

CREATE INDEX IF NOT EXISTS idx_forecast_points_location_time
    ON forecast_points(location_id, valid_at_utc);

CREATE INDEX IF NOT EXISTS idx_evaluations_routine_occurrence
    ON evaluations(routine_id, occurrence_at_utc);

CREATE INDEX IF NOT EXISTS idx_notification_outbox_status
    ON notification_outbox(status, available_at_utc);
