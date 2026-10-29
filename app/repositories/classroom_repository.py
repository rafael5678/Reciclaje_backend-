from datetime import datetime
from app.database import get_conn


class ClassroomRepository:
    def create(self, name: str, code: str, owner_id: int, created_at: str) -> dict:
        conn = get_conn()
        try:
            row = conn.execute(
                "INSERT INTO classrooms (name, code, owner_id, created_at) VALUES (?, ?, ?, ?) RETURNING id",
                (name.strip(), code, owner_id, created_at),
            ).fetchone()
            conn.execute(
                "INSERT INTO classroom_members (classroom_id, user_id, joined_at) VALUES (?, ?, ?)",
                (int(row["id"]), owner_id, created_at),
            )
            conn.commit()
            return self.get(int(row["id"])) or {}
        finally:
            conn.close()

    def get(self, classroom_id: int) -> dict | None:
        conn = get_conn()
        try:
            row = conn.execute("SELECT id, name, code, owner_id FROM classrooms WHERE id = ?", (classroom_id,)).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def by_code(self, code: str) -> dict | None:
        conn = get_conn()
        try:
            row = conn.execute("SELECT id, name, code, owner_id FROM classrooms WHERE code = ?", (code,)).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def for_user(self, user_id: int) -> list[dict]:
        conn = get_conn()
        try:
            rows = conn.execute(
                """
                SELECT c.id, c.name, c.code, c.owner_id,
                       (SELECT COUNT(*) FROM classroom_members other WHERE other.classroom_id = c.id) AS members
                FROM classrooms c
                JOIN classroom_members m ON m.classroom_id = c.id
                WHERE m.user_id = ?
                ORDER BY c.name
                """,
                (user_id,),
            ).fetchall()
            return [dict(row) for row in rows]
        finally:
            conn.close()

    def count_members(self, classroom_id: int) -> int:
        conn = get_conn()
        try:
            row = conn.execute("SELECT COUNT(*) AS n FROM classroom_members WHERE classroom_id = ?", (classroom_id,)).fetchone()
            return int(row["n"])
        finally:
            conn.close()

    def is_member(self, classroom_id: int, user_id: int) -> bool:
        conn = get_conn()
        try:
            row = conn.execute(
                "SELECT 1 AS ok FROM classroom_members WHERE classroom_id = ? AND user_id = ?",
                (classroom_id, user_id),
            ).fetchone()
            return row is not None
        finally:
            conn.close()

    def add_member(self, classroom_id: int, user_id: int, joined_at: str) -> None:
        conn = get_conn()
        try:
            conn.execute(
                "INSERT INTO classroom_members (classroom_id, user_id, joined_at) VALUES (?, ?, ?) ON CONFLICT DO NOTHING",
                (classroom_id, user_id, joined_at),
            )
            conn.commit()
        finally:
            conn.close()

    def remove_member(self, classroom_id: int, user_id: int) -> None:
        conn = get_conn()
        try:
            conn.execute("DELETE FROM classroom_members WHERE classroom_id = ? AND user_id = ?", (classroom_id, user_id))
            conn.commit()
        finally:
            conn.close()

    def delete(self, classroom_id: int) -> None:
        conn = get_conn()
        try:
            conn.execute("DELETE FROM classroom_members WHERE classroom_id = ?", (classroom_id,))
            conn.execute("DELETE FROM classrooms WHERE id = ?", (classroom_id,))
            conn.commit()
        finally:
            conn.close()

    def ranking(self, classroom_id: int, week_start: str) -> list[dict]:
        conn = get_conn()
        try:
            param_start = datetime.fromisoformat(week_start) if conn.postgres else week_start
            rows = conn.execute(
                """
                SELECT u.id AS user_id, u.name,
                       COUNT(s.id) AS scans,
                       COALESCE(SUM(s.points), 0) AS points,
                       COALESCE(SUM(s.co2_kg), 0) AS co2_kg,
                       COALESCE(SUM(CASE WHEN s.created_at >= ? THEN s.points ELSE 0 END), 0) AS week_points
                FROM classroom_members m
                JOIN users u ON u.id = m.user_id
                LEFT JOIN scans s ON s.user_id = u.id
                WHERE m.classroom_id = ?
                GROUP BY u.id, u.name
                ORDER BY points DESC, scans DESC, u.name
                """,
                (param_start, classroom_id),
            ).fetchall()
            return [dict(row) for row in rows]
        finally:
            conn.close()
