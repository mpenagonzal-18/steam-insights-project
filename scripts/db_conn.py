from pathlib import Path
import psycopg2

root = Path(__file__).resolve().parent.parent # Como esta en root/scripts/, hay que ponerlo así
db_name = "steam_db"

def get_connection(dbname = db_name, autocommit = False):
    # Creamos una nueva conexión a la base de datos, cada script llama a esto
    # LECTURA DE CONTRASEÑA
    with open(root / "password.txt") as f:
        password = f.read().strip()
    # CONEXIÓN A steam_db
    conn = psycopg2.connect(
        host = 'localhost',
        port = 5432,
        dbname = dbname,
        user = 'postgres',
        password = password
    )
    conn.autocommit = autocommit
    return conn
