"""Sorting-lab bins and pieces. UI copy stays in Spanish."""

MISTAKE_COST = 5

BINS = [
    {"id": "yellow", "title": "Amarillo", "detail": "Plásticos y envases"},
    {"id": "blue", "title": "Azul", "detail": "Papel y cartón"},
    {"id": "green", "title": "Verde", "detail": "Vidrio"},
    {"id": "black", "title": "Negro", "detail": "No se recicla"},
    {"id": "brown", "title": "Marrón", "detail": "Orgánicos"},
]

PIECES = [
    {"id": "pet-cap", "title": "Tapa", "bin_id": "yellow", "hint": "La tapa es otro plástico. Quítala y tírala al amarillo, no pegada al PET."},
    {"id": "pet-label", "title": "Etiqueta", "bin_id": "blue", "hint": "Si es papel, pélala y va al azul. El adhesivo no es botella."},
    {"id": "pet-body", "title": "Cuerpo PET", "bin_id": "yellow", "hint": "Enjuaga, aplasta y deposita el cuerpo en el amarillo."},
    {"id": "glass-lid", "title": "Tapa de metal", "bin_id": "yellow", "hint": "El metal de la tapa va con envases, no con el vidrio."},
    {"id": "glass-body", "title": "Frasco de vidrio", "bin_id": "green", "hint": "Coge el vidrio por el cuerpo, enjuágalo y tira al verde. No lo rompas."},
    {"id": "paper-box", "title": "Cartón", "bin_id": "blue", "hint": "Cartón limpio y aplastado va al azul."},
    {"id": "paper-sheet", "title": "Papel", "bin_id": "blue", "hint": "Papel seco y sin grasa va al azul."},
    {"id": "peel", "title": "Cáscara", "bin_id": "brown", "hint": "Restos de comida van al marrón, sin bolsa plástica."},
    {"id": "napkin", "title": "Servilleta sucia", "bin_id": "black", "hint": "Papel sucio no se recicla. Va al negro."},
    {"id": "hdpe-cap", "title": "Tapa HDPE", "bin_id": "yellow", "hint": "La tapa va al amarillo, suelta del envase."},
    {"id": "hdpe-body", "title": "Envase HDPE", "bin_id": "yellow", "hint": "El envase opaco va al amarillo, enjuagado."},
    {"id": "mlt-pack", "title": "Caja multicapa", "bin_id": "yellow", "hint": "Parece cartón, pero va al amarillo, no al azul."},
    {"id": "met-can", "title": "Lata", "bin_id": "yellow", "hint": "Latas limpias van al amarillo, con los envases."},
]

BY_PIECE = {item["id"]: item for item in PIECES}
BY_BIN = {item["id"]: item for item in BINS}
