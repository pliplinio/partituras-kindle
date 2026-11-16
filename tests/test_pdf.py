"""Materialização e links com HTMLs sintéticos (Chromium)."""

from __future__ import annotations

import pymupdf
import pytest
from conftest import construir_html

from partituras.casos_de_uso.gerar_pdf import gerar_candidato
from partituras.pdf.materializacao import BASE_CAIXA, TOPO_CAIXA, retangulos_cabecalho
from partituras.pdf.texto import destino

pytestmark = pytest.mark.chromium


@pytest.fixture(scope="module")
def com_auxiliar(tmp_path_factory):
    pasta = tmp_path_factory.mktemp("aux")
    return gerar_candidato(construir_html(auxiliar=True), pasta, "Teste_v04.pdf")


def test_retornos_sao_goto_para_a_pagina_1(com_auxiliar):
    """LNK-01, LNK-02: GoTo internos, sem encostar na margem superior."""
    with pymupdf.open(com_auxiliar.candidato) as doc:
        for p in com_auxiliar.plano.paginas_partitura:
            retornos = [lk for lk in doc[p.pagina].get_links() if destino(lk) == 0]
            assert len(retornos) == 2
            assert all(lk["kind"] == pymupdf.LINK_GOTO for lk in retornos)
            assert all(pymupdf.Rect(lk["from"]).y0 > 0 for lk in retornos)


def test_auxiliar_sem_retorno(com_auxiliar):
    """LNK-04, PRES-03."""
    with pymupdf.open(com_auxiliar.candidato) as doc:
        assert doc[len(doc) - 1].get_links() == []
    assert com_auxiliar.plano.paginas[-1].papel == "auxiliar"


def test_retorno_segue_o_texto_quando_ha_texto(com_auxiliar):
    """LNK-03: com texto extraível, a área é o retângulo real do título."""
    with pymupdf.open(com_auxiliar.candidato) as doc:
        pagina = doc[2]
        titulo, abc = retangulos_cabecalho(pagina)
        palavras = [w for w in pagina.get_text("words") if w[4] == "ABC"]
        assert palavras and abs(abc.x0 - palavras[0][0]) < 0.01


def test_caixa_padrao_sem_texto():
    """LNK-03: sem texto, a caixa aprovada de 17 a 35 px em 880×650."""
    doc = pymupdf.open()
    pagina = doc.new_page(width=660, height=487.92)
    titulo, abc = retangulos_cabecalho(pagina)
    assert titulo.y0 == pytest.approx(487.92 * TOPO_CAIXA)
    assert titulo.y1 == pytest.approx(487.92 * BASE_CAIXA)
    assert abc.x0 > titulo.x1


def test_overlay_gera_pdf_valido(tmp_path):
    r = gerar_candidato(construir_html(overlay=True), tmp_path, "Ov_v02.pdf")
    assert r.gate.ok and all(p["retornos"] == 2 for p in r.gate.partituras)


def test_sem_setlist_retornos_vao_para_o_indice(tmp_path):
    """SET-08, LNK-01: página 1 é o índice."""
    r = gerar_candidato(construir_html(setlist=None), tmp_path, "Sem_v02.pdf")
    assert r.plano.paginas[0].papel == "index"
    assert r.gate.setlist == []
    assert all(i["ok"] for i in r.gate.indice)
