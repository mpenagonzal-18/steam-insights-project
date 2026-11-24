import json
from pathlib import Path
from psycopg2.extras import execute_values
from db_conn import get_connection

def run(data_path=None):
    data_path = Path(data_path) if data_path else Path(__file__).resolve().parent / "data" / "raw"
    metadata_path = data_path / "games_metadata.json"
    print("Inserting relational data...")
    with get_connection() as conn:
        with conn.cursor() as cur:
            # 1. CHECK IF TABLES ARE EMPTY
            tables = [
                "steam.games",
                "steam.users",
                "steam.recommendations",
                "steam.tags",
                "steam.game_tags",
                "steam.platforms",
                "steam.game_platforms",
                "staging.metadata_raw"
            ]
            for table in tables:
                cur.execute(f"""
                    SELECT EXISTS (
                        SELECT 1 FROM {table}
                    )
                """)
                if cur.fetchone()[0]:
                    raise ValueError(
                        f"{table} already contains data."
                    )
            # 2. IMPORT JSON INTO STAGING
            print("Importing JSON metadata...")
            batch = []
            with open(metadata_path, "r", encoding="utf-8") as f:
                for line in f:
                    if not line.strip():
                        continue
                    item = json.loads(line)
                    batch.append((
                        item["app_id"],
                        item.get("description"),
                        json.dumps(item.get("tags", []))
                    ))
                    if len(batch) >= 1000:
                        execute_values(
                            cur,
                            """
                            INSERT INTO staging.metadata_raw
                            (app_id, description, tags)
                            VALUES %s
                            """,
                            batch
                        )

                        batch.clear()
                if batch:
                    execute_values(
                        cur,
                        """
                        INSERT INTO staging.metadata_raw
                        (app_id, description, tags)
                        VALUES %s
                        """,
                        batch
                    )
            print("JSON metadata imported.")
            # 3. INSERT GAMES
            print("Importing games...")
            cur.execute("""
                INSERT INTO steam.games (
                    app_id, title, description,
                    date_release, rating, positive_ratio,
                    user_reviews, price_final,
                    price_original, discount
                )

                SELECT
                    g.app_id::INTEGER,
                    g.title,
                    NULLIF(m.description, ''),
                    g.date_release::DATE,
                    g.rating,
                    g.positive_ratio::NUMERIC::SMALLINT,
                    g.user_reviews::INTEGER,
                    g.price_final::NUMERIC(10,2),
                    g.price_original::NUMERIC(10,2),
                    g.discount::NUMERIC::SMALLINT

                FROM staging.games g

                LEFT JOIN staging.metadata_raw m
                    ON g.app_id::INTEGER = m.app_id;
            """)
            print(f"-> {cur.rowcount} games inserted.")
            # 4. INSERT USERS
            print("Importing users...")
            cur.execute("""
                INSERT INTO steam.users (
                    user_id, products, reviews
                )

                SELECT
                    user_id::INTEGER,
                    products::INTEGER,
                    reviews::INTEGER

                FROM staging.users;
            """)
            print(f"-> {cur.rowcount} users inserted.")
            # 5. INSERT PLATFORMS
            print("Importing platforms...")
            platform_columns = {
                "win": "Windows",
                "mac": "Mac",
                "linux": "Linux",
                "steam_deck": "Steam Deck"
            }
            for platform in platform_columns.values():
                cur.execute("""
                    INSERT INTO steam.platforms (platform_name)
                    VALUES (%s)
                    ON CONFLICT (platform_name) DO NOTHING;
                """, (platform,))
            print("Platforms imported.")
            # 6. INSERT GAME_PLATFORMS
            print("Importing game-platform relationships...")
            for column, platform in platform_columns.items():
                cur.execute(f"""
                    INSERT INTO steam.game_platforms (
                        app_id, platform_id
                    )

                    SELECT DISTINCT
                        g.app_id,
                        p.platform_id

                    FROM staging.games s

                    JOIN steam.games g
                        ON g.app_id = s.app_id::INTEGER

                    JOIN steam.platforms p
                        ON p.platform_name = %s

                    WHERE LOWER(s.{column}) = 'true'

                    ON CONFLICT DO NOTHING;
                """, (platform,))
                print(
                    f"-> {platform}: {cur.rowcount} relationships."
                )
            # 7. INSERT TAGS
            print("Importing tags...")
            cur.execute("""
                INSERT INTO steam.tags (tag_name)

                SELECT DISTINCT BTRIM(t.tag)

                FROM staging.metadata_raw m

                CROSS JOIN LATERAL
                    jsonb_array_elements_text(m.tags) AS t(tag)

                WHERE BTRIM(t.tag) <> ''

                ON CONFLICT (tag_name) DO NOTHING;
            """)
            print(f"-> {cur.rowcount} tags inserted.")
            # 8. INSERT GAME_TAGS
            print("Importing game-tag relationships...")

            cur.execute("""
                INSERT INTO steam.game_tags (
                    app_id, tag_id
                )

                SELECT DISTINCT
                    g.app_id,
                    t.tag_id

                FROM staging.metadata_raw m

                JOIN steam.games g
                    ON g.app_id = m.app_id

                CROSS JOIN LATERAL
                    jsonb_array_elements_text(m.tags) AS x(tag)

                JOIN steam.tags t
                    ON t.tag_name = BTRIM(x.tag)

                ON CONFLICT DO NOTHING;
            """)
            print(
                f"-> {cur.rowcount} game-tag relationships."
            )
            # 9. INSERT RECOMMENDATIONS
            print("Importing recommendations...")
            cur.execute("""
                INSERT INTO steam.recommendations (
                    review_id, app_id, user_id,
                    review_date, is_recommended,
                    hours, helpful, funny
                )

                SELECT
                    review_id::BIGINT,
                    app_id::INTEGER,
                    user_id::INTEGER,
                    date::DATE,
                    is_recommended::BOOLEAN,
                    hours::NUMERIC(12,2),
                    helpful::INTEGER,
                    funny::INTEGER

                FROM staging.recommendations;
            """)
            print(
                f"-> {cur.rowcount} recommendations inserted."
            )
    print("ALL DATA INSERTED SUCCESSFULLY.")

if __name__ == "__main__":
    run()
