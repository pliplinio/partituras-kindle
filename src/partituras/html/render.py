"""Marcação gerada para índice, set list e páginas de partitura.

O formato é idêntico ao dos HTMLs canônicos existentes: regenerar um repertório
sem mudanças não altera nenhum byte.
"""

from __future__ import annotations

from collections.abc import Sequence
from html import escape

from partituras.dominio.indice import COLUNAS, EntradaIndice, colunas

TITULO_OVERLAY_PX = 17
ABC_OVERLAY_PX = 14


def _attr(valor: str) -> str:
    return escape(valor, quote=True)


def _texto(valor: str) -> str:
    return escape(valor, quote=False)


def corpo_indice(entradas: Sequence[EntradaIndice]) -> str:
    """Tabela real de 3 colunas, preenchida coluna a coluna (IDX-03, IDX-04)."""
    cols = colunas(list(entradas))
    linhas = max((len(c) for c in cols), default=0)
    trs = []
    for r in range(linhas):
        tds = []
        for c in range(COLUNAS):
            if r < len(cols[c]):
                e = cols[c][r]
                tds.append(
                    f'<td><a data-index-group="{_attr(e.grupo)}" href="#{_attr(e.pagina)}" '
                    f'title="{_attr(e.titulo)}">{_texto(e.rotulo)}</a></td>'
                )
            else:
                tds.append("<td></td>")
        trs.append("<tr>" + "".join(tds) + "</tr>")
    return (
        '<h1>Índice</h1><table aria-label="Índice alfabético de músicas" class="index-table">'
        "<tbody>" + "".join(trs) + "</tbody></table>"
    )


def item_setlist(posicao: int, titulo: str, grupo: str | None, pagina: str | None) -> str:
    """Texto real com link quando há partitura; sem link quando não há (SET-02, SET-03, SET-09).

    O texto visível escapa aspas e apóstrofos, como nos HTMLs existentes.
    """
    pos = _attr(str(posicao))
    if grupo is None or pagina is None:
        return (
            f'<li data-setlist-pos="{pos}"><span class="setlist-missing" data-setlist-pos="{pos}" '
            f'title="{_attr(titulo)}">{_attr(titulo)}</span></li>'
        )
    return (
        f'<li data-setlist-pos="{pos}"><a data-setlist-pos="{pos}" data-setlist-group="{_attr(grupo)}" '
        f'href="#{_attr(pagina)}" title="{_attr(titulo)}">{_attr(titulo)}</a></li>'
    )


def corpo_setlist(itens_html: Sequence[str]) -> str:
    return (
        '<h1>Set list</h1><ol aria-label="Set list de músicas" class="setlist-list">'
        + "".join(itens_html)
        + "</ol>"
    )


def rotulo_pagina(titulo: str, parte: int, total: int) -> str:
    """`Nome` ou `Nome (k de N)` (LAY-03)."""
    return f"{titulo} ({parte} de {total})" if total > 1 else titulo


def secao_raw_score(
    titulo: str,
    grupo: str,
    parte: int,
    total: int,
    id_: str,
    data_uri: str,
    destino: str,
    fontes_aprovadas: bool,
) -> str:
    """Cabeçalho separado no topo e imagem ocupando toda a área abaixo (LAY-01, LAY-02).

    `fontes_aprovadas` aplica título 17 px e `ABC` 14 px, usados nas páginas raw-score
    de HTMLs com template overlay (LAY-06).
    """
    rotulo = rotulo_pagina(titulo, parte, total)
    fonte_titulo = f"font-size:{TITULO_OVERLAY_PX}px;" if fontes_aprovadas else ""
    fonte_abc = f"font-size:{ABC_OVERLAY_PX}px;" if fontes_aprovadas else ""
    return f"""<section class="slide score-native" id="{_attr(id_)}" data-role="score" data-song="{_attr(titulo)}" data-group="{_attr(grupo)}" data-part="{parte}" data-total-parts="{total}" aria-label="{_attr(rotulo)}">
  <header class="score-header" style="flex:0 0 8%;display:grid;grid-template-columns:1fr auto 1fr;align-items:center;padding:0 5%;font-family:Arial,sans-serif;font-size:clamp(16px,2.2vw,30px);line-height:1;">
    <a class="score-title" href="{_attr(destino)}" style="grid-column:2;justify-self:center;color:#0563c1;text-decoration:underline;{fonte_titulo}">{_attr(rotulo)}</a>
    <a class="score-abc" href="{_attr(destino)}" style="grid-column:3;justify-self:end;color:#0563c1;text-decoration:underline;{fonte_abc}">ABC</a>
  </header>
  <div class="score-image-wrap" style="flex:1 1 auto;min-height:0;width:100%;overflow:hidden;">
    <img class="score-image" alt="Partitura {_attr(rotulo)}" src="{data_uri}" style="display:block;width:100%;height:100%;object-fit:fill;"/>
  </div>
</section>"""


def secao_overlay(
    titulo: str,
    grupo: str,
    parte: int,
    total: int,
    id_: str,
    data_uri: str,
    destino: str,
    esquerda_titulo: float,
    esquerda_abc: float,
) -> str:
    """Imagem na página inteira e cabeçalho transparente sobreposto (LAY-04)."""
    rotulo = rotulo_pagina(titulo, parte, total)
    return (
        f'<section class="slide score-overlay-v2" id="{_attr(id_)}" data-role="score" '
        f'data-song="{_attr(titulo)}" data-group="{_attr(grupo)}" data-part="{parte}" '
        f'data-total-parts="{total}" aria-label="{_attr(rotulo)}">'
        f'<img class="score-image" alt="Partitura {_attr(rotulo)}" src="{data_uri}"/>'
        f'<header class="score-header-overlay">'
        f'<a class="score-title-overlay" href="{_attr(destino)}" style="left:{esquerda_titulo:.4f}%;">'
        f"{_attr(rotulo)}</a>"
        f'<a class="score-abc-overlay" href="{_attr(destino)}" style="left:{esquerda_abc:.4f}%;">ABC</a>'
        f"</header></section>"
    )
