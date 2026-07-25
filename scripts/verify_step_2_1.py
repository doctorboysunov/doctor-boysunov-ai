from app.db.connection import get_connection, init_db

init_db()

with get_connection() as conn:
    tables = [
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
    ]

expected = {"conversations", "messages", "sqlite_sequence", "users"}
assert expected.issubset(set(tables)), tables
print("Step 2.1 OK:", tables)
