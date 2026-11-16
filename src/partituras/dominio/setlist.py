"""Set list: leitura do texto do usuário e ligação de cada item a uma música.

SET-07: aceitar listas numeradas, marcadores, travessões, uma música por linha,
blocos e bis; ignorar só cabeçalhos, datas, locais, horários, seções e
observações inequívocos. Uma linha que não seja inequivocamente um desses
resíduos é tratada como música.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass

from partituras.dominio.modelos import ItemSetlist, Musica
from partituras.dominio.nomes import Candidato, Correspondencia, Situacao, corresponder

_PREFIXO = re.compile(r"^\s*(?:\d{1,3}\s*[.)\-–—:]\s*|[-–—•*·▪►>]+\s*)")
_IGNORAR = [
    re.compile(r"^set\s*-?\s*list\b.*$", re.I),
    re.compile(r"^repert[óo]rio\b.*$", re.I),
    re.compile(r"^(?:bloco|parte|set)\s*[\dA-Za-zºª]{0,3}\s*:?$", re.I),
    re.compile(r"^\d{1,2}\s*[ºª]?\s*(?:set|bloco|parte)\s*:?$", re.I),
    re.compile(r"^(?:intervalo|pausa)\b.*$", re.I),
    re.compile(r"^(?:obs|observa[çc][ãa]o|nota)\b.*$", re.I),
    re.compile(r"^(?:local|data|hor[áa]rio|endere[çc]o)\s*:.*$", re.I),
    re.compile(r"^\d{1,2}[/.-]\d{1,2}(?:[/.-]\d{2,4})?\b.*$"),
    re.compile(r"^\d{1,2}\s*(?:h|:)\s*\d{0,2}\s*(?:h|min)?$", re.I),
    re.compile(r"^\(.*\)$"),
]
_BIS = re.compile(r"^bis\s*:?\s*$", re.I)


@dataclass(frozen=True)
class LinhaSetlist:
    posicao: int
    titulo: str
    bis: bool


def ler_texto(texto: str) -> list[LinhaSetlist]:
    """Converte o texto colado pelo usuário em itens na ordem."""
    itens: list[LinhaSetlist] = []
    em_bis = False
    for bruta in texto.splitlines():
        linha = bruta.strip()
        if not linha:
            continue
        if _BIS.match(linha):
            em_bis = True
            continue
        if any(p.match(linha) for p in _IGNORAR):
            continue
        titulo = _PREFIXO.sub("", linha, count=1).strip()
        bis = em_bis
        marcado = re.match(r"^bis\s*[:\-–—]\s*(.+)$", titulo, re.I)
        if marcado:
            titulo, bis = marcado.group(1).strip(), True
        if titulo:
            itens.append(LinhaSetlist(len(itens) + 1, titulo, bis))
    return itens


@dataclass(frozen=True)
class Resolucao:
    item: ItemSetlist
    correspondencia: Correspondencia | None


def resolver(
    titulos: Sequence[str],
    musicas: Sequence[Musica],
    grupos_existentes: Sequence[str | None] | None = None,
) -> list[Resolucao]:
    """Liga cada título a uma música.

    Se `grupos_existentes[i]` já aponta para uma música que existe, a ligação
    declarada é mantida sem recalcular (ligação explícita vale mais que nome).
    Caso contrário, usa `corresponder`, que levanta `Ambiguidade` quando não há
    escolha segura (NOM-04). Música não encontrada fica sem grupo (SET-09).
    """
    candidatos = [Candidato(m.grupo, m.titulo) for m in musicas]
    existentes = {m.grupo for m in musicas}
    resultado: list[Resolucao] = []
    for i, titulo in enumerate(titulos):
        declarado = grupos_existentes[i] if grupos_existentes else None
        if declarado and declarado in existentes:
            resultado.append(Resolucao(ItemSetlist(i + 1, titulo, declarado), None))
            continue
        c = corresponder(titulo, candidatos)
        grupo = c.escolhido.chave if c.situacao is not Situacao.AUSENTE else None
        resultado.append(Resolucao(ItemSetlist(i + 1, titulo, grupo), c))
    return resultado
