"""Compatibilidade com os HTMLs reais da pasta `partituras_claude`.

Os repertórios reais não ficam no repositório. Para rodar:

    PARTITURAS_HTML_REAIS="/caminho/partituras_claude" pytest tests/test_html_reais.py

Sem a variável, os testes são pulados.
"""

from __future__ import annotations

import pytest
from conftest import html_real

from partituras.html.documento import Documento
from partituras.html.edicao import reconstruir_indice, reconstruir_setlist

REAIS = {
    "Skaravana.html": {"musicas": 24, "paginas": 28, "setlist": 9, "crlf": True},
    "Xamego.html": {"musicas": 31, "paginas": 40, "setlist": 23, "crlf": False},
    "Fanfarock.html": {"musicas": 11, "paginas": 22, "setlist": 11, "crlf": False},
}


@pytest.mark.parametrize("nome", sorted(REAIS))
def test_regenerar_sem_mudancas_nao_altera_bytes(nome):
    """Índice e set list regenerados são idênticos aos existentes (HTML-09, IDX, SET)."""
    dados = html_real(nome)
    doc = Documento.de_bytes(dados)
    assert doc.para_bytes() == dados
    regenerado, relatorio = reconstruir_setlist(reconstruir_indice(doc))
    assert regenerado.para_bytes() == dados
    assert relatorio.ausentes == []


@pytest.mark.parametrize("nome", sorted(REAIS))
def test_estrutura_dos_reais(nome):
    esperado = REAIS[nome]
    dados = html_real(nome)
    repertorio = Documento.de_bytes(dados).repertorio()
    assert len(repertorio.musicas) == esperado["musicas"]
    assert len(repertorio.paginas) == esperado["paginas"]
    assert len(repertorio.setlist) == esperado["setlist"]
    assert (b"\r\n" in dados) is esperado["crlf"]
