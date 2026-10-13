"""Textos de qué hacer con el objeto. Gemini los escribe; si no, usamos estos."""

from app.models.catalog import BY_CODE

SPECIAL = {
    "lapicero": {
        "meaning": "Es un bolígrafo. El cuerpo puede ser plástico, pero lleva tinta, metal y piezas mezcladas. En la ruta de reciclaje domiciliaria no se recupera como una botella.",
        "destination": "Contenedor negro: residuo no reciclable. No lo pongas en el amarillo.",
        "actions": ["No lo mezcles con botellas ni envases", "Si aún escribe, reúsalo o dónalo", "Si ya no sirve, bolsa de residuo general"],
        "tip": "Aunque sea transparente, no es PET de bebida. En el amarillo contamina el lote.",
    },
    "bolígrafo": {
        "meaning": "Es un bolígrafo o pluma. Combina plásticos distintos, tinta y a veces metal. No entra en el reciclaje de envases.",
        "destination": "Contenedor negro. Si tu ciudad tiene un punto de útiles o RAEE pequeño, pregúntalo; si no, va a general.",
        "actions": ["Reúsalo si todavía escribe", "No lo eches con las botellas", "Al terminar, bolsa negra aparte"],
        "tip": "Un solo bolígrafo en un saco de PET puede hacer que rechacen el lote.",
    },
    "lápiz": {
        "meaning": "Es un lápiz de madera y grafito. No es papel ni cartón reciclable de oficina.",
        "destination": "Contenedor negro. La madera tratada y el grafito no van al azul.",
        "actions": ["Úsalo hasta el final", "No lo metas con hojas ni cajas", "Descártalo en residuo general"],
        "tip": "El contenedor azul es solo para papel y cartón limpios, no para lápices.",
    },
    "control remoto": {
        "meaning": "Es un control remoto. Tiene carcasa plástica, circuitos y pilas. Es un aparato electrónico pequeño, no un envase.",
        "destination": "Las pilas van a un punto de pilas. El control, sin pilas, va a residuo general o a un punto de RAEE si tu municipio lo recibe.",
        "actions": ["Saca las pilas", "Lleva las pilas a un punto de recolección", "El control vacío no va al amarillo"],
        "tip": "Nunca lo tires con las pilas puestas: el ácido y los metales contaminan.",
    },
    "celular": {
        "meaning": "Es un teléfono. Tiene batería, metales y circuitos. No se tira a ningún contenedor de reciclaje de casa.",
        "destination": "Punto de RAEE, tienda de celulares o campaña de recolección. Nunca al negro con la batería si puedes evitarlo, y nunca al amarillo.",
        "actions": ["No lo rompas", "Borra tus datos si puedes", "Entrégalo en un punto de electrónicos"],
        "tip": "La batería es el riesgo. No la eches suelta a la basura.",
    },
    "papel higiénico": {
        "meaning": "Es papel higiénico. Aunque sea papel, ya está sucio y las fibras no sirven para reciclar.",
        "destination": "Contenedor negro. Nunca al azul.",
        "actions": ["No lo mezcles con hojas limpias", "Si está usado, va a general", "El cartón del tubo, si está limpio, sí puede ir al azul"],
        "tip": "El papel higiénico usado contamina todo el lote de papel.",
    },
    "botella": {
        "meaning": "Es una botella plástica de bebida (PET). Sí se recicla si va limpia y sola.",
        "destination": "Contenedor amarillo: plásticos y envases.",
        "actions": ["Vacía el líquido", "Enjuaga un poco", "Quita la tapa", "Aplástala para que ocupe menos"],
        "tip": "La tapa es otro plástico. Quítala para no mezclar resinas.",
    },
}


def fallback_guide(code: str, object_name: str) -> dict:
    key = (object_name or "").lower()
    for name, guide in SPECIAL.items():
        if name in key:
            return dict(guide)
    material = BY_CODE[code]
    bin_name = material["container"].lower()
    if material["recyclable"]:
        destination = f"Contenedor {bin_name}: {material['container_detail']}. Sí se puede reciclar si lo preparas bien."
    else:
        destination = f"Contenedor {bin_name}: {material['container_detail']}. No lo mezcles con material reciclable."
    return {
        "meaning": material["blurb"],
        "destination": destination,
        "actions": list(material["steps"]),
        "tip": material["warning"],
    }


def attach_guide(hit: dict, extra: dict | None = None) -> dict:
    base = fallback_guide(hit["material_code"], hit.get("object_name") or "")
    guide = dict(base)
    if extra:
        for field in ("meaning", "destination", "tip"):
            value = str(extra.get(field) or "").strip()
            if value:
                guide[field] = value[:420]
        actions = extra.get("actions")
        if isinstance(actions, list):
            clean = [str(item).strip()[:80] for item in actions if str(item).strip()]
            if clean:
                guide["actions"] = clean[:5]
    hit["guide"] = guide
    return hit
