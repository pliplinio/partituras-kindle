"""Laboratório de regressão da Fanfateste (TST-01, TST-02).

Executa o código produtivo do HTML ao PDF, sem Drive, Gmail nem Kindle.
Cenários 1 a 4 são sequenciais; 7 a 12 partem do estado do cenário 4.
Os cenários 5 e 6 (substituição rápida) entram na etapa 4.

Requer o Chromium do Playwright (`python -m playwright install chromium`).
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pymupdf
import pytest

from partituras.casos_de_uso.gerar_pdf import gerar_candidato
from partituras.dominio.erros import Ambiguidade, Inconsistencia
from partituras.dominio.modelos import Papel
from partituras.dominio.plano import planejar
from partituras.html.documento import Documento
from partituras.html.edicao import (
    PedidoMusica,
    gravar_musica,
    gravar_versao_template,
    reconstruir_setlist,
)
from partituras.pdf import gate

pytestmark = pytest.mark.chromium

ENTRADA = Path(__file__).parent / "golden" / "entrada"
MUSICAS = {
    "Jonia": ["Jonia.png"],
    "Doria": ["Doria (1 de 2).png", "Doria (2 de 2).png"],
    "Frigia": ["Frigia (1 de 2).png", "Frigia (2 de 2).png"],
    "Lidio": ["Lidio.png"],
}


def _incluir(doc: Documento, musica: str, setlist: list[str]) -> Documento:
    imagens = tuple(ENTRADA / nome for nome in MUSICAS[musica])
    doc, rel = gravar_musica(doc, PedidoMusica("Fanfateste", musica, imagens), substituir=False)
    assert rel.imagens_entrada_sha256 == rel.imagens_incorporadas_sha256
    doc, _ = reconstruir_setlist(doc, setlist)
    return doc


@pytest.fixture(scope="module")
def estados() -> dict[str, Documento]:
    """HTML canônico após cada cenário sequencial 1 a 4."""
    base = Documento.de_bytes((ENTRADA / "template_v01.html").read_bytes())
    base = gravar_versao_template(base, 1)
    resultado = {}
    doc = _incluir(base, "Jonia", ["Jonia"])
    resultado["01_Jonia"] = doc
    doc = _incluir(doc, "Doria", ["Jonia", "Doria"])
    resultado["02_Doria"] = doc
    doc = _incluir(doc, "Frigia", ["Jonia", "Doria", "Frigia"])
    resultado["03_Frigia"] = doc
    doc = _incluir(doc, "Lidio", ["Jonia", "Doria", "Frigia", "Lidio"])
    resultado["04_Lidio"] = doc
    return resultado


def _gerar(doc: Documento, pasta: Path, nome: str):
    return gerar_candidato(doc.para_bytes(), pasta, f"{nome}.pdf")


def _sequencia(resultado) -> list[tuple[str, int | None]]:
    return [(p.musica or str(p.papel), p.parte) for p in resultado.plano.paginas]


@pytest.mark.parametrize(
    ("cenario", "paginas", "musicas"),
    [
        ("01_Jonia", 3, ["Jonia"]),
        ("02_Doria", 5, ["Jonia", "Doria"]),
        ("03_Frigia", 7, ["Jonia", "Doria", "Frigia"]),
        ("04_Lidio", 8, ["Jonia", "Doria", "Frigia", "Lidio"]),
    ],
)
def test_cenarios_sequenciais(estados, tmp_path, cenario, paginas, musicas):
    doc = estados[cenario]
    assert doc.versao_template == 1
    assert [m.titulo for m in doc.repertorio().musicas] == musicas
    r = _gerar(doc, tmp_path, cenario)
    assert r.gate.paginas_reais == paginas
    assert [i["ok"] for i in r.gate.setlist] == [True] * len(musicas)
    assert all(i["ok"] for i in r.gate.indice)
    assert all(p["retornos"] >= 2 for p in r.gate.partituras)
    assert r.candidato.name == f"{cenario}.candidate.pdf"
    assert hashlib.sha256(r.candidato.read_bytes()).hexdigest() == r.sha256


def test_07_setlist_reordenado(estados, tmp_path):
    """Ordem do set list diferente da canônica; Doria preservada ao final (SET-06, PRES-02)."""
    doc, _ = reconstruir_setlist(estados["04_Lidio"], ["Lidio", "Frigia", "Jonia"])
    r = _gerar(doc, tmp_path, "07")
    assert _sequencia(r) == [
        ("setlist", None), ("index", None),
        ("Lidio", 1), ("Frigia", 1), ("Frigia", 2), ("Jonia", 1),
        ("Doria", 1), ("Doria", 2),
    ]  # fmt: skip
    assert r.plano.preservadas == ["doria"]


def test_08_repeticao_multipagina(estados, tmp_path):
    """Música repetida gera ocorrências físicas distintas, cada item com a sua (SET-05)."""
    doc, _ = reconstruir_setlist(estados["04_Lidio"], ["Doria", "Jonia", "Doria"])
    r = _gerar(doc, tmp_path, "08")
    assert r.gate.paginas_reais == 10
    destinos = [i["destinos"] for i in r.gate.setlist]
    assert destinos == [[3], [5], [6]]
    doria = [p for p in r.plano.paginas_partitura if p.grupo == "doria"]
    assert [(p.pagina + 1, p.parte, p.ocorrencia) for p in doria] == [
        (3, 1, 1), (4, 2, 1), (6, 1, 2), (7, 2, 2),
    ]  # fmt: skip
    indice_doria = next(i for i in r.gate.indice if i["titulo"] == "Doria")
    assert indice_doria["destinos"] == [3]


def test_09_setlist_reduzido_preserva_os_demais(estados, tmp_path):
    """PRES-01, PRES-02: todas as músicas aparecem; as fora do set list vão ao final."""
    doc, _ = reconstruir_setlist(estados["04_Lidio"], ["Frigia"])
    r = _gerar(doc, tmp_path, "09")
    assert r.plano.preservadas == ["jonia", "doria", "lidio"]
    assert r.gate.paginas_reais == 8


def test_10_musica_sem_partitura(estados, tmp_path):
    """SET-09: item visível, sem link e sem página inventada."""
    with pytest.raises(Ambiguidade):
        reconstruir_setlist(estados["04_Lidio"], ["Jonia", "Mixolidio", "Lidio"])
    doc, rel = reconstruir_setlist(estados["04_Lidio"], ["Jonia", "Inexistente", "Lidio"])
    assert rel.ausentes == [{"posicao": 2, "titulo": "Inexistente"}]
    r = _gerar(doc, tmp_path, "10")
    item = r.gate.setlist[1]
    assert item["titulo"] == "Inexistente" and item["destinos"] == [] and item["ok"]
    assert r.gate.paginas_reais == 8


@pytest.fixture(scope="module")
def pdf_04(estados, tmp_path_factory):
    pasta = tmp_path_factory.mktemp("pdf04")
    resultado = _gerar(estados["04_Lidio"], pasta, "04")
    return resultado


def _corromper(origem: Path, destino: Path, alterar) -> Path:
    with pymupdf.open(origem) as doc:
        alterar(doc)
        doc.save(destino)
    return destino


def test_11_link_externo_e_rejeitado(pdf_04, tmp_path):
    """LNK-05: o gate rejeita a corrupção."""

    def externo(doc):
        doc[2].insert_link(
            {
                "kind": pymupdf.LINK_URI,
                "from": pymupdf.Rect(300, 300, 360, 320),
                "uri": "https://x.y",
            }
        )

    pdf = _corromper(pdf_04.candidato, tmp_path / "11.pdf", externo)
    with pytest.raises(Inconsistencia, match="externo"):
        gate.validar(pdf, pdf_04.plano)


def test_12_destino_interno_errado_e_rejeitado(pdf_04, tmp_path):
    """LNK-06: link interno válido, mas para a música errada."""

    def errado(doc):
        pagina = doc[0]
        primeiro = pagina.get_links()[0]
        primeiro["page"] = 7
        pagina.update_link(primeiro)

    pdf = _corromper(pdf_04.candidato, tmp_path / "12.pdf", errado)
    with pytest.raises(Inconsistencia, match="set list 1"):
        gate.validar(pdf, pdf_04.plano)


def test_indice_sem_link_e_rejeitado(pdf_04, tmp_path):
    """LNK-08: contagem não basta; cada rótulo precisa do seu destino."""

    def sem_link(doc):
        pagina = doc[1]
        pagina.delete_link(pagina.get_links()[0])

    pdf = _corromper(pdf_04.candidato, tmp_path / "x.pdf", sem_link)
    with pytest.raises(Inconsistencia, match="índice"):
        gate.validar(pdf, pdf_04.plano)


def test_link_que_cobre_pouco_do_texto_e_rejeitado(pdf_04, tmp_path):
    """LNK-07: a área clicável precisa cobrir pelo menos 90% do texto."""

    def estreito(doc):
        pagina = doc[0]
        link = pagina.get_links()[0]
        r = pymupdf.Rect(link["from"])
        centro = (r.x0 + r.x1) / 2
        link["from"] = pymupdf.Rect(centro - 2, r.y0, centro + 2, r.y1)
        pagina.update_link(link)

    pdf = _corromper(pdf_04.candidato, tmp_path / "c.pdf", estreito)
    with pytest.raises(Inconsistencia, match="set list 1"):
        gate.validar(pdf, pdf_04.plano)


def test_retorno_ausente_e_rejeitado(pdf_04, tmp_path):
    """LNK-01: título e ABC de toda partitura voltam para a página 1."""

    def sem_retorno(doc):
        pagina = doc[4]
        for link in pagina.get_links():
            pagina.delete_link(link)

    pdf = _corromper(pdf_04.candidato, tmp_path / "r.pdf", sem_retorno)
    with pytest.raises(Inconsistencia, match="página 5: retornos"):
        gate.validar(pdf, pdf_04.plano)


def test_paginas_a_mais_reprovam(pdf_04, tmp_path):
    """VAL-02, VAL-07: total real diferente do esperado."""

    def duplicar(doc):
        doc.fullcopy_page(2)

    pdf = _corromper(pdf_04.candidato, tmp_path / "d.pdf", duplicar)
    with pytest.raises(Inconsistencia, match="páginas reais/esperadas"):
        gate.validar(pdf, pdf_04.plano)


def test_pdf_corrompido_reprova(pdf_04, tmp_path):
    """VAL-07: saída corrompida."""
    pdf = tmp_path / "ruim.pdf"
    pdf.write_bytes(b"%PDF-1.7 lixo")
    with pytest.raises(Inconsistencia):
        gate.validar(pdf, pdf_04.plano)


def test_indice_fisico_em_tres_colunas(pdf_04):
    """IDX-06, IDX-07: 4 músicas em 2/1/1, leitura coluna a coluna alfabética."""
    assert pdf_04.gate.indice_colunas == [2, 1, 1]
    assert [i["titulo"] for i in pdf_04.gate.indice] == ["Doria", "Frigia", "Jonia", "Lidio"]


def test_falha_no_gate_descarta_candidato(estados, tmp_path, monkeypatch):
    """PDF-10: se a validação falha, o candidato é apagado."""
    from partituras.casos_de_uso import gerar_pdf

    def falhar(*_):
        raise Inconsistencia("falha simulada")

    monkeypatch.setattr(gerar_pdf, "validar", falhar)
    with pytest.raises(Inconsistencia):
        _gerar(estados["01_Jonia"], tmp_path, "falha")
    assert list(tmp_path.iterdir()) == []


def test_pdf_cru_nao_sobra(estados, tmp_path):
    """PDF-07: o PDF cru é temporário; só o candidato fica na pasta."""
    _gerar(estados["01_Jonia"], tmp_path, "Fanfateste_v02")
    assert [p.name for p in tmp_path.iterdir()] == ["Fanfateste_v02.candidate.pdf"]


def test_conversor_gera_uma_pagina_por_slide(estados, tmp_path):
    """PDF-06: contagem e geometria do PDF cru."""
    from partituras.pdf.conversao import ChromiumConversor, conferir_pdf_cru

    doc = estados["04_Lidio"]
    cru = tmp_path / "cru.pdf"
    ChromiumConversor().converter(doc.para_bytes(), cru)
    conferir_pdf_cru(cru, len(doc.secoes))
    with pytest.raises(Inconsistencia, match="slides"):
        conferir_pdf_cru(cru, len(doc.secoes) + 1)


def test_plano_igual_na_geracao_e_no_gate(estados):
    """PDF-09: o gate deriva de novo o plano do HTML e chega ao mesmo resultado."""
    doc = estados["04_Lidio"]
    a = planejar(doc.repertorio())
    b = planejar(Documento.de_bytes(doc.para_bytes()).repertorio())
    assert a.paginas == b.paginas and a.setlist == b.setlist and a.indice == b.indice
    assert [p.papel for p in a.paginas[:2]] == [Papel.SETLIST, Papel.INDICE]
