from pathlib import Path
from scripts.db_conn import get_connection, db_name

def run(data_path=None):
    data_path = Path(data_path) if data_path else Path(__file__).resolve().parent.parent / "data" / "raw"
    print("Creating staging tables...")
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE SCHEMA IF NOT EXISTS staging;

                CREATE TABLE IF NOT EXISTS staging.games (
                    app_id TEXT,
                    title TEXT,
                    date_release TEXT,
                    win TEXT,
                    mac TEXT,
                    linux TEXT,
                    rating TEXT,
                    positive_ratio TEXT,
                    user_reviews TEXT,
                    price_final TEXT,
                    price_original TEXT,
                    discount TEXT,
                    steam_deck TEXT
                );

                CREATE TABLE IF NOT EXISTS staging.users (
                    user_id TEXT,
                    products TEXT,
                    reviews TEXT
                );

                CREATE TABLE IF NOT EXISTS staging.recommendations (
                    app_id TEXT,
                    helpful TEXT,
                    funny TEXT,
                    date TEXT,
                    is_recommended TEXT,
                    hours TEXT,
                    user_id TEXT,
                    review_id TEXT
                );
            """)
            conn.commit()
            files = {
                "games.csv": "staging.games",
                "users.csv": "staging.users",
                "recommendations.csv": "staging.recommendations",
            }
            for filename, table in files.items():

                filepath = data_path / filename

                # Comprobar si la tabla contiene registros
                cur.execute(f"SELECT EXISTS (SELECT 1 FROM {table} LIMIT 1)")
                has_data = cur.fetchone()[0]

                if has_data:
                    print(f"{table} already contains data; import has been skipped.")
                    continue

                print(f"Importing {filename}...")

                with open(filepath, "r", encoding="utf-8") as f:
                    cur.copy_expert(
                        f"""
                        COPY {table}
                        FROM STDIN
                        WITH (
                            FORMAT CSV,
                            HEADER TRUE,
                            DELIMITER ',',
                            NULL ''
                        )
                        """,
                        f
                    )
                # NOTA: STIDIN -> Standard Input (queremos importar los datos que le mandamos)
                print(f"{filename} imported correctly.")
            print("Staging import finished.")

if __name__ == "__main__":
    run()
