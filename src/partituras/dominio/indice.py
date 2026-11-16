"""Conteúdo e distribuição do índice (IDX-01 a IDX-04)."""

from __future__ import annotations

from dataclasses import dataclass

from partituras.dominio.modelos import Repertorio
from partituras.dominio.nomes import chave_ordenacao

LIMITE_ROTULO = 22
COLUNAS = 3


@dataclass(frozen=True)
class EntradaIndice:
    grupo: str
    titulo: str
    pagina: str

    @property
    def rotulo(self) -> str:
        """Texto exibido, limitado a 22 caracteres (IDX-03)."""
        return self.titulo[:LIMITE_ROTULO]


def entradas_indice(repertorio: Repertorio) -> list[EntradaIndice]:
    """Uma entrada por música, em ordem alfabética sem acentos nem maiúsculas.

    A ordenação é estável: títulos iguais mantêm a ordem do arquivo.
    """
    entradas = [EntradaIndice(m.grupo, m.titulo, m.primeira_pagina) for m in repertorio.musicas]
    return sorted(entradas, key=lambda e: chave_ordenacao(e.titulo))


def tamanhos_colunas(total: int) -> list[int]:
    """Distribuição equilibrada; as primeiras colunas recebem a sobra. 29 → [10, 10, 9]."""
    base, sobra = divmod(total, COLUNAS)
    return [base + (1 if i < sobra else 0) for i in range(COLUNAS)]


def colunas(entradas: list[EntradaIndice]) -> list[list[EntradaIndice]]:
    """Preenche a coluna 1 de cima para baixo, depois a 2, depois a 3 (IDX-04)."""
    resultado: list[list[EntradaIndice]] = []
    inicio = 0
    for tamanho in tamanhos_colunas(len(entradas)):
        resultado.append(entradas[inicio : inicio + tamanho])
        inicio += tamanho
    return resultado
