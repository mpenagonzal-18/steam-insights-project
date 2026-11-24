from psycopg2 import sql
from db_conn import get_connection, db_name

def run():
    print("CONNECTING TO POSTGRESQL...")
    with get_connection(dbname="postgres", autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (db_name,))
            if cur.fetchone() is None:
                cur.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(db_name)))
                print(f"Database '{db_name}' created successfully.")
            else:
                print(f"Database '{db_name}' already exists.")

if __name__ == "__main__":
    run()
