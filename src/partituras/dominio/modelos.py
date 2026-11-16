"""Modelo do repertório, independente do formato HTML."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class Papel(StrEnum):
    SETLIST = "setlist"
    INDICE = "index"
    PARTITURA = "score"
    AUXILIAR = "auxiliar"


@dataclass(frozen=True)
class Pagina:
    """Uma `section.slide` do HTML canônico, na ordem do arquivo."""

    id: str
    papel: Papel
    musica: str | None = None
    grupo: str | None = None
    parte: int | None = None
    total_partes: int | None = None


@dataclass(frozen=True)
class Musica:
    """Grupo de páginas consecutivas de uma mesma música (MULTI-01)."""

    grupo: str
    titulo: str
    paginas: tuple[str, ...]

    @property
    def primeira_pagina(self) -> str:
        return self.paginas[0]


@dataclass(frozen=True)
class ItemSetlist:
    """Item do set list. `grupo` vazio significa música sem partitura (SET-09)."""

    posicao: int
    titulo: str
    grupo: str | None = None


@dataclass
class Repertorio:
    paginas: list[Pagina]
    setlist: list[ItemSetlist] | None = None
    tem_indice: bool = False
    musicas: list[Musica] = field(default_factory=list)

    @property
    def pagina_inicial(self) -> str:
        """Destino dos links de título e `ABC` (LNK-01, SET-01, SET-08)."""
        if self.setlist is not None:
            return "setlist"
        if self.tem_indice:
            return "index"
        return self.paginas[0].id if self.paginas else ""

    def musica(self, grupo: str) -> Musica | None:
        return next((m for m in self.musicas if m.grupo == grupo), None)
