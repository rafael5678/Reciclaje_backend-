"""Sanitize login fields. Names allow one space; passwords do not."""
import re

from fastapi import HTTPException

NAME_PATTERN = re.compile(r"^[A-Za-zÁÉÍÓÚáéíóúÑñÜü]+(?: [A-Za-zÁÉÍÓÚáéíóúÑñÜü]+)*$")
EMAIL_PATTERN = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


class Credentials:
    def email(self, value: str) -> str:
        cleaned = "".join(value.split()).lower()
        if not EMAIL_PATTERN.match(cleaned):
            raise HTTPException(status_code=400, detail="Escribe un correo válido, sin espacios")
        return cleaned

    def password(self, value: str) -> str:
        if any(character.isspace() for character in value):
            raise HTTPException(status_code=400, detail="La contraseña no puede tener espacios")
        if len(value) < 6:
            raise HTTPException(status_code=400, detail="Mínimo 6 caracteres, sin espacios")
        if len(value) > 80:
            raise HTTPException(status_code=400, detail="La contraseña es demasiado larga")
        return value

    def name(self, value: str) -> str:
        cleaned = " ".join(value.split())
        if len(cleaned) < 2:
            raise HTTPException(status_code=400, detail="Escribe tu nombre (como Rafael Calzada)")
        if len(cleaned) > 80:
            raise HTTPException(status_code=400, detail="El nombre es demasiado largo")
        if not NAME_PATTERN.match(cleaned):
            raise HTTPException(status_code=400, detail="Usa solo letras y un espacio entre nombres")
        if len(cleaned.split(" ")) > 5:
            raise HTTPException(status_code=400, detail="El nombre tiene demasiadas palabras")
        return cleaned


credentials = Credentials()
