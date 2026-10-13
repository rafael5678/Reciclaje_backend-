from app.database import get_conn

SCAN_COLUMNS = """
    id, user_id, material_code, object_name, confidence,
    separated_well, points, weight_kg, co2_kg, created_at,
    (photo IS NOT NULL) AS has_photo
"""


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
                f"""
                SELECT {SCAN_COLUMNS} FROM scans
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
        photo: bytes | None = None,
    ) -> dict:
        conn = get_conn()
        try:
            row = conn.execute(
                f"""
                INSERT INTO scans (
                    user_id, material_code, object_name, confidence,
                    separated_well, points, weight_kg, co2_kg, created_at, photo
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                RETURNING {SCAN_COLUMNS}
                """,
                (
                    user_id,
                    material_code,
                    object_name,
                    confidence,
                    bool(separated_well),
                    points,
                    weight_kg,
                    co2_kg,
                    created_at,
                    photo,
                ),
            ).fetchone()
            conn.commit()
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

    def photo_for(self, user_id: int, scan_id: int) -> bytes | None:
        conn = get_conn()
        try:
            row = conn.execute(
                "SELECT photo FROM scans WHERE id = ? AND user_id = ?",
                (scan_id, user_id),
            ).fetchone()
            if row is None or row["photo"] is None:
                return None
            return bytes(row["photo"])
        finally:
            conn.close()
