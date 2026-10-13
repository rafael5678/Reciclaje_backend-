import random
from collections import defaultdict
from datetime import datetime, timedelta

from app.models.catalog import BY_CODE
from app.repositories.scan_repository import ScanRepository
from app.repositories.user_repository import UserRepository
from app.services.security import hash_password

user_repository = UserRepository()
scan_repository = ScanRepository()

WEEK_PLAN = [(6, 4), (5, 7), (4, 3), (3, 9), (2, 6), (1, 9), (0, 12)]
PREVIOUS_PLAN = [(13, 6), (12, 5), (11, 7), (10, 6), (9, 5), (8, 7), (7, 6)]


def seed_if_empty() -> None:
    demo = user_repository.get_by_email("rafael@ecoscan.app")
    if demo is None:
        created = datetime.now().astimezone().isoformat(timespec="seconds")
        demo = user_repository.create(
            "Rafael Gonzalez",
            "rafael@ecoscan.app",
            hash_password("ecoscan123"),
            created,
        )
    if scan_repository.count_for(demo["id"]) == 0:
        scan_repository.insert_many(_historical_rows(demo["id"]))


def _historical_rows(user_id: int) -> list[tuple]:
    rng = random.Random(7)
    now = datetime.now().astimezone()
    today = now.date()
    pool = (
        ["PET"] * 29
        + ["HDPE"] * 13
        + ["MLT"] * 9
        + ["PAP"] * 30
        + ["VID"] * 16
        + ["MET"] * 13
        + ["ORG"] * 7
        + ["GEN"] * 2
    )
    rng.shuffle(pool)
    cursor = 0
    rows: list[tuple] = []
    placed: dict = defaultdict(int)

    featured = [
        ("PET", "Botella de agua", 0.96, 0, 15, 12, True),
        ("MLT", "Caja de leche", 0.94, 0, 14, 52, True),
        ("MET", "Lata de atún", 0.91, 0, 14, 40, True),
        ("VID", "Frasco de vidrio", 0.97, 0, 13, 5, True),
        ("HDPE", "Envase de champú", 0.93, 0, 9, 30, True),
        ("ORG", "Cáscara de banano", 0.89, 1, 20, 18, True),
        ("GEN", "Servilleta con grasa", 0.95, 1, 19, 30, True),
        ("PAP", "Caja de cartón", 0.98, 1, 11, 2, True),
        ("GEN", "Bolsa de snack", 0.87, 1, 18, 5, True),
    ]
    for code, name, confidence, days_ago, hour, minute, well in featured:
        day = today - timedelta(days=days_ago)
        rows.append(_row(user_id, code, name, confidence, well, day, hour, minute, now))
        placed[day] += 1

    def take_slot(day, night: bool, force_bad: bool):
        nonlocal cursor
        code = pool[cursor]
        cursor += 1
        material = BY_CODE[code]
        name = rng.choice(material["examples"])
        well = not force_bad
        confidence = rng.uniform(0.64, 0.8) if force_bad else rng.uniform(0.86, 0.99)
        hour = rng.choice([20, 21, 22]) if night else rng.randint(8, 12 if day == today else 18)
        minute = rng.randint(0, 59)
        rows.append(_row(user_id, code, name, round(confidence, 2), well, day, hour, minute, now))

    bad_left = 12
    night_left = 3
    targets: list = []
    for days_ago, count in WEEK_PLAN:
        day = today - timedelta(days=days_ago)
        missing = count - placed[day]
        targets.extend([day] * missing)
    for index, day in enumerate(targets):
        force_bad = bad_left > 0
        if force_bad:
            bad_left -= 1
        night = night_left > 0
        if night:
            night_left -= 1
        take_slot(day, night, force_bad)

    for days_ago, count in PREVIOUS_PLAN:
        day = today - timedelta(days=days_ago)
        for _ in range(count):
            force_bad = bad_left > 0
            if force_bad:
                bad_left -= 1
            take_slot(day, False, force_bad)

    for index in range(36):
        day = today - timedelta(days=14 + (index % 18))
        force_bad = bad_left > 0
        if force_bad:
            bad_left -= 1
        take_slot(day, False, force_bad)

    if cursor != len(pool):
        raise RuntimeError(f"Semilla inconsistente: {cursor} de {len(pool)}")
    return rows


def _row(user_id, code, name, confidence, well, day, hour, minute, now):
    material = BY_CODE[code]
    created = datetime(
        day.year,
        day.month,
        day.day,
        hour,
        minute,
        tzinfo=now.tzinfo,
    )
    if created > now:
        created = now - timedelta(minutes=8)
    return (
        user_id,
        code,
        name,
        confidence,
        1 if well else 0,
        10,
        material["weight_kg"],
        material["co2_kg"] if well else 0,
        created.isoformat(timespec="seconds"),
    )
