"""Fingerprint, delta e referências golden (INS-01 a INS-04, INS-08, INS-09, TST-03, TST-04)."""

from __future__ import annotations

import json
from pathlib import Path

import pymupdf
import pytest
from golden import laboratorio

from partituras.dominio.erros import Bloqueio, Inconsistencia
from partituras.pdf.fingerprint import (
    DPI,
    SCHEMA_MANIFESTO,
    carregar_manifesto_aprovado,
    delta,
    manifesto,
    manifesto_aprovado,
    sha256_arquivo,
)


def _pdf(caminho: Path, textos: list[str], tamanho=(660, 487.92)) -> Path:
    doc = pymupdf.open()
    for i, texto in enumerate(textos):
        pagina = doc.new_page(width=tamanho[0], height=tamanho[1])
        pagina.insert_text((50, 60), texto, fontsize=20)
        if i > 0:
            pagina.insert_link(
                {"kind": pymupdf.LINK_GOTO, "from": pymupdf.Rect(40, 40, 200, 70), "page": 0}
            )
    doc.save(caminho)
    doc.close()
    return caminho


@pytest.fixture
def anterior(tmp_path) -> dict:
    return manifesto(_pdf(tmp_path / "a.pdf", ["Indice", "Jonia", "Doria", "Frigia"]))


def test_manifesto_cobre_todas_as_paginas(tmp_path):
    """INS-01: 100% das páginas a 110 DPI, com pixels, texto e links."""
    pdf = _pdf(tmp_path / "m.pdf", ["A", "B", "C"])
    m = manifesto(pdf)
    assert m["schema"] == SCHEMA_MANIFESTO and m["dpi"] == DPI == 110
    assert m["total_paginas"] == 3 and [p["pagina"] for p in m["paginas"]] == [1, 2, 3]
    assert m["pdf_sha256"] == sha256_arquivo(pdf)
    campos = {"visual_sha256", "text_sha256", "links_sha256", "links_count", "page_width"}
    assert campos <= set(m["paginas"][0])


def test_destino_no_ponto_zero_entra_no_fingerprint_de_links(tmp_path):
    """Point(0, 0) é falso em Python; o destino precisa constar mesmo assim."""
    m = manifesto(_pdf(tmp_path / "z.pdf", ["A", "B"]))
    sem_destino = manifesto(_pdf(tmp_path / "w.pdf", ["A", "B"]))
    assert m["paginas"][1]["links_sha256"] == sem_destino["paginas"][1]["links_sha256"]
    assert m["paginas"][1]["links_count"] == 1


def test_reuso_independe_da_posicao(tmp_path, anterior):
    """INS-02: mesma página em outra posição herda a inspeção."""
    cand = manifesto(_pdf(tmp_path / "c.pdf", ["Indice", "Frigia", "Jonia", "Novo"]))
    d = delta(cand, anterior)
    assert d.reutilizaveis == {1: [1], 2: [4], 3: [2]}
    assert list(d.para_inspecao) == [4] and not d.integral


def test_mudanca_so_de_links_reaproveita_e_registra(tmp_path, anterior):
    """INS-03."""
    caminho = _pdf(tmp_path / "l.pdf", ["Indice", "Jonia", "Doria", "Frigia"])
    with pymupdf.open(caminho) as doc:
        doc[2].insert_link(
            {"kind": pymupdf.LINK_GOTO, "from": pymupdf.Rect(300, 40, 400, 70), "page": 1}
        )
        doc.saveIncr()
    d = delta(manifesto(caminho), anterior)
    assert not d.para_inspecao and d.links_mudaram == [3]


@pytest.mark.parametrize(
    ("argumentos", "motivo"),
    [
        ({"mudanca_template": True}, "mudança de template"),
        ({"mudanca_renderizador": True}, "mudança do mecanismo de renderização"),
        ({"pedido_integral": True}, "pedido do usuário"),
    ],
)
def test_inspecao_integral_obrigatoria(tmp_path, anterior, argumentos, motivo):
    """INS-04."""
    cand = manifesto(_pdf(tmp_path / "c.pdf", ["Indice", "Jonia", "Doria", "Frigia"]))
    d = delta(cand, anterior, **argumentos)
    assert d.integral and d.motivo_integral == motivo and len(d.para_inspecao) == 4


