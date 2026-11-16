"""Garante que toda regra de REGRAS.md esteja ligada a testes (TST-05)."""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

RAIZ = Path(__file__).resolve().parent.parent
REGRAS = RAIZ / "REGRAS.md"
MATRIZ = RAIZ / "tests" / "matriz_regras.yaml"
PADRAO_REGRA = re.compile(r"^- \[([A-Z]+-\d{2})\] ", re.MULTILINE)


def ids_em_regras() -> list[str]:
    return PADRAO_REGRA.findall(REGRAS.read_text(encoding="utf-8"))


def carregar_matriz() -> dict:
    return yaml.safe_load(MATRIZ.read_text(encoding="utf-8"))


def test_ids_de_regras_sao_unicos():
    ids = ids_em_regras()
    repetidos = sorted({i for i in ids if ids.count(i) > 1})
    assert not repetidos, f"IDs repetidos em REGRAS.md: {repetidos}"


def test_regras_e_matriz_coincidem():
    regras = set(ids_em_regras())
    matriz = set(carregar_matriz()["regras"])
    assert regras - matriz == set(), f"Regras sem entrada na matriz: {sorted(regras - matriz)}"
    assert matriz - regras == set(), f"Entradas da matriz sem regra: {sorted(matriz - regras)}"


def test_cada_entrada_tem_etapa_valida():
    for regra, dados in carregar_matriz()["regras"].items():
        assert isinstance(dados.get("etapa"), int), f"{regra} sem etapa"
        assert 1 <= dados["etapa"] <= 7, f"{regra} com etapa fora de 1..7"
        assert isinstance(dados.get("testes"), list), f"{regra} sem lista de testes"


def test_regras_da_etapa_atual_tem_testes():
    matriz = carregar_matriz()
    etapa_atual = matriz["etapa_atual"]
    faltando = sorted(
        regra
        for regra, dados in matriz["regras"].items()
        if dados["etapa"] <= etapa_atual and not dados["testes"]
    )
    assert not faltando, f"Regras da etapa {etapa_atual} ou anterior sem teste: {faltando}"


def _testes_citados() -> list[str]:
    return sorted(
        {teste for dados in carregar_matriz()["regras"].values() for teste in dados["testes"]}
    )


@pytest.mark.parametrize("node_id", _testes_citados())
def test_testes_citados_existem(node_id: str):
    arquivo, _, funcao = node_id.partition("::")
    caminho = RAIZ / "tests" / arquivo
    assert caminho.is_file(), f"Arquivo de teste inexistente: {arquivo}"
    assert re.search(rf"^def {re.escape(funcao)}\(", caminho.read_text(encoding="utf-8"), re.M), (
        f"Função de teste inexistente: {node_id}"
    )
