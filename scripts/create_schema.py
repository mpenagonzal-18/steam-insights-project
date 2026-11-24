from db_conn import get_connection

def run():
    print("Creating relational model...")
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE SCHEMA IF NOT EXISTS steam;

                -- 1. GAMES
                CREATE TABLE IF NOT EXISTS steam.games (
                    app_id INTEGER PRIMARY KEY,
                    title TEXT NOT NULL,
                    description TEXT,
                    date_release DATE,
                    rating TEXT,
                    positive_ratio SMALLINT,
                    user_reviews INTEGER,
                    price_final NUMERIC(10,2),
                    price_original NUMERIC(10,2),
                    discount SMALLINT,
                    CHECK (positive_ratio BETWEEN 0 AND 100),
                    CHECK (price_final >= 0),
                    CHECK (price_original >= 0),
                    CHECK (discount BETWEEN 0 AND 100),
                    CHECK (user_reviews >= 0)
                );

                -- 2. USERS
                CREATE TABLE IF NOT EXISTS steam.users (
                    user_id INTEGER PRIMARY KEY,
                    products INTEGER,
                    reviews INTEGER,
                    CHECK (products >= 0),
                    CHECK (reviews >= 0)
                );

                -- 3. RECOMMENDATIONS
                CREATE TABLE IF NOT EXISTS steam.recommendations (
                    review_id BIGINT PRIMARY KEY,
                    app_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    review_date DATE,
                    is_recommended BOOLEAN,
                    hours NUMERIC(12,2),
                    helpful INTEGER,
                    funny INTEGER,
                    FOREIGN KEY (app_id)
                        REFERENCES steam.games(app_id),
                    FOREIGN KEY (user_id)
                        REFERENCES steam.users(user_id),
                    CHECK (hours >= 0),
                    CHECK (helpful >= 0),
                    CHECK (funny >= 0)
                );

                -- 4. TAGS
                CREATE TABLE IF NOT EXISTS steam.tags (
                    tag_id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
                    tag_name TEXT NOT NULL UNIQUE
                );

                -- 5. GAME_TAGS
                CREATE TABLE IF NOT EXISTS steam.game_tags (
                    app_id INTEGER NOT NULL,
                    tag_id INTEGER NOT NULL,
                    PRIMARY KEY (app_id, tag_id),
                    FOREIGN KEY (app_id)
                        REFERENCES steam.games(app_id),
                    FOREIGN KEY (tag_id)
                        REFERENCES steam.tags(tag_id)
                );

                -- 6. PLATFORMS
                CREATE TABLE IF NOT EXISTS steam.platforms (
                    platform_id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
                    platform_name TEXT NOT NULL UNIQUE
                );

                -- 7. GAME_PLATFORMS
                CREATE TABLE IF NOT EXISTS steam.game_platforms (
                    app_id INTEGER NOT NULL,
                    platform_id INTEGER NOT NULL,
                    PRIMARY KEY (app_id, platform_id),
                    FOREIGN KEY (app_id)
                        REFERENCES steam.games(app_id),
                    FOREIGN KEY (platform_id)
                        REFERENCES steam.platforms(platform_id)
                );

                -- STAGING FOR JSON DATA
                CREATE TABLE IF NOT EXISTS staging.metadata_raw (
                    app_id INTEGER,
                    description TEXT,
                    tags JSONB
                );

                -- INDEXES
                CREATE INDEX IF NOT EXISTS idx_rec_app_id
                    ON steam.recommendations(app_id);

                CREATE INDEX IF NOT EXISTS idx_rec_user_id
                    ON steam.recommendations(user_id);

                CREATE INDEX IF NOT EXISTS idx_rec_date
                    ON steam.recommendations(review_date);

                CREATE INDEX IF NOT EXISTS idx_game_tags_tag
                    ON steam.game_tags(tag_id);

                CREATE INDEX IF NOT EXISTS idx_game_platforms_platform
                    ON steam.game_platforms(platform_id);
            """)
    print("Relational schema created successfully.")

if __name__ == "__main__":
    run()
