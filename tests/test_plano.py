from __future__ import annotations

import pytest
from conftest import construir_html

from partituras.dominio.erros import Inconsistencia
from partituras.dominio.modelos import Papel
from partituras.dominio.plano import Origem, planejar, problemas_preservacao, relatorio_pre_geracao
from partituras.html.documento import Documento
from partituras.html.edicao import reconstruir_setlist


def _plano(**kw):
    doc = Documento.de_bytes(construir_html(**kw))
    return planejar(doc.repertorio()), doc


def test_com_setlist_frente_e_set_list_depois_indice():
    """SET-01."""
    plano, _ = _plano()
    assert [p.papel for p in plano.paginas[:3]] == [Papel.SETLIST, Papel.INDICE, Papel.PARTITURA]
    assert plano.inicio_partituras == 2


def test_sem_setlist_indice_primeiro_e_ordem_canonica():
    """SET-08."""
    plano, doc = _plano(setlist=None)
    assert plano.paginas[0].papel is Papel.INDICE
    grupos = [p.grupo for p in plano.paginas_partitura]
    canon = [g for m in doc.repertorio().musicas for g in [m.grupo] * len(m.paginas)]
    assert grupos == canon
    assert {p.origem for p in plano.paginas_partitura} == {Origem.CANONICA}


def test_ocorrencia_aponta_para_a_propria_pagina():
    """SET-04, SET-05."""
    plano, _ = _plano(setlist=["Simmer Down", "Garden of Love", "Simmer Down"])
    assert [d.pagina for d in plano.setlist] == [2, 3, 5]
    assert [p.ocorrencia for p in plano.paginas_partitura if p.grupo == "simmer-down"] == [1, 2]


def test_preservadas_ao_final_na_ordem_canonica():
    """PRES-02."""
    plano, _ = _plano(setlist=["Skaravan"])
    assert plano.preservadas == ["coisa-no-5", "garden-of-love", "ska-paralamas", "simmer-down"]


def test_auxiliar_preservada_uma_vez_depois_das_partituras():
    """PRES-03."""
    plano, doc = _plano(auxiliar=True)
    auxiliares = [p for p in plano.paginas if p.papel is Papel.AUXILIAR]
    assert len(auxiliares) == 1
    assert auxiliares[0].pagina == len(plano.paginas) - 1


def test_todas_as_paginas_canonicas_aparecem():
    """PRES-01, PRES-04: comparação com as páginas de origem."""
    plano, doc = _plano(setlist=["Skaravan"], auxiliar=True)
    assert problemas_preservacao(plano, doc.repertorio()) == []
    plano.paginas = [p for p in plano.paginas if p.id != "slide-3"]
    assert problemas_preservacao(plano, doc.repertorio()) == [
        "página canônica slide-3 ausente do PDF"
    ]


def test_indice_aponta_para_primeira_ocorrencia():
    """IDX-05: com repetição, o índice usa a primeira; fora do set list, a preservada."""
    plano, _ = _plano(setlist=["Simmer Down", "Simmer Down"])
    destino = {d.entrada.grupo: d.pagina for d in plano.indice}
    assert destino["simmer-down"] == 2
    assert destino["coisa-no-5"] == plano.paginas_partitura[2].pagina


def test_sem_indice_bloqueia():
    """VAL-07: índice ausente."""
    doc = Documento.de_bytes(construir_html(com_indice=False))
    with pytest.raises(Inconsistencia, match="índice"):
        planejar(doc.repertorio())


def test_musica_sem_partitura_nao_cria_pagina():
    """SET-09."""
    doc = Documento.de_bytes(construir_html())
    doc, _ = reconstruir_setlist(doc, ["Garden of Love", "Inexistente"])
    plano = planejar(doc.repertorio())
    assert plano.ausentes[0].titulo == "Inexistente"
    assert plano.ausentes[0].pagina is None
    assert len(plano.paginas) == 2 + 6


def test_relatorio_pre_geracao():
    """REL-06."""
    doc = Documento.de_bytes(construir_html())
    doc, _ = reconstruir_setlist(doc, ["Garden of Love", "Inexistente", "Garden of Love"])
    plano = planejar(doc.repertorio())
    rel = relatorio_pre_geracao(plano, doc.repertorio())
    assert rel["setlist"][0] == {
        "posicao": 1,
        "musica": "Garden of Love",
        "grupo": "garden-of-love",
        "paginas": [3, 4],
    }
    assert rel["ausentes"] == [{"posicao": 2, "musica": "Inexistente"}]
    assert rel["repeticoes"] == ["garden-of-love"]
    assert rel["multipaginas"] == ["garden-of-love"]
    assert rel["total_esperado"] == len(plano.paginas) == len(rel["sequencia"])
