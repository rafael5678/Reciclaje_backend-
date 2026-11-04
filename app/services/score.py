"""Points from material, confidence, and sorting."""
from app.models.catalog import BY_CODE


class Score:
    def award(self, material_code: str, confidence: float, separated_well: bool) -> tuple[int, list[str]]:
        """Compute points and the reasons shown in the UI."""
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


score = Score()


def award_points(material_code: str, confidence: float, separated_well: bool) -> tuple[int, list[str]]:
    return score.award(material_code, confidence, separated_well)