def test_inspecao_integral_sem_anterior_e_com_outro_tamanho(tmp_path, anterior):
    """INS-04: sem PDF anterior verificável ou com tamanho de página diferente."""
    cand = manifesto(_pdf(tmp_path / "c.pdf", ["Indice", "Jonia"]))
    assert delta(cand, None).motivo_integral == "sem PDF anterior aprovado verificável"
    outro = manifesto(_pdf(tmp_path / "o.pdf", ["Indice", "Jonia"], tamanho=(880, 650)))
    assert delta(outro, anterior).motivo_integral == "mudança de tamanho de página"


def test_mesmo_sha_reaproveita_tudo(anterior):
    """FLX-05."""
    d = delta(anterior, anterior)
    assert not d.para_inspecao and len(d.reutilizaveis) == 4


def test_manifesto_anterior_exige_sha_aprovado(anterior):
    """INS-02, INS-09: schema, DPI e SHA-256 conferidos antes do reuso."""
    sha = anterior["pdf_sha256"]
    assert carregar_manifesto_aprovado(anterior, sha) is anterior
    assert carregar_manifesto_aprovado({"delta": {"candidate_manifest": anterior}}, sha) is anterior
    with pytest.raises(Bloqueio):
        carregar_manifesto_aprovado(anterior, "f" * 64)
    with pytest.raises(Inconsistencia):
        carregar_manifesto_aprovado({**anterior, "dpi": 72}, sha)
    with pytest.raises(Inconsistencia):
        carregar_manifesto_aprovado({**anterior, "schema": "outro"}, sha)
    with pytest.raises(Inconsistencia):
        carregar_manifesto_aprovado(anterior, "abc")


def test_manifesto_aprovado_registra_inspecao_e_origem(tmp_path, anterior):
    """INS-08."""
    cand = manifesto(_pdf(tmp_path / "c.pdf", ["Indice", "Jonia", "Novo"]))
    d = delta(cand, anterior)
    m = manifesto_aprovado(cand, d, [3], "Fanfateste_v01.pdf")
    assert m["paginas_inspecionadas"] == [3] and m["paginas_reutilizadas"] == [1, 2]
    assert m["origem_reuso"] == "Fanfateste_v01.pdf" and m["pdf_sha256"] == cand["pdf_sha256"]
    assert json.loads(json.dumps(m)) == m


# --- Laboratório golden ---------------------------------------------------------------------


def _snap(anterior) -> dict:
    return laboratorio.snapshot(anterior, ["indice", "jonia"])


def test_golden_compara_sem_alterar_referencia(tmp_path, anterior):
    """TST-04: a execução normal só lê `expected/`."""
    expected = tmp_path / "expected"
    expected.mkdir()
    snap = _snap(anterior)
    assert laboratorio.comparar("01_Jonia", snap, expected)["golden"] == "SEM_GOLDEN"
    assert not any(expected.iterdir())


def test_golden_exige_aprovacao_visual_explicita(tmp_path, anterior):
    """TST-04."""
    snaps = {c: _snap(anterior) for c in laboratorio.POSITIVOS}
    with pytest.raises(PermissionError):
        laboratorio.promover(snaps, {}, tmp_path)
    with pytest.raises(PermissionError, match="não cobre"):
        laboratorio.promover(snaps, {"approved": True, "scenarios": ["01_Jonia"]}, tmp_path)
    aprovacao = {"approved": True, "scenarios": list(laboratorio.POSITIVOS)}
    assert len(laboratorio.promover(snaps, aprovacao, tmp_path)) == 10
    assert laboratorio.comparar("01_Jonia", snaps["01_Jonia"], tmp_path)["golden"] == "OK"
    alterado = {**snaps["01_Jonia"], "sequencia": ["indice"]}
    assert laboratorio.comparar("01_Jonia", alterado, tmp_path)["golden"] == "DIVERGENTE"


def test_pass_e_regressao_validada(anterior):
    """TST-03: regressão validada só com golden OK em todos os positivos."""
    sem = {c: {"golden": "SEM_GOLDEN"} for c in laboratorio.POSITIVOS}
    rejeitados = {n: True for n in laboratorio.NEGATIVOS}
    r = laboratorio.resumo(sem, rejeitados)
    assert r["status"] == "PASS" and r["regression_validated_against_golden"] is False
    ok = {c: {"golden": "OK"} for c in laboratorio.POSITIVOS}
    assert laboratorio.resumo(ok, rejeitados)["regression_validated_against_golden"] is True
    assert laboratorio.resumo(ok, {"11_bad_external_link": True})["status"] == "FAIL"
    divergente = {**ok, "05_replace_fast_1p": {"golden": "DIVERGENTE"}}
    assert laboratorio.resumo(divergente, rejeitados)["status"] == "FAIL"
