"""Gate de escopo da substituição simples de música (VAL-04).

Prova que a edição mexeu só no grupo alvo: o restante do HTML continua igual.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from partituras.dominio.erros import Inconsistencia
from partituras.dominio.modelos import Papel
from partituras.html.documento import Documento, atributos

_CABECA = re.compile(r"^.*?</head>", re.I | re.S)


@dataclass
class RelatorioEscopo:
    grupo: str
    violacoes: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.violacoes


def _cabeca(doc: Documento) -> str:
    m = _CABECA.search(doc.texto)
    return m.group(0) if m else ""


def _secoes_fora(doc: Documento, grupo: str) -> list[str]:
    return [
        s.texto
        for s in doc.secoes
        if s.papel in (Papel.PARTITURA, Papel.AUXILIAR) and s.attrs.get("data-group") != grupo
    ]


def verificar(antes: Documento, depois: Documento, grupo: str) -> RelatorioEscopo:
    rel = RelatorioEscopo(grupo)
    v = rel.violacoes
    ra, rd = antes.repertorio(), depois.repertorio()

    if rd.musica(grupo) is None:
        v.append(f"grupo alvo {grupo} ausente do candidato")
    if _cabeca(antes) != _cabeca(depois):
        v.append("CSS ou template global mudou")
    if antes.versao_template != depois.versao_template:
        v.append("versão de template mudou")
    if _secoes_fora(antes, grupo) != _secoes_fora(depois, grupo):
        v.append("páginas de outras músicas ou auxiliares mudaram")
    if [m.grupo for m in ra.musicas] != [m.grupo for m in rd.musicas]:
        v.append("grupos inseridos, removidos ou reordenados")
    if ra.setlist != rd.setlist:
        v.append("set list mudou (posições, títulos ou grupos)")
    if _indice(antes) != _indice(depois):
        v.append("índice mudou de conjunto ou ordem")
    return rel


def _indice(doc: Documento) -> list[tuple[str | None, str | None]]:
    """Conjunto e ordem do índice; o destino (href) pode mudar com o grupo alvo."""
    secao = doc.secao(Papel.INDICE)
    if secao is None:
        return []
    itens = (atributos(m) for m in re.findall(r"<a\b[^>]*>", secao.corpo, re.I))
    return [(a.get("data-index-group"), a.get("title")) for a in itens]


def exigir(antes: Documento, depois: Documento, grupo: str) -> RelatorioEscopo:
    rel = verificar(antes, depois, grupo)
    if not rel.ok:
        raise Inconsistencia("gate de escopo: " + "; ".join(rel.violacoes))
    return rel
