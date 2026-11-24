from db_conn import get_connection

def run():
    files = {
        "games.csv": "staging.games",
        "users.csv": "staging.users",
        "recommendations.csv": "staging.recommendations",
    }
    print("*** DATA ANALYSIS ***")
    with get_connection() as conn:
        with conn.cursor() as cur:
            print("1. Row count for every table")
            for filename, table in files.items():
                cur.execute(
                    f"""
                    SELECT COUNT(*) as total_games
                    FROM {table};
                    """
                )
                count = cur.fetchone()[0]
                print(f"-> Row count in {table}: {count}")
            print("2. Are the keys unique?")
            keys = {
                'staging.games': 'app_id',
                'staging.users': 'user_id',
                'staging.recommendations': 'review_id'
            }
            for table, key in keys.items():
                cur.execute(
                    f"""
                    SELECT {key}, COUNT(*) AS repetitions
                    FROM {table}
                    GROUP BY {key}
                    HAVING COUNT(*) > 1;
                    """
                )
                duplicates = cur.fetchall()
                print(f"-> Duplicate keys in {table}: {len(duplicates)}")
            print("3. Null values per column / Total null counts")
            columns = {
                "staging.games": [
                    "app_id", "title", "date_release", "win", "mac",
                    "linux", "rating", "positive_ratio", "user_reviews",
                    "price_final", "price_original", "discount", "steam_deck"
                ],

                "staging.users": [
                    "user_id", "products", "reviews"
                ],

                "staging.recommendations": [
                    "app_id", "helpful", "funny", "date",
                    "is_recommended", "hours", "user_id", "review_id"
                ]
            }
            for table, cols in columns.items():
                print(f"-> Nulls per column in {table}")
                for col in cols:
                    cur.execute(
                        f'''
                        SELECT COUNT(*) FILTER (WHERE {col} IS NULL) AS nulls
                        FROM {table};
                        '''
                    )
                    nulls_col = cur.fetchone()[0]
                    print(f"----> Column '{col}': {nulls_col} nulls")
            print("4. Value ranges and formats of data")
            print("- 4.1. Numeric columns -")
            numeric_columns = {
                "staging.games": [
                    "app_id", "positive_ratio", "user_reviews",
                    "price_final", "price_original", "discount"
                ],
                "staging.users": [
                    "user_id", "products", "reviews"
                ],
                "staging.recommendations": [
                    "app_id", "helpful", "funny", "hours",
                    "user_id", "review_id"
                ]
            }
            # Para sacar los números -> diferenciar entre formatos válidos (1, 2.90, etc.) e inválidos
            for table, columns in numeric_columns.items():
                print(f"\nTable: {table}")
                for col in columns:
                    # Formatos válidos
                    cur.execute(f"""
                        SELECT
                            MIN({col}::NUMERIC),
                            MAX({col}::NUMERIC)
                        FROM {table}
                        WHERE {col} IS NOT NULL
                        AND {col} ~ '^-?[0-9]+(\\.[0-9]+)?$'
                    """)
                    min_value, max_value = cur.fetchone()
                    # Formatos inválidos -> Aquellos que no coinciden con un formato entero/decimal en los datos
                    cur.execute(f"""
                        SELECT COUNT(*)
                        FROM {table}
                        WHERE {col} IS NOT NULL
                        AND {col} !~ '^-?[0-9]+(\\.[0-9]+)?$'
                    """)
                    invalid = cur.fetchone()[0]
                    print(f"-> {col}: MIN={min_value}, MAX={max_value}, INVALID={invalid}")
            print("- 4.2. Categorical columns")
            categorical_columns = {
                "staging.games": [
                    "rating", "win", "mac", "linux", "steam_deck"
                ],
                "staging.recommendations": [
                    "is_recommended"
                ]
            }
            for table, columns in categorical_columns.items():
                for col in columns:
                    print(f"\n{table}.{col}:")
                    cur.execute(f"""
                        SELECT {col}, COUNT(*)
                        FROM {table}
                        GROUP BY {col}
                        ORDER BY COUNT(*) DESC
                    """)
                    for value, count in cur.fetchall():
                        print(f"-> {value}: {count}")
            print("- 4.3. Columns with dates")
            # Columnas con fechas
            date_columns = {
                "staging.games": "date_release",
                "staging.recommendations": "date"
            }

            for table, col in date_columns.items(): # El AND contiene el formato de fecha AAAA-MM-DD
                cur.execute(f"""
                    SELECT
                        MIN({col}),
                        MAX({col}),
                        COUNT(*) FILTER (
                            WHERE {col} IS NOT NULL
                            AND {col} !~ '^\\d{{4}}-\\d{{2}}-\\d{{2}}$'
                        )
                    FROM {table}
                """)
                min_date, max_date, invalid = cur.fetchone()
                print(f"\n{table}.{col}")
                print(f"-> MIN: {min_date}")
                print(f"-> MAX: {max_date}")
                print(f"-> Invalid formats: {invalid}")
            print("5. Duplicates and unexpected values")
            print("- 5.1. Duplicate values")
            for filename, table in files.items():
                cur.execute(
                    f'''
                    SELECT COUNT(*) as total_samples
                    FROM {table};
                    '''
                )
                total = cur.fetchone()[0]
                cur.execute(
                    f'''
                    SELECT COUNT(*) FROM (SELECT DISTINCT * FROM {table}) AS unique_rows;
                    '''
                )
                unique = cur.fetchone()[0]
                print(f"--> {table}: {total - unique} duplicates")
            print("- 5.2. Unexpected values")
            print("* Numeric columns *")
            # Determinamos los rangos válidos de nuestras variables
            valid_ranges = {
                "staging.games": {
                    "price_final": (0, None),
                    "price_original": (0, None),
                    "positive_ratio": (0, 100),
                    "discount": (0, 100),
                    "user_reviews": (0, None)
                },
                "staging.users": {
                    "products": (0, None),
                    "reviews": (0, None)
                },
                "staging.recommendations": {
                    "hours": (0, None),
                    "helpful": (0, None),
                    "funny": (0, None)
                }
            }
            for table, columns in valid_ranges.items(): # Las cosas inesperadas deben aparecer sobre todo en valores numéricos
                print(f"-> Table {table}")
                for col, (minimum, maximum) in columns.items():
                    # Como SQL no reconoce 'None', hay que poner NULL para determinar que no hay límite
                    min_sql = "NULL" if minimum is None else str(minimum)
                    max_sql = "NULL" if maximum is None else str(maximum)
                    cur.execute(
                        f"""
                        SELECT COUNT(*)
                        FROM {table}
                        WHERE {col} IS NOT NULL
                        AND {col} ~ '^-?[0-9]+(\\.[0-9]+)?$'
                        AND (
                            ({min_sql}::NUMERIC IS NOT NULL AND {col}::NUMERIC < {min_sql}::NUMERIC)
                            OR
                            ({max_sql}::NUMERIC IS NOT NULL AND {col}::NUMERIC > {max_sql}::NUMERIC)
                        );
                        """
                    )
                    unexpected = cur.fetchone()[0]
                    print(f"---> {col}: {unexpected} unexpected values")
            print("* Date columns *")
            date_columns = {
                "staging.games": ["date_release"],
                "staging.recommendations": ["date"]
            }
            for table, columns in date_columns.items():
                print(f"-> Table {table}")
                for col in columns:
                    cur.execute(f"""
                        SELECT COUNT(*)
                        FROM {table}
                        WHERE {col} IS NOT NULL
                        AND (
                            {col} !~ '^\\d{{4}}-\\d{{2}}-\\d{{2}}$'
                            OR (
                                {col} ~ '^\\d{{4}}-\\d{{2}}-\\d{{2}}$'
                                AND NOT pg_input_is_valid({col}, 'date')
                            )
                        )
                    """)
                    # El AND de las fechas: combina valores sin formato AAAA-MM-DD y fechas que pg_input_is_valid no las considera
                    # válidas (ejemplo: 30 de febrero -> fecha inexistente).
                    unexpected = cur.fetchone()[0]
                    print(f"---> {col}: {unexpected} unexpected dates")
            print("* BOOLEAN Categorical columns *")
            bool_categorical_columns = {
                "staging.games": [
                    "win", "mac", "linux", "steam_deck"
                ],
                "staging.recommendations": [
                    "is_recommended"
                ]
            }
            for table, columns in bool_categorical_columns.items():
                print(f"-> Table {table}")
                for col in columns:
                    cur.execute(f"""
                        SELECT COUNT(*)
                        FROM {table}
                        WHERE {col} IS NOT NULL
                        AND LOWER({col}) NOT IN ('true', 'false')
                    """)
                    # Se hace LOWER({col}) para pasarlo a minúsculas y ser compatible con la lógica de SQL
                    unexpected = cur.fetchone()[0]
                    print(f"-> {col}: {unexpected} unexpected values")
            print("* LABELED Categrical column - Rating column *")
            cur.execute("""
                SELECT rating, COUNT(*)
                FROM staging.games
                GROUP BY rating
                ORDER BY COUNT(*) DESC
            """)
            for rating, count in cur.fetchall():
                print(f"-> {rating}: {count}")

if __name__ == "__main__":
    run()
