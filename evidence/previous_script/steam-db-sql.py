import psycopg2
import kagglehub
import shutil
from pathlib import Path

# DESCARGA EL DATASET
cache_path = Path(
    kagglehub.dataset_download(
        "antonkozyriev/game-recommendations-on-steam"
    )
)
# MOVEMOS EL DATASET DESDE LA CACHÉ AL DIRECTORIO NUEVO
target_dir = Path("./data/raw")
target_dir.mkdir(parents = True, exist_ok = True)

shutil.copytree(cache_path, target_dir, dirs_exist_ok=True)

data_path = target_dir

print("Dataset location:", data_path)
# COMPROBACIÓN SI HA IMPORTADO psycopg2 CORRECTAMENTE
print(f"Using psycopg2 version {psycopg2.__version__}")

# CONEXIÓN A LA BASE DE DATOS
print("CONNECTING TO POSTGRESQL... PLEASE WAIT")
with open("password.txt") as f:
    password = f.read().strip()

conn = psycopg2.connect(
    host = 'localhost',
    port = 5432,
    dbname = 'postgres',
    user = 'postgres',
    password = password
)

# CREACIÓN / LECTURA DE LA BASE DE DATOS
print("SUCCESSFULLY CONNECTED TO POSTGRESQL. ")
conn.autocommit = True
cur = conn.cursor()
database_name = "steam_db"

cur.execute(
    "SELECT 1 FROM pg_database WHERE datname = %s",
    (database_name,)
)

if cur.fetchone() is None:
    cur.execute(
        f'CREATE DATABASE "{database_name}"'
    )
    print(f"Database '{database_name}' created successfully.")
else:
    print(f"Database '{database_name}' already exists.")

cur.close()
conn.close()

# INSERCIÓN DE LOS DATOS NUEVOS
conn = psycopg2.connect(
    host="localhost",
    port=5432,
    dbname=database_name,
    user="postgres",
    password=password
)
cur = conn.cursor()

print("Connected to steam_db successfully.")
print(f"---- PART A: DATA LAYER OF {database_name} ----\n*** DATA ANALYSIS ***")
print("Creating all the tables in the database...")

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

print("Staging tables created successfully. Importing the data...")
files = {
    "games.csv": "staging.games",
    "users.csv": "staging.users",
    "recommendations.csv": "staging.recommendations"
}
try:
    with conn.cursor() as cur:
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

        # Confirmar la transacción completa
        conn.commit()
        print("All files have been properly imported. Carrying out the desired Data Analysis...")
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
            print(f"-> Are there nulls in {table}?: {cur.fetchone()}")
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
                SELECT DISTINCT COUNT(*) as unique_samples
                FROM {table};
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
except Exception as e:
    # Deshacer toda la importación si hay un error
    conn.rollback()
    print("There was an error when importing/analyzing the data:", e)

finally:
    print("DATA ANALYSIS CONCLUDED.")
    conn.close()
print("*** RELATIONAL MODEL AND ER DIAGRAM ***")
evidence_dir = Path("./evidence")
print(f"ER diagram directory: '{evidence_dir/"er_diagram.png"}'")
print(f"Relational model directory: '{evidence_dir/"relational_model.png"}'")
# REALIZAMOS CONEXIÓN NUEVA
conn = psycopg2.connect(
    host="localhost",
    port=5432,
    dbname=database_name,
    user="postgres",
    password=password
)
cur = conn.cursor()
print("*** PYTHON SCHEMA ***")
# Como se ve en las fotos de los modelos, hay ciertas tablas como la de plataformas que ya deben tener los valores.
print("\nCREATING RELATIONAL MODEL...")
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
conn.commit()
print("Relational schema created successfully.")

import json
from psycopg2.extras import execute_values

print("\nINSERTING DATA INTO RELATIONAL MODEL...")

# Ruta del JSON descargado mediante kagglehub
metadata_path = data_path / "games_metadata.json"
try:
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
    # CONFIRM ALL INSERTIONS
    conn.commit()
    print("\nALL DATA INSERTED SUCCESSFULLY.")

except Exception as e:
    # UNDO ALL INSERTIONS
    conn.rollback()
    print("\nERROR: TRANSACTION ROLLED BACK.")
    print(e)
    raise