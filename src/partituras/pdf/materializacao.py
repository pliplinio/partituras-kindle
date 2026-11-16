"""Materialização do PDF a partir do PDF cru e do plano (PDF-08, IDX-06, LNK-01 a LNK-04).

Os parâmetros de desenho do índice e de geometria dos links são os da versão
anterior, para que páginas iguais continuem com os mesmos pixels e a inspeção
visual possa ser reaproveitada.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import pymupdf

from partituras.dominio.erros import Inconsistencia
from partituras.dominio.indice import colunas, tamanhos_colunas
from partituras.dominio.plano import Plano
from partituras.pdf.texto import linha_exata, linhas, melhor_linha

# Índice desenhado
TITULO_INDICE = "ÍNDICE"
MARGEM_INDICE = 52.0
ESPACO_COLUNAS = 24.0
TOPO_INDICE = 72.0
FONTE_INDICE = 14.0

# Faixa do cabeçalho onde ficam título e ABC (fração da altura)
FAIXA_CABECALHO = 0.14
# Caixa aprovada do cabeçalho em 880×650: y de 17 a 35 px
TOPO_CAIXA = 17.0 / 650.0
BASE_CAIXA = 35.0 / 650.0
FOLGA_X, FOLGA_Y = 6.0, 2.0
MINIMO_SETLIST = 0.55


@dataclass
class RelatorioMaterializacao:
    paginas: int = 0
    colunas_indice: list[int] = field(default_factory=list)
    links_setlist: int = 0
    links_indice: int = 0
    paginas_com_retorno: list[int] = field(default_factory=list)


def materializar(pdf_cru: Path, saida: Path, plano: Plano) -> RelatorioMaterializacao:
    relatorio = RelatorioMaterializacao()
    with pymupdf.open(pdf_cru) as cru:
        if len(cru) != plano.paginas_cruas:
            raise Inconsistencia(
                f"PDF cru com {len(cru)} páginas; o plano espera {plano.paginas_cruas}"
            )
        doc = pymupdf.open()
        for numero in plano.ordem_crua:
            doc.insert_pdf(cru, from_page=numero, to_page=numero, links=True, annots=True)
    try:
        relatorio.colunas_indice = _desenhar_indice(doc, plano)
        relatorio.links_setlist, relatorio.links_indice = _links_frente(doc, plano)
        relatorio.paginas_com_retorno = _links_retorno(doc, plano)
        relatorio.paginas = len(doc)
        saida.parent.mkdir(parents=True, exist_ok=True)
        doc.save(saida, garbage=4, deflate=True, clean=True)
    finally:
        doc.close()
    return relatorio


def _desenhar_indice(doc: pymupdf.Document, plano: Plano) -> list[int]:
    """Substitui a página do índice por 3 colunas reais (IDX-06)."""
    numero = plano.pagina_indice
    rect = pymupdf.Rect(doc[numero].rect)
    doc.delete_page(numero)
    pagina = doc.new_page(pno=numero, width=rect.width, height=rect.height)
    pagina.insert_textbox(
        pymupdf.Rect(0, 18, rect.width, 52),
        TITULO_INDICE,
        fontsize=20,
        fontname="helv",
        align=pymupdf.TEXT_ALIGN_CENTER,
        color=(0, 0, 0),
    )
    entradas = [d.entrada for d in plano.indice]
    tamanhos = tamanhos_colunas(len(entradas))
    largura = (rect.width - 2 * MARGEM_INDICE - 2 * ESPACO_COLUNAS) / 3.0
    xs = [MARGEM_INDICE + i * (largura + ESPACO_COLUNAS) for i in range(3)]
    linhas_max = max(tamanhos or [1]) or 1
    passo = min(54.0, max(32.0, (rect.height - TOPO_INDICE - 42.0) / linhas_max))
    for c, coluna in enumerate(colunas(entradas)):
        for r, entrada in enumerate(coluna):
            y = TOPO_INDICE + r * passo
            pagina.insert_textbox(
                pymupdf.Rect(xs[c], y, xs[c] + largura, y + 24.0),
                entrada.rotulo,
                fontsize=FONTE_INDICE,
                fontname="helv",
                align=pymupdf.TEXT_ALIGN_LEFT,
                color=(0, 0, 0),
            )
    return tamanhos


def _inserir_goto(pagina: pymupdf.Page, rect: pymupdf.Rect, destino: int) -> None:
    clicavel = pymupdf.Rect(rect)
    clicavel.x0 -= 2
    clicavel.x1 += 4
    clicavel.y0 -= 2
    clicavel.y1 += 3
    pagina.insert_link(
        {"kind": pymupdf.LINK_GOTO, "from": clicavel, "page": destino, "to": pymupdf.Point(0, 0)}
    )


def _links_frente(doc: pymupdf.Document, plano: Plano) -> tuple[int, int]:
    """Recria os links do set list (por ocorrência) e do índice (primeira ocorrência)."""
    frente = [0, 1] if plano.tem_setlist else [0]
    for numero in frente:
        for link in list(doc[numero].get_links()):
            doc[numero].delete_link(link)

    falhas: list[str] = []
    n_setlist = 0
    if plano.tem_setlist:
        pagina = doc[0]
        candidatas, usadas = linhas(pagina), set()
        for item in plano.setlist:
            achado = melhor_linha(candidatas, item.titulo, usadas, MINIMO_SETLIST)
            if achado is None:
                falhas.append(f"set list {item.posicao}: texto não encontrado")
                continue
            usadas.add(achado[0])
            if item.pagina is not None:
                _inserir_goto(pagina, achado[1].rect, item.pagina)
                n_setlist += 1

    pagina = doc[plano.pagina_indice]
    candidatas, usadas = linhas(pagina), set()
    n_indice = 0
    for destino in plano.indice:
        achado = linha_exata(candidatas, destino.entrada.rotulo, usadas)
        if achado is None:
            falhas.append(f"índice: {destino.entrada.titulo} não encontrado")
            continue
        usadas.add(achado[0])
        _inserir_goto(pagina, achado[1].rect, destino.pagina)
        n_indice += 1

    if falhas:
        raise Inconsistencia("navegação da frente do PDF: " + "; ".join(falhas))
    return n_setlist, n_indice


def retangulos_cabecalho(pagina: pymupdf.Page) -> tuple[pymupdf.Rect, pymupdf.Rect]:
    """Retângulos de título e `ABC`: texto real quando houver, senão a caixa aprovada (LNK-03)."""
    limite = pagina.rect.height * FAIXA_CABECALHO
    palavras = [p for p in pagina.get_text("words") if p[1] < limite]
    abc = [pymupdf.Rect(p[:4]) for p in palavras if str(p[4]).strip().upper() == "ABC"]
    titulo = [pymupdf.Rect(p[:4]) for p in palavras if str(p[4]).strip().upper() != "ABC"]
    w, h = pagina.rect.width, pagina.rect.height
    if titulo:
        rect_titulo = titulo[0]
        for r in titulo[1:]:
            rect_titulo |= r
    else:
        rect_titulo = pymupdf.Rect(w * 0.25, h * TOPO_CAIXA, w * 0.75, h * BASE_CAIXA)
    if abc:
        rect_abc = abc[0]
        for r in abc[1:]:
            rect_abc |= r
    else:
        rect_abc = pymupdf.Rect(w * 0.875, h * TOPO_CAIXA, w * 0.965, h * BASE_CAIXA)
    return rect_titulo, rect_abc


def area_clicavel(rect: pymupdf.Rect, pagina: pymupdf.Rect) -> pymupdf.Rect:
    r = pymupdf.Rect(rect)
    r.x0 = max(pagina.x0, r.x0 - FOLGA_X)
    r.x1 = min(pagina.x1, r.x1 + FOLGA_X)
    r.y0 = max(pagina.y0, r.y0 - FOLGA_Y)
    r.y1 = min(pagina.y1, r.y1 + FOLGA_Y)
    return r


def _links_retorno(doc: pymupdf.Document, plano: Plano) -> list[int]:
    """Título e `ABC` de toda página de partitura viram GoTo para a página 1 (LNK-01, LNK-02).

    Só páginas de partitura do plano; auxiliares não recebem (LNK-04).
    """
    feitas = []
    for p in plano.paginas_partitura:
        pagina = doc[p.pagina]
        faixa = pymupdf.Rect(0, 0, pagina.rect.width, pagina.rect.height * FAIXA_CABECALHO)
        for link in list(pagina.get_links()):
            if pymupdf.Rect(link["from"]).intersects(faixa):
                pagina.delete_link(link)
        for rect in retangulos_cabecalho(pagina):
            pagina.insert_link(
                {
                    "kind": pymupdf.LINK_GOTO,
                    "from": area_clicavel(rect, pagina.rect),
                    "page": 0,
                    "to": pymupdf.Point(0, 0),
                }
            )
        feitas.append(p.pagina + 1)
    return feitas
