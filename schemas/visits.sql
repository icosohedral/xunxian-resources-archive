CREATE TABLE IF NOT EXISTS daily_visit (
    visit_day TEXT PRIMARY KEY,
    visitor_count INTEGER NOT NULL CHECK (visitor_count >= 0)
);

CREATE TABLE IF NOT EXISTS daily_visitor (
    visit_day TEXT NOT NULL,
    visitor_id TEXT NOT NULL,
    PRIMARY KEY (visit_day, visitor_id)
);
