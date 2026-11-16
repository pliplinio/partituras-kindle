from __future__ import annotations

import pytest

from partituras.dominio.erros import Ambiguidade
from partituras.dominio.nomes import (
    Candidato,
    Situacao,
    corresponder,
    normalizar,
    similaridade,
)

SKARAVANA = [
    Candidato("ska-paralamas", "Ska Paralamas"),
    Candidato("skaravan", "Skaravan"),
    Candidato("jamaica-ska", "Jamaica Ska"),
    Candidato("the-reburial", "The Reburial"),
    Candidato("a-message-to-you-rudy", "A Message to You Rudy"),
    Candidato("cristine-keeler", "Cristine Keeler"),
]


def test_igualdade_normalizada_vence():
    c = corresponder("SKA  paralamas!", SKARAVANA)
    assert c.situacao is Situacao.EXATA
    assert c.escolhido.chave == "ska-paralamas"


@pytest.mark.parametrize(
    ("procurado", "esperado"),
    [
        ("Ska Paralamas", "ska-paralamas"),
        ("Skaravan", "skaravan"),
        ("ska paralamas", "ska-paralamas"),
        ("SKARAVAN", "skaravan"),
    ],
)
def test_ska_paralamas_e_skaravan_nunca_se_confundem(procurado, esperado):
    """Caso obrigatório de regressão (NOM-05)."""
    c = corresponder(procurado, SKARAVANA)
    assert c.escolhido.chave == esperado
    assert c.melhor_score == 1.0
    assert c.segundo_score < 0.9


def test_aceita_diferencas_inequivocas():
    """Acentos, maiúsculas, pontuação e pequenos erros (NOM-01)."""
    assert corresponder("Christine Keeler", SKARAVANA).escolhido.chave == "cristine-keeler"
    assert corresponder("Reburial", SKARAVANA).escolhido.chave == "the-reburial"
    assert corresponder("A message to you rude", SKARAVANA).escolhido.chave == (
        "a-message-to-you-rudy"
    )
    assert normalizar("Coração Nº 5!") == "coracao no 5"


def test_registra_melhor_segundo_e_diferenca():
    """NOM-02."""
    c = corresponder("Christine Keeler", SKARAVANA)
    assert c.situacao is Situacao.APROXIMADA
    dados = c.como_dict()
    assert dados["procurado"] == "Christine Keeler"
    assert dados["escolhido"] == "Cristine Keeler"
    assert dados["melhor_score"] > dados["segundo_score"]
    assert dados["diferenca"] == pytest.approx(
        dados["melhor_score"] - dados["segundo_score"], abs=0.002
    )


def test_diferenca_menor_que_008_e_ambigua():
    """NOM-03 e NOM-04: nunca escolhe sozinho."""
    candidatos = [Candidato("a", "Festa no Mar"), Candidato("b", "Festa no Bar")]
    assert similaridade("Festa no Par", "Festa no Mar") == similaridade(
        "Festa no Par", "Festa no Bar"
    )
    with pytest.raises(Ambiguidade):
        corresponder("Festa no Par", candidatos)


def test_dois_exatos_iguais_sao_ambiguos():
    candidatos = [Candidato("a", "Domingo"), Candidato("b", "Domingo")]
    with pytest.raises(Ambiguidade):
        corresponder("Domingo", candidatos)


def test_grafia_completa_desempata_titulos_com_parenteses():
    """ "Coração Partido" e "Coração Partido (graus)" normalizam igual; a grafia completa decide."""
    candidatos = [
        Candidato("coracao-partido-graus", "Coração Partido (graus)"),
        Candidato("coracao-partido", "Coração Partido"),
    ]
    assert corresponder("coração partido", candidatos).escolhido.chave == "coracao-partido"
    assert corresponder("Coração Partido (Graus)", candidatos).escolhido.chave == (
        "coracao-partido-graus"
    )


def test_abaixo_do_limiar_e_ausente():
    c = corresponder("Música que não existe", SKARAVANA)
    assert c.situacao is Situacao.AUSENTE
    assert c.escolhido is None


def test_multipagina_conta_uma_vez():
    """Uma música com várias páginas é uma só candidata; não gera falsa ambiguidade."""
    candidatos = [Candidato("garden-of-love", "Garden of Love")] * 2 + [
        Candidato("simmer-down", "Simmer Down")
    ]
    c = corresponder("Garden of Lov", candidatos)
    assert c.escolhido.chave == "garden-of-love"
    assert c.segundo.chave == "simmer-down"


def test_aproximacao_fraca_pede_confirmacao():
    """NOM-03: entre 0,68 e 0,80 não se sabe se é a música ou uma ausente."""
    assert 0.68 <= similaridade("Mixolidio", "Lidio") < 0.80
    with pytest.raises(Ambiguidade):
        corresponder("Mixolidio", [Candidato("lidio", "Lidio")])


def test_aproximacao_inequivoca_nao_interrompe():
    """FLX-06: só ambiguidade, inconsistência ou bloqueio param o processamento."""
    c = corresponder("Jamaica  Ska.", SKARAVANA)
    assert c.situacao is Situacao.EXATA
    c = corresponder("Jamaika Ska", SKARAVANA)
    assert c.situacao is Situacao.APROXIMADA


def test_inclusao_so_por_palavras_inteiras():
    """ "Lidio" não é abreviação de "Mixolidio"; "Reburial" é de "The Reburial"."""
    assert similaridade("Reburial", "The Reburial") == 0.92
    assert similaridade("Mixolidio", "Lidio") < 0.92
    with pytest.raises(Ambiguidade, match="Confirme"):
        corresponder("Mixolidio", [Candidato("lidio", "Lidio"), Candidato("jonia", "Jonia")])
