"""Compatibilidade com os HTMLs reais da pasta `partituras_claude`.

Os repertórios reais não ficam no repositório. Para rodar:

    PARTITURAS_HTML_REAIS="/caminho/partituras_claude" pytest tests/test_html_reais.py

Sem a variável, os testes são pulados.
"""

from __future__ import annotations

import pytest
from conftest import html_real

from partituras.dominio.repertorio import problemas_ordem
from partituras.html.documento import Documento
from partituras.html.edicao import reconstruir_indice, reconstruir_setlist

# Contagens de 28/11/2026.
REAIS = {
    "Skaravana.html": {"musicas": 24, "paginas": 28, "setlist": 9, "crlf": True},
    "Xamego.html": {"musicas": 32, "paginas": 41, "setlist": 15, "crlf": False},
    "Fanfarock.html": {"musicas": 11, "paginas": 22, "setlist": 9, "crlf": False},
}


@pytest.mark.parametrize("nome", sorted(REAIS))
def test_regenerar_sem_mudancas_so_reordena(nome):
    """Índice e set list regenerados não mudam o conteúdo; no máximo põem as páginas na
    ordem do set list (HTML-09, IDX, SET-10). Uma segunda regeneração não muda nada."""
    dados = html_real(nome)
    doc = Documento.de_bytes(dados)
    assert doc.para_bytes() == dados
    regenerado, relatorio = reconstruir_setlist(reconstruir_indice(doc))
    assert relatorio.ausentes == []
    assert problemas_ordem(regenerado.repertorio()) == []
    assert sorted(s.texto for s in regenerado.secoes) == sorted(s.texto for s in doc.secoes)
    assert regenerado.texto[: regenerado.secoes[0].inicio] == doc.texto[: doc.secoes[0].inicio]
    assert regenerado.texto[regenerado.secoes[-1].fim :] == doc.texto[doc.secoes[-1].fim :]
    de_novo, _ = reconstruir_setlist(reconstruir_indice(regenerado))
    assert de_novo.para_bytes() == regenerado.para_bytes()


@pytest.mark.parametrize("nome", sorted(REAIS))
def test_estrutura_dos_reais(nome):
    esperado = REAIS[nome]
    dados = html_real(nome)
    repertorio = Documento.de_bytes(dados).repertorio()
    assert len(repertorio.musicas) == esperado["musicas"]
    assert len(repertorio.paginas) == esperado["paginas"]
    assert len(repertorio.setlist) == esperado["setlist"]
    assert (b"\r\n" in dados) is esperado["crlf"]
