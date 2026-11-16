"""Normalização e correspondência de nomes de músicas (NOM-01 a NOM-05).

A fórmula de similaridade é a mesma da versão ChatGPT, para que os scores
registrados nos relatórios continuem comparáveis. A diferença é que cada música
entra uma vez como candidata (por grupo), e não uma vez por página.
"""

from __future__ import annotations

import difflib
import re
import unicodedata
from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum

from partituras.dominio.erros import Ambiguidade

LIMIAR_MINIMO = 0.68
LIMIAR_SEGURO = 0.80
DIFERENCA_MINIMA = 0.08
SCORE_CONTIDO = 0.92


def sem_acentos(texto: str) -> str:
    decomposto = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in decomposto if not unicodedata.combining(c))


def normalizar(texto: str) -> str:
    """Forma comparável: sem acentos, minúscula, sem parênteses, `ABC` nem cifras soltas."""
    texto = sem_acentos(texto or "").lower()
    texto = re.sub(r"\([^)]*\)", " ", texto)
    texto = re.sub(r"\babc\b", " ", texto)
    texto = re.sub(r"\b[a-g](?:#|b)?m?\b", " ", texto)
    texto = re.sub(r"[^a-z0-9]+", " ", texto)
    return re.sub(r"\s+", " ", texto).strip()


def slug(texto: str) -> str:
    """Identificador estável de grupo (`data-group`)."""
    base = re.sub(r"[^a-z0-9]+", "-", sem_acentos(texto or "").lower()).strip("-")
    return base or "musica"


def chave_ordenacao(texto: str) -> str:
    """Ordem alfabética ignorando acentos e maiúsculas (IDX-02)."""
    return sem_acentos(texto or "").casefold()


def normalizar_forte(texto: str) -> str:
    """Igualdade de grafia ignorando só acentos, maiúsculas e espaços extras.

    Desempata títulos que `normalizar` torna iguais, como "Coração Partido" e
    "Coração Partido (graus)".
    """
    return re.sub(r"\s+", " ", chave_ordenacao(texto)).strip()


def similaridade(a: str, b: str) -> float:
    na, nb = normalizar(a), normalizar(b)
    if not na or not nb:
        return 0.0
    if na == nb:
        return 1.0
    # Abreviação: um nome contido no outro como palavras inteiras ("Reburial" em
    # "The Reburial"). "Lidio" dentro de "Mixolidio" não conta.
    if f" {na} " in f" {nb} " or f" {nb} " in f" {na} ":
        return SCORE_CONTIDO
    return difflib.SequenceMatcher(None, na, nb).ratio()


class Situacao(StrEnum):
    EXATA = "exata"
    APROXIMADA = "aproximada"
    AUSENTE = "ausente"


@dataclass(frozen=True)
class Candidato:
    chave: str
    titulo: str


@dataclass(frozen=True)
class Correspondencia:
    """Registro de uma correspondência (NOM-02)."""

    procurado: str
    situacao: Situacao
    escolhido: Candidato | None
    melhor_score: float
    segundo: Candidato | None
    segundo_score: float

    @property
    def diferenca(self) -> float:
        return round(self.melhor_score - self.segundo_score, 6)

    def como_dict(self) -> dict:
        return {
            "procurado": self.procurado,
            "situacao": str(self.situacao),
            "escolhido": self.escolhido.titulo if self.escolhido else None,
            "grupo": self.escolhido.chave if self.escolhido else None,
            "melhor_score": round(self.melhor_score, 3),
            "segundo": self.segundo.titulo if self.segundo else None,
            "segundo_score": round(self.segundo_score, 3),
            "diferenca": round(self.diferenca, 3),
        }


def corresponder(procurado: str, candidatos: Sequence[Candidato]) -> Correspondencia:
    """Encontra a música correspondente.

    - igualdade normalizada exata vence sempre, se for única;
    - abaixo de LIMIAR_MINIMO a música é ausente;
    - entre LIMIAR_MINIMO e LIMIAR_SEGURO é ambiguidade (música ou ausente?);
    - diferença menor que DIFERENCA_MINIMA entre os dois melhores é ambiguidade.

    Levanta `Ambiguidade` em vez de escolher (NOM-04).
    """
    unicos: dict[str, Candidato] = {}
    for candidato in candidatos:
        unicos.setdefault(candidato.chave, candidato)
    pontuados = sorted(
        ((similaridade(procurado, c.titulo), c) for c in unicos.values()),
        key=lambda par: par[0],
        reverse=True,
    )
    if not pontuados:
        return Correspondencia(procurado, Situacao.AUSENTE, None, 0.0, None, 0.0)

    alvo = normalizar(procurado)
    exatos = [c for _, c in pontuados if normalizar(c.titulo) == alvo]
    if len(exatos) > 1:
        forte = normalizar_forte(procurado)
        exatos = [c for c in exatos if normalizar_forte(c.titulo) == forte] or exatos
    if len(exatos) > 1:
        raise Ambiguidade(
            f'"{procurado}" corresponde exatamente a mais de uma música: '
            + ", ".join(c.titulo for c in exatos)
        )

    melhor_score, melhor = pontuados[0]
    segundo_score, segundo = pontuados[1] if len(pontuados) > 1 else (0.0, None)

    if exatos:
        escolhido = exatos[0]
        outros = [(score, c) for score, c in pontuados if c.chave != escolhido.chave]
        segundo_score, segundo = outros[0] if outros else (0.0, None)
        return Correspondencia(procurado, Situacao.EXATA, escolhido, 1.0, segundo, segundo_score)
    if melhor_score < LIMIAR_MINIMO:
        return Correspondencia(
            procurado, Situacao.AUSENTE, None, melhor_score, melhor, segundo_score
        )
    if melhor_score < LIMIAR_SEGURO:
        raise Ambiguidade(
            f'"{procurado}" lembra "{melhor.titulo}" ({melhor_score:.3f}), mas a semelhança é '
            f"baixa: pode ser essa música ou uma música sem partitura. Confirme o nome."
        )
    if segundo is not None and melhor_score - segundo_score < DIFERENCA_MINIMA:
        raise Ambiguidade(
            f'"{procurado}" é ambíguo: "{melhor.titulo}" ({melhor_score:.3f}) e '
            f'"{segundo.titulo}" ({segundo_score:.3f}); diferença menor que {DIFERENCA_MINIMA}.'
        )
    return Correspondencia(
        procurado, Situacao.APROXIMADA, melhor, melhor_score, segundo, segundo_score
    )
