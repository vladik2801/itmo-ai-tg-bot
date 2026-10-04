
CREATE TABLE IF NOT EXISTS user_settings (
    user_id BIGINT PRIMARY KEY,
    mode TEXT NOT NULL DEFAULT 'default'
        CHECK (mode IN ('default', 'study', 'translate', 'summary')),
    temperature NUMERIC NOT NULL DEFAULT 0.3
        CHECK (temperature IN (0.0, 0.3, 0.7, 1.0))
);

CREATE TABLE IF NOT EXISTS messages (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    chat_id BIGINT NOT NULL,
    role TEXT NOT NULL
        CHECK (role IN ('user', 'assistant')),
    content TEXT NOT NULL
        CHECK (content ~ '[^[:space:]]'),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS messages_chat_id_id_idx
    ON messages (chat_id, id);

ALTER TABLE user_settings
    ALTER COLUMN mode SET DEFAULT 'study';

ALTER TABLE user_settings
    DROP CONSTRAINT IF EXISTS user_settings_mode_check;

ALTER TABLE user_settings
    ADD CONSTRAINT user_settings_mode_check
    CHECK (mode IN ('default', 'study', 'translate', 'summary'));