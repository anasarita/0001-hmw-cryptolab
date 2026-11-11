import os
import sqlite3

def reset_db():
    db_file = "cryptolab.db"
    if os.path.exists(db_file):
        conn = sqlite3.connect(db_file)
        cur = conn.cursor()
        cur.execute("DELETE FROM transactions;")
        cur.execute("DELETE FROM participants;")
        cur.execute("DELETE FROM rooms;")
        cur.execute("DELETE FROM admin_audit_log;")
        conn.commit()
        conn.close()
        print("[OK] Base de datos 'cryptolab.db' reiniciada con exito.")
        print("     Todas las salas y transacciones de prueba han sido limpiadas.")
        print("     El usuario administrador configurado en .env y las tablas base se conservan.")
    else:
        print("[!] No existe 'cryptolab.db' para reiniciar.")

if __name__ == "__main__":
    reset_db()
