from app.database import get_conn


class UserRepository:
    def count(self) -> int:
        conn = get_conn()
        try:
            row = conn.execute("SELECT COUNT(*) AS n FROM users").fetchone()
            return int(row["n"])
        finally:
            conn.close()

    def get_by_id(self, user_id: int) -> dict | None:
        conn = get_conn()
        try:
            row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def get_by_email(self, email: str) -> dict | None:
        conn = get_conn()
        try:
            row = conn.execute(
                "SELECT * FROM users WHERE email = ?",
                (email.lower().strip(),),
            ).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def delete(self, user_id: int) -> None:
        conn = get_conn()
        try:
            conn.execute("DELETE FROM classroom_members WHERE user_id = ?", (user_id,))
            conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
            conn.commit()
        finally:
            conn.close()

    def create(self, name: str, email: str, password_hash: str, created_at: str) -> dict:
        conn = get_conn()
        try:
            row = conn.execute(
                """
                INSERT INTO users (name, email, password_hash, created_at)
                VALUES (?, ?, ?, ?)
                RETURNING id
                """,
                (name.strip(), email.lower().strip(), password_hash, created_at),
            ).fetchone()
            conn.commit()
            user_id = int(row["id"])
        finally:
            conn.close()
        user = self.get_by_id(user_id)
        if user is None:
            raise RuntimeError("No se pudo crear el usuario")
        return user
