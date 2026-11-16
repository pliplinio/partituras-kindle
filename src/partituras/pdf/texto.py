"""Linhas de texto com posição, para localizar rótulos e conferir links."""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass

import pymupdf

from partituras.dominio.nomes import DIFERENCA_MINIMA, normalizar, similaridade


@dataclass(frozen=True)
class Linha:
    texto: str
    rect: pymupdf.Rect


def linhas(pagina: pymupdf.Page) -> list[Linha]:
    """Linhas reconstruídas a partir das palavras, de cima para baixo."""
    grupos: dict[tuple[int, int], list] = defaultdict(list)
    for palavra in pagina.get_text("words"):
        grupos[(int(palavra[5]), int(palavra[6]))].append(palavra)
    resultado = []
    for palavras in grupos.values():
        palavras.sort(key=lambda p: p[7])
        texto = " ".join(p[4] for p in palavras).strip()
        if not texto:
            continue
        rect = pymupdf.Rect(palavras[0][:4])
        for p in palavras[1:]:
            rect |= pymupdf.Rect(p[:4])
        resultado.append(Linha(texto, rect))
    resultado.sort(key=lambda linha: (round(linha.rect.y0, 1), linha.rect.x0))
    return resultado


def melhor_linha(
    candidatas: list[Linha], alvo: str, usadas: set[int], minimo: float
) -> tuple[int, Linha, float] | None:
    """Linha de maior similaridade lexical; posição só desempata (NOM-05).

    Ignora o número inicial de linhas como "1. Música".
    """
    alvo_n = normalizar(alvo)
    melhor: tuple[int, Linha, float] | None = None
    for i, linha in enumerate(candidatas):
        if i in usadas:
            continue
        texto_n = normalizar(linha.texto)
        sem_numero = re.sub(r"^\s*\d+\s*", "", texto_n).strip()
        score = max(similaridade(alvo_n, texto_n), similaridade(alvo_n, sem_numero))
        if score < minimo:
            continue
        if (
            melhor is None
            or score > melhor[2] + 1e-9
            or (abs(score - melhor[2]) <= 1e-9 and linha.rect.y0 < melhor[1].rect.y0)
        ):
            melhor = (i, linha, score)
    return melhor


def linha_exata(
    candidatas: list[Linha], alvo: str, usadas: set[int]
) -> tuple[int, Linha, float] | None:
    """Igualdade normalizada primeiro; aproximação só ≥ 0,90 e sem empate (IDX-07, VAL-03)."""
    alvo_n = normalizar(alvo)
    exatas, aproximadas = [], []
    for i, linha in enumerate(candidatas):
        if i in usadas:
            continue
        texto_n = normalizar(linha.texto)
        if not texto_n:
            continue
        if texto_n == alvo_n:
            exatas.append((i, linha, 1.0))
            continue
        score = similaridade(alvo_n, texto_n)
        if score >= 0.90:
            aproximadas.append((i, linha, score))
    if exatas:
        return min(exatas, key=lambda r: (r[1].rect.y0, r[1].rect.x0))
    if not aproximadas:
        return None
    aproximadas.sort(key=lambda r: (-r[2], r[1].rect.y0, r[1].rect.x0))
    if len(aproximadas) > 1 and aproximadas[0][2] - aproximadas[1][2] < DIFERENCA_MINIMA:
        return None
    return aproximadas[0]


def destino(link: dict) -> int | None:
    if link.get("kind") == pymupdf.LINK_GOTO and isinstance(link.get("page"), int):
        return link["page"]
    return None


def cobertura(link_rect: pymupdf.Rect, texto_rect: pymupdf.Rect) -> float:
    """Fração da área do texto coberta pelo link (LNK-07)."""
    area = texto_rect.get_area()
    if area <= 0:
        return 0.0
    return (pymupdf.Rect(link_rect) & texto_rect).get_area() / area


def links_sobre(pagina: pymupdf.Page, rect: pymupdf.Rect) -> list[dict]:
    """Links cujo retângulo contém o centro do texto."""
    centro = pymupdf.Point((rect.x0 + rect.x1) / 2, (rect.y0 + rect.y1) / 2)
    return [link for link in pagina.get_links() if pymupdf.Rect(link["from"]).contains(centro)]
