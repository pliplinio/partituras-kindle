"""Verificações da estrutura do projeto: versão, changelog e camadas."""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

from partituras.version import __version__

RAIZ = Path(__file__).resolve().parent.parent
PACOTE = RAIZ / "src" / "partituras"

# Camadas que cada camada pode importar (além de si mesma e da biblioteca padrão).
DEPENDENCIAS_PERMITIDAS = {
    "dominio": set(),
    "html": {"dominio"},
    "pdf": {"dominio"},
    "adaptadores": {"dominio", "casos_de_uso"},
    "casos_de_uso": {"dominio", "html", "pdf", "adaptadores"},
}


def test_versao_semantica():
    assert re.fullmatch(r"\d+\.\d+\.\d+", __version__)


def test_changelog_tem_versao_atual():
    changelog = (RAIZ / "CHANGELOG.md").read_text(encoding="utf-8")
    assert f"## [{__version__}]" in changelog


def test_versao_codigo_independente():
    """A versão do código não é derivada de template, PDF nem testes (VER-03)."""
    fonte = (PACOTE / "version.py").read_text(encoding="utf-8")
    arvore = ast.parse(fonte)
    atribuicoes = [n for n in arvore.body if isinstance(n, ast.Assign)]
    assert len(atribuicoes) == 1
    assert isinstance(atribuicoes[0].value, ast.Constant)
    assert not any(isinstance(n, (ast.Import, ast.ImportFrom)) for n in arvore.body)


def _imports_internos(arquivo: Path) -> set[str]:
    camadas: set[str] = set()
    for no in ast.walk(ast.parse(arquivo.read_text(encoding="utf-8"))):
        nomes: list[str] = []
        if isinstance(no, ast.ImportFrom) and no.module and no.level == 0:
            nomes = [no.module]
        elif isinstance(no, ast.Import):
            nomes = [alias.name for alias in no.names]
        for nome in nomes:
            partes = nome.split(".")
            if (
                partes[0] == "partituras"
                and len(partes) > 1
                and partes[1] in DEPENDENCIAS_PERMITIDAS
            ):
                camadas.add(partes[1])
    return camadas


@pytest.mark.parametrize("camada", sorted(DEPENDENCIAS_PERMITIDAS))
def test_camadas_respeitam_dependencias(camada: str):
    pasta = PACOTE / camada
    assert pasta.is_dir(), f"Camada ausente: {camada}"
    for arquivo in pasta.rglob("*.py"):
        proibidas = _imports_internos(arquivo) - DEPENDENCIAS_PERMITIDAS[camada] - {camada}
        assert not proibidas, f"{arquivo.relative_to(RAIZ)} importa camadas proibidas: {proibidas}"
