from __future__ import annotations

import pytest

from partituras.dominio.erros import Inconsistencia
from partituras.dominio.indice import entradas_indice, tamanhos_colunas
from partituras.dominio.modelos import ItemSetlist, Pagina, Papel
from partituras.dominio.repertorio import montar_repertorio, problemas_estruturais


def p(id_, grupo, parte, total, musica=None):
    return Pagina(id_, Papel.PARTITURA, musica or grupo.title(), grupo, parte, total)


def test_ids_unicos():
    """EST-01."""
    assert "id repetido: slide-3" in problemas_estruturais(
        [p("slide-3", "a", 1, 1), p("slide-3", "b", 1, 1)]
    )


def test_partitura_declara_todos_os_atributos():
    """EST-02."""
    pagina = Pagina("slide-3", Papel.PARTITURA, "Música", None, 1, None)
    problemas = problemas_estruturais([pagina])
    assert problemas == ["slide-3: faltam data-group, data-total-parts"]


def test_grupo_reune_as_paginas_da_musica():
    """MULTI-01."""
    r = montar_repertorio([p("s1", "a", 1, 2), p("s2", "a", 2, 2), p("s3", "b", 1, 1)], None, True)
    assert [(m.grupo, m.paginas) for m in r.musicas] == [("a", ("s1", "s2")), ("b", ("s3",))]


def test_paginas_do_grupo_consecutivas():
    """MULTI-02."""
    problemas = problemas_estruturais([p("s1", "a", 1, 2), p("s2", "b", 1, 1), p("s3", "a", 2, 2)])
    assert "grupo a: páginas não consecutivas" in problemas


@pytest.mark.parametrize(
    "paginas",
    [
        [p("s1", "a", 1, 2), p("s2", "a", 3, 2)],
        [p("s1", "a", 1, 2)],
        [p("s1", "a", 1, 2), p("s2", "a", 2, 3)],
        [p("s1", "a", 2, 2), p("s2", "a", 1, 2)],
    ],
)
def test_partes_1_a_n_com_mesmo_total(paginas):
    """MULTI-03."""
    assert problemas_estruturais(paginas)


def test_inconsistencia_reprova():
    """MULTI-04."""
    with pytest.raises(Inconsistencia, match="partes"):
        montar_repertorio([p("s1", "a", 1, 2), p("s2", "a", 3, 2)], None, True)


def test_setlist_com_grupo_inexistente_reprova():
    with pytest.raises(Inconsistencia, match="inexistentes"):
        montar_repertorio([p("s1", "a", 1, 1)], [ItemSetlist(1, "X", "zzz")], True)


def test_pagina_inicial():
    """SET-01 e SET-08: set list quando existe; índice quando não."""
    paginas = [p("s1", "a", 1, 1)]
    assert montar_repertorio(paginas, [ItemSetlist(1, "A", "a")], True).pagina_inicial == "setlist"
    assert montar_repertorio(paginas, None, True).pagina_inicial == "index"


def test_indice_uma_entrada_por_musica_em_ordem_alfabetica():
    """IDX-01 e IDX-02."""
    paginas = [
        p("s1", "zeca", 1, 1, "Zeca"),
        p("s2", "ela", 1, 2, "Éla"),
        p("s3", "ela", 2, 2, "Éla"),
        p("s4", "bela", 1, 1, "bela"),
        p("s5", "alma", 1, 1, "Alma"),
    ]
    entradas = entradas_indice(montar_repertorio(paginas, None, True))
    assert [e.titulo for e in entradas] == ["Alma", "bela", "Éla", "Zeca"]
    assert [e.pagina for e in entradas] == ["s5", "s4", "s2", "s1"]


def test_rotulo_do_indice_limitado_a_22():
    """IDX-03."""
    titulo = "Joan Jett - I Love Rock And Roll"
    r = montar_repertorio([p("s1", "x", 1, 1, titulo)], None, True)
    entrada = entradas_indice(r)[0]
    assert entrada.rotulo == titulo[:22]
    assert entrada.titulo == titulo


@pytest.mark.parametrize(
    ("total", "esperado"),
    [
        (29, [10, 10, 9]),
        (24, [8, 8, 8]),
        (25, [9, 8, 8]),
        (1, [1, 0, 0]),
        (2, [1, 1, 0]),
        (0, [0, 0, 0]),
    ],
)
def test_tres_colunas_equilibradas(total, esperado):
    """IDX-04."""
    assert tamanhos_colunas(total) == esperado
    assert max(esperado) - min(esperado) <= 1
