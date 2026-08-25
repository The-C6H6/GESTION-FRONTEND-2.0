from esiqie_dictamenes.core.errors import ValidationError

from .models import Inscrito
from .repository import AlumnoRepository


class AlumnoController:
    def __init__(self, repository: AlumnoRepository) -> None:
        self._repository = repository

    async def find_inscrito(self, boleta: str) -> Inscrito:
        normalized = boleta.strip()
        if not normalized:
            raise ValidationError("Escribe el número de boleta.")
        return await self._repository.get_inscrito(normalized)
