from __future__ import annotations

from partituras.dominio.modelos import Musica
from partituras.dominio.setlist import ler_texto, resolver


def test_formatos_aceitos():
    """SET-07: numerada, marcadores, travessões, uma por linha, blocos e bis."""
    texto = """
    Set list - Carnaval
    15/02/2027
    Local: Praça da Sé
    20h30
    1º set
    1. Coisa Nº 5
    2) Garden of Love
    3 - Christine Keeler
    - Ska Paralamas
    • Jamaica Ska
    Reburial
    Intervalo
    (trocar palheta)
    Bis
    Simmer Down
    """
    itens = ler_texto(texto)
    assert [i.titulo for i in itens] == [
        "Coisa Nº 5",
        "Garden of Love",
        "Christine Keeler",
        "Ska Paralamas",
        "Jamaica Ska",
        "Reburial",
        "Simmer Down",
    ]
    assert [i.posicao for i in itens] == list(range(1, 8))
    assert [i.bis for i in itens] == [False] * 6 + [True]


def test_linha_duvidosa_e_musica():
    """Só resíduos inequívocos são ignorados."""
    itens = ler_texto("Coisa Nº 5\nBlink 182 - All The Small Things\n4 Estações")
    assert [i.titulo for i in itens] == [
        "Coisa Nº 5",
        "Blink 182 - All The Small Things",
        "4 Estações",
    ]


def test_repeticao_vira_dois_itens():
    itens = ler_texto("Garden of Love\nSimmer Down\nGarden of Love")
    assert [i.titulo for i in itens] == ["Garden of Love", "Simmer Down", "Garden of Love"]


def test_ligacao_declarada_vale_mais_que_nome():
    musicas = [Musica("i-love-rock-n-roll", "I Love Rock N Roll", ("slide-5",))]
    titulo = "Joan Jett / Queen - I Love Rock And Roll / We Will Rock You"
    r = resolver([titulo], musicas, ["i-love-rock-n-roll"])
    assert r[0].item.grupo == "i-love-rock-n-roll"
    assert r[0].correspondencia is None


def test_musica_sem_partitura_fica_sem_grupo():
    """SET-09."""
    musicas = [Musica("simmer-down", "Simmer Down", ("slide-5",))]
    r = resolver(["Música Nova Sem Partitura"], musicas)
    assert r[0].item.grupo is None
