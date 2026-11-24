from pathlib import Path
from scripts.db_conn import get_connection
# Directorio de los archivos SQL
sql_dir = Path(__file__).parent / "sql"
# Lista de queries: (archivo SQL, título)
queries = [
    ("q1_top_20_games_rating.sql", "1. Top 20 highest-rated games"),
    ("q2_platforms_compatible_games.sql", "2. Games compatible with each platform"),
    ("q3_top15_tags.sql", "3. Top 15 most popular tags"),
    ("q4_rating_cat_avgs.sql", "4. Average prices and ratings by category"),
    ("q5_top10_recommended_games.sql", "5. Most positively recommended games"),
    ("q6_recommendations_avg_playtime.sql", "6. Average playing time by recommendation"),
    ("q7_top3_rated_per_release_year.sql", "7. Top 3 rated games per release year"),
    ("q8_positive_change_monthly.sql", "8. Monthly positive recommendation trends"),
    ("q9_higher_positive_than_avg_cat.sql", "9. Games outperforming their category"),
    ("q10_simulating_discounts_top10.sql", "10. Simulating a discount campaign")
]
# Conexión a la base de datos
conn = get_connection(dbname="steam_db")
try:
    with conn.cursor() as cur:
        for filename, title in queries:
            print(f"\n{'=' * 60}")
            print(title)
            print(f"{'=' * 60}")
            # Leer archivo SQL
            with open(sql_dir / filename, "r", encoding="utf-8") as f:
                sql = f.read()
            # Ejecutar query
            cur.execute(sql)
            # Mostrar resultados si la query devuelve filas
            if cur.description is not None:
                columns = [col[0] for col in cur.description]
                rows = cur.fetchall()
                print(" | ".join(columns))
                for row in rows:
                    print(" | ".join(str(value) for value in row))
                print(f"\nTotal rows: {len(rows)}")
            else:
                print("Query executed successfully.")
            # Cerrar cualquier transacción pendiente
            conn.rollback()
finally:
    conn.close()
print("\nALL QUERIES EXECUTED SUCCESSFULLY.")
