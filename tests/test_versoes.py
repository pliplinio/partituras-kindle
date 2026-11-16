from __future__ import annotations

import pytest

from partituras.dominio.erros import Bloqueio, Inconsistencia
from partituras.dominio.versoes import (
    TipoAlteracao,
    conferir_versao_template,
    garantir_nao_sobrescreve,
    nome_html,
    nome_html_arquivado,
    nome_pdf,
    nova_versao_template,
    proxima_versao_pdf,
    selecionar_fonte,
)


def test_html_tem_nome_fixo_sem_versao():
    """HTML-01."""
    assert nome_html("Skaravana") == "Skaravana.html"
    with pytest.raises(Inconsistencia):
        nome_html("pasta/Skaravana")


def test_versao_anterior_vai_para_old():
    """HTML-06: a versão vigente é arquivada antes da mudança de template."""
    assert nome_html_arquivado("Skaravana", 6) == "old/Skaravana_v06.html"
    assert nome_html_arquivado("Xamego", 22) == "old/Xamego_v22.html"


def test_nova_versao_de_template_e_mais_um():
    """HTML-05."""
    assert nova_versao_template(6) == 7


def test_template_muda_so_em_alteracao_de_template():
    """HTML-03, HTML-04 e HTML-10."""
    conferir_versao_template(6, 6, TipoAlteracao.CONTEUDO)
    conferir_versao_template(6, 7, TipoAlteracao.TEMPLATE)
    with pytest.raises(Inconsistencia):
        conferir_versao_template(6, 7, TipoAlteracao.CONTEUDO)
    with pytest.raises(Inconsistencia):
        conferir_versao_template(6, 6, TipoAlteracao.TEMPLATE)
    with pytest.raises(Inconsistencia):
        conferir_versao_template(6, 8, TipoAlteracao.TEMPLATE)


def test_nome_do_pdf():
    """PDF-01."""
    assert nome_pdf("Skaravana", 7) == "Skaravana_v07.pdf"
    assert nome_pdf("Xamego", 38) == "Xamego_v38.pdf"
    with pytest.raises(Inconsistencia):
        nome_pdf("Xamego", 0)


def test_proxima_versao_conta_so_pdfs_existentes():
    """PDF-02: a versão de template não entra na conta."""
    assert proxima_versao_pdf("Skaravana", ["Skaravana_v13.pdf", "Skaravana_v09.pdf"]) == 14
    assert proxima_versao_pdf("Skaravana", ["Xamego_v40.pdf", "Skaravana.html"]) == 1


def test_numeracao_propria_recomeca_em_v01():
    """PDF-03: sem PDF na pasta da versão Claude, o primeiro é v01."""
    assert nome_pdf("Skaravana", proxima_versao_pdf("Skaravana", [])) == "Skaravana_v01.pdf"


def test_colisao_usa_proxima_livre():
    assert proxima_versao_pdf("Skaravana", ["Skaravana_v7.pdf"]) == 8
    assert proxima_versao_pdf("Skaravana", ["skaravana_v10.PDF"]) == 11


def test_nunca_sobrescreve_pdf():
    """PDF-04."""
    garantir_nao_sobrescreve("Skaravana_v15.pdf", ["Skaravana_v14.pdf"])
    with pytest.raises(Bloqueio):
        garantir_nao_sobrescreve("Skaravana_v14.pdf", ["skaravana_v14.pdf"])


def test_fonte_e_o_html_nunca_pptx():
    """ARQ-03."""
    arquivos = ["Skaravana v05.pptx", "Skaravana.html", "Skaravana_v13.pdf"]
    assert selecionar_fonte("Skaravana", arquivos) == "Skaravana.html"
    with pytest.raises(Bloqueio, match="formato antigo"):
        selecionar_fonte("Skaravana", ["Skaravana v05.pptx", "Skaravana_v06.html"])
