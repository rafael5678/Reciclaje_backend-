from app.models.catalog import BY_CODE


def award_points(material_code: str, confidence: float, separated_well: bool) -> tuple[int, list[str]]:
    material = BY_CODE.get(material_code) or BY_CODE["GEN"]
    points = 8
    why = ["8 por identificar el objeto"]
    if material["recyclable"]:
        points += 4
        why.append("4 porque sí se aprovecha")
    else:
        points += 3
        why.append("3 por no mezclarlo con el reciclaje")
    if separated_well:
        points += 4
        why.append("4 por separarlo bien")
    if confidence >= 0.85:
        points += 2
        why.append("2 por una detección clara")
    return points, why
