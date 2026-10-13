from app.database import get_conn


class ScanRepository:
    def count_for(self, user_id: int) -> int:
        conn = get_conn()
        try:
            row = conn.execute(
                "SELECT COUNT(*) AS n FROM scans WHERE user_id = ?",
                (user_id,),
            ).fetchone()
            return int(row["n"])
        finally:
            conn.close()

    def list_by_user(self, user_id: int) -> list[dict]:
        conn = get_conn()
        try:
            rows = conn.execute(
                """
                SELECT * FROM scans
                WHERE user_id = ?
                ORDER BY created_at DESC, id DESC
                """,
                (user_id,),
            ).fetchall()
            return [dict(row) for row in rows]
        finally:
            conn.close()

    def insert(
        self,
        user_id: int,
        material_code: str,
        object_name: str,
        confidence: float,
        separated_well: bool,
        points: int,
        weight_kg: float,
        co2_kg: float,
        created_at: str,
    ) -> dict:
        conn = get_conn()
        try:
            cur = conn.execute(
                """
                INSERT INTO scans (
                    user_id, material_code, object_name, confidence,
                    separated_well, points, weight_kg, co2_kg, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    user_id,
                    material_code,
                    object_name,
                    confidence,
                    1 if separated_well else 0,
                    points,
                    weight_kg,
                    co2_kg,
                    created_at,
                ),
            )
            conn.commit()
            scan_id = cur.lastrowid
            row = conn.execute("SELECT * FROM scans WHERE id = ?", (scan_id,)).fetchone()
            return dict(row)
        finally:
            conn.close()

    def insert_many(self, rows: list[tuple]) -> None:
        conn = get_conn()
        try:
            conn.executemany(
                """
                INSERT INTO scans (
                    user_id, material_code, object_name, confidence,
                    separated_well, points, weight_kg, co2_kg, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                rows,
            )
            conn.commit()
        finally:
            conn.close()
