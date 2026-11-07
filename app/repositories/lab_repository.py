"""lab_attempts table: sorting mistakes that adjust ranking points."""
from app.database import get_conn


class LabRepository:
    def insert(self, user_id: int, piece_id: str, bin_id: str, correct: bool, delta: int, created_at: str) -> None:
        conn = get_conn()
        try:
            conn.execute(
                """
                INSERT INTO lab_attempts (user_id, piece_id, bin_id, correct, delta, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (user_id, piece_id, bin_id, bool(correct), delta, created_at),
            )
            conn.commit()
        finally:
            conn.close()

    def delta_for(self, user_id: int) -> int:
        conn = get_conn()
        try:
            row = conn.execute(
                "SELECT COALESCE(SUM(delta), 0) AS total FROM lab_attempts WHERE user_id = ?",
                (user_id,),
            ).fetchone()
            return int(row["total"] if row else 0)
        finally:
            conn.close()


lab_repository = LabRepository()
