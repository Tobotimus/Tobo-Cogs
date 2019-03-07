CREATE TABLE IF NOT EXISTS strikes (
    id BIGINT PRIMARY KEY,
    user BIGINT NOT NULL,
    guild BIGINT NOT NULL,
    moderator BIGINT NOT NULL,
    reason TEXT
);
