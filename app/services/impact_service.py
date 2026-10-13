from datetime import datetime, timedelta

from app.models.catalog import CATEGORY_COLORS, CATEGORY_ORDER
from app.models.schemas import CategoryCount, DayCount, ImpactOut
from app.repositories.scan_repository import ScanRepository
from app.services.scan_service import present_scan

scan_repository = ScanRepository()
WEEKDAYS = ["lun", "mar", "mié", "jue", "vie", "sáb", "dom"]


def _parse(value: str) -> datetime:
    return datetime.fromisoformat(value)


class ImpactService:
    def for_user(self, user_id: int) -> ImpactOut:
        rows = scan_repository.list_by_user(user_id)
        scans = [present_scan(row) for row in rows]
        now = datetime.now().astimezone()
        today = now.date()
        last7 = {today - timedelta(days=offset) for offset in range(7)}
        previous7 = {today - timedelta(days=offset) for offset in range(7, 14)}

        def on_dates(dates: set) -> list:
            return [scan for scan in scans if _parse(scan.created_at).date() in dates]

        week = on_dates(last7)
        prev = on_dates(previous7)
        today_scans = [scan for scan in scans if _parse(scan.created_at).date() == today]
        night = [
            scan
            for scan in week
            if _parse(scan.created_at).hour >= 19 or _parse(scan.created_at).hour < 6
        ]
        total = len(scans)
        well = sum(1 for scan in scans if scan.separated_well)
        points = sum(scan.points for scan in scans)
        weight = round(sum(scan.weight_kg for scan in scans), 2)
        co2 = round(sum(scan.co2_kg for scan in scans), 2)
        week_change = _change(len(week), len(prev))

        weekly: list[DayCount] = []
        for offset in range(6, -1, -1):
            day = today - timedelta(days=offset)
            count = sum(1 for scan in scans if _parse(scan.created_at).date() == day)
            label = "Hoy" if offset == 0 else f"{WEEKDAYS[day.weekday()]} {day.day}"
            weekly.append(DayCount(label=label, count=count, is_today=offset == 0))

        grouped = {name: 0 for name in CATEGORY_ORDER}
        for scan in scans:
            grouped[scan.category] = grouped.get(scan.category, 0) + 1
        categories = _categories(grouped, total)

        return ImpactOut(
            total=total,
            well_percent=0 if total == 0 else round(100 * well / total),
            today=len(today_scans),
            last7=len(week),
            previous7=len(prev),
            night=len(night),
            week_change_percent=week_change,
            points=points,
            weight_kg=weight,
            co2_kg=co2,
            weekly=weekly,
            categories=categories,
            recent=scans[:8],
        )


def _change(current: int, previous: int) -> int:
    if previous == 0:
        return 100 if current else 0
    return round((current - previous) * 100 / previous)


def _categories(grouped: dict[str, int], total: int) -> list[CategoryCount]:
    if total == 0:
        return [
            CategoryCount(name=name, count=0, percent=0, color=CATEGORY_COLORS[name])
            for name in CATEGORY_ORDER
        ]
    raw = [round(100 * grouped[name] / total) for name in CATEGORY_ORDER]
    drift = 100 - sum(raw)
    if raw:
        richest = max(range(len(raw)), key=lambda index: grouped[CATEGORY_ORDER[index]])
        raw[richest] += drift
    return [
        CategoryCount(
            name=name,
            count=grouped[name],
            percent=raw[index],
            color=CATEGORY_COLORS[name],
        )
        for index, name in enumerate(CATEGORY_ORDER)
    ]


impact_service = ImpactService()
