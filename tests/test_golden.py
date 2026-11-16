"""Laboratório de regressão da Fanfateste (TST-01, TST-02).

Executa o código produtivo do HTML ao PDF, sem Drive, Gmail nem Kindle.
Cenários 1 a 4 são sequenciais; 5 a 12 partem do estado do cenário 4.

Requer o Chromium do Playwright (`python -m playwright install chromium`).
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pymupdf
import pytest

from partituras import cli
from partituras.casos_de_uso import executar
from partituras.casos_de_uso.gerar_pdf import gerar_candidato
from partituras.casos_de_uso.substituir_musica import Anterior, substituir
from partituras.dominio.erros import Ambiguidade, Bloqueio, Inconsistencia
from partituras.dominio.modelos import Papel
from partituras.dominio.plano import planejar
from partituras.html import escopo
from partituras.html.documento import Documento
from partituras.html.edicao import (
    PedidoMusica,
    gravar_musica,
    gravar_versao_template,
    reconstruir_setlist,
)
from partituras.pdf import gate
from partituras.pdf.fingerprint import delta, manifesto
from partituras.pdf.inspecao import folhas_de_contato, pre_validar, registrar_inspecao, renderizar

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


# --- Cenários 5 e 6: substituição rápida (etapa 4) -------------------------------------------


def _anterior(pdf_04) -> Anterior:
    return Anterior(sha256=pdf_04.sha256, pdf=pdf_04.candidato)


def test_05_substituicao_rapida_uma_pagina(estados, pdf_04, tmp_path):
    """PDF-11, VAL-05, FLX-03: patch incremental, gate nominal e inspeção só da música."""
    pedido = PedidoMusica("Fanfateste", "Lidio", (ENTRADA / "Jonia.png",))
    r = substituir(estados["04_Lidio"].para_bytes(), pedido, tmp_path, "05.pdf", _anterior(pdf_04))
    assert r.metodo == "incremental_pdf_patch" and r.motivo_integral is None
    assert r.nominal["presenca_ok"] and r.nominal["partes_encontradas"] == [1]
    lidio = [p.pagina + 1 for p in pdf_04.plano.paginas_partitura if p.grupo == "lidio"]
    assert sorted(r.delta.para_inspecao) == lidio
    assert len(r.delta.reutilizaveis) == 7
    assert [p.name for p in r.renders] == [f"pagina-{lidio[0]:03d}.png"]


def test_06_substituicao_rapida_multipagina(estados, pdf_04, tmp_path):
    """PDF-11 em música de 2 partes."""
    imagens = (ENTRADA / "Frigia (1 de 2).png", ENTRADA / "Frigia (2 de 2).png")
    pedido = PedidoMusica("Fanfateste", "Doria", imagens)
    r = substituir(estados["04_Lidio"].para_bytes(), pedido, tmp_path, "06.pdf", _anterior(pdf_04))
    assert r.metodo == "incremental_pdf_patch"
    assert r.nominal["partes_encontradas"] == [1, 2]
    assert sorted(r.delta.para_inspecao) == [4, 5]


def test_mudanca_de_partes_cai_para_geracao_integral(estados, pdf_04, tmp_path):
    """PDF-12: o motivo do fallback fica registrado."""
    pedido = PedidoMusica(
        "Fanfateste", "Lidio", (ENTRADA / "Doria (1 de 2).png", ENTRADA / "Lidio.png")
    )
    r = substituir(estados["04_Lidio"].para_bytes(), pedido, tmp_path, "x.pdf", _anterior(pdf_04))
    assert r.metodo == "geracao_integral"
    assert "páginas" in r.motivo_integral
    assert r.nominal["partes_encontradas"] == [1, 2]


def test_patch_exige_sha_aprovado(estados, pdf_04, tmp_path):
    """PDF-11: o PDF anterior precisa ter o SHA-256 aprovado."""
    pedido = PedidoMusica("Fanfateste", "Lidio", (ENTRADA / "Jonia.png",))
    with pytest.raises(Bloqueio):
        substituir(
            estados["04_Lidio"].para_bytes(),
            pedido,
            tmp_path,
            "y.pdf",
            Anterior("0" * 64, pdf=pdf_04.candidato),
        )
    assert not (tmp_path / "y.candidate.pdf").exists()


def test_patch_preserva_links_das_outras_paginas(estados, pdf_04, tmp_path):
    """Links compartilhados entre páginas não podem sumir com o patch."""
    pedido = PedidoMusica("Fanfateste", "Lidio", (ENTRADA / "Jonia.png",))
    r = substituir(estados["04_Lidio"].para_bytes(), pedido, tmp_path, "z.pdf", _anterior(pdf_04))
    with pymupdf.open(r.candidato) as doc, pymupdf.open(pdf_04.candidato) as antes:
        assert [len(p.get_links()) for p in doc] == [len(p.get_links()) for p in antes]


def test_mesmo_pdf_reaproveita_tudo(pdf_04):
    """FLX-05: mesmo SHA-256 (só mudou o nome) não pede renderização."""
    m = manifesto(pdf_04.candidato)
    d = delta(m, m)
    assert not d.para_inspecao and len(d.reutilizaveis) == 8


def test_escopo_bloqueia_mudanca_fora_do_grupo(estados):
    """VAL-04."""
    antes = estados["04_Lidio"]
    depois, _ = reconstruir_setlist(antes, ["Lidio", "Jonia"])
    rel = escopo.verificar(antes, depois, "lidio")
    assert "set list mudou (posições, títulos ou grupos)" in rel.violacoes
    with pytest.raises(Inconsistencia, match="escopo"):
        escopo.exigir(antes, depois, "lidio")


def test_pre_validacao_sinaliza_pagina_vazia(pdf_04, tmp_path):
    """VAL-08."""

    def esvaziar(doc):
        pagina = doc[2]
        pagina.add_redact_annot(pagina.rect, fill=(1, 1, 1))
        pagina.apply_redactions(images=pymupdf.PDF_REDACT_IMAGE_REMOVE)

    pdf = _corromper(pdf_04.candidato, tmp_path / "v.pdf", esvaziar)
    tipos = {(a.pagina, a.tipo) for a in pre_validar(pdf, pdf_04.plano)}
    assert (3, "pagina_vazia") in tipos and (3, "imagem_ausente") in tipos
    assert pre_validar(pdf_04.candidato, pdf_04.plano) == []


def test_registro_de_inspecao_exige_todas_as_paginas(pdf_04):
    """INS-06, INS-07: não se declara inspeção que não foi feita."""
    d = delta(manifesto(pdf_04.candidato), None)
    with pytest.raises(Bloqueio, match="faltam"):
        registrar_inspecao(pdf_04.candidato, d, [1, 2, 3])
    reg = registrar_inspecao(pdf_04.candidato, d, list(range(1, 9)))
    assert reg.sha256 == pdf_04.sha256 and reg.aprovada
    assert "cortes" in reg.checklist and "páginas ausentes" in reg.checklist


def test_folhas_de_contato_ate_6(pdf_04, tmp_path):
    """INS-05."""
    renders = renderizar(pdf_04.candidato, range(1, 9), tmp_path)
    folhas = folhas_de_contato(renders, tmp_path)
    assert len(renders) == 8 and len(folhas) == 2
    with pytest.raises(ValueError):
        folhas_de_contato(renders, tmp_path, por_folha=7)


# --- Etapa 5: execução completa pelo CLI ----------------------------------------------------


def _cli(*args) -> int:
    return cli.main([str(a) for a in args])


def test_fluxo_completo_pelo_cli(estados, tmp_path, capsys):
    """FLX-01, PRO-03, KIN-05, HIS-01, REL-01: duas execuções seguidas na mesma pasta."""
    pasta = tmp_path / "partituras_claude"
    pasta.mkdir()
    (pasta / "Fanfateste.html").write_bytes(estados["04_Lidio"].para_bytes())

    t1 = tmp_path / "exec1"
    assert _cli("iniciar", "--trabalho", t1) == 0
    assert _cli("preparar", "--trabalho", t1, "--pasta", pasta, "--fanfarra", "Fanfateste") == 0
    assert _cli("gerar", "--trabalho", t1) == 0
    estado = executar.Estado.abrir(t1)
    assert estado.dados["paginas_para_inspecao"] == list(range(1, 9))  # sem anterior: integral
    assert _cli("promover", "--trabalho", t1, "--pasta", pasta) == 2  # sem inspeção, nada grava
    assert not (pasta / "Fanfateste_v01.pdf").exists()
    assert _cli("aprovar", "--trabalho", t1, "--inspecionadas", "1-8") == 0
    assert _cli("promover", "--trabalho", t1, "--pasta", pasta) == 0
    assert _cli("kindle", "--trabalho", t1, "--metodo", "gmail_conector_envio",
                "--resultado", "sucesso") == 0  # fmt: skip
    capsys.readouterr()
    assert _cli("finalizar", "--trabalho", t1, "--pasta", pasta) == 0
    relatorio = capsys.readouterr().out.strip().splitlines()
    assert relatorio[-1] == "STATUS FINAL: SUCESSO"
    assert (pasta / "Fanfateste_v01.pdf").is_file()
    assert (pasta / "automacao/manifestos/Fanfateste_v01.manifest.json").is_file()

    t2 = tmp_path / "exec2"
    _cli("iniciar", "--trabalho", t2, "--sem-envio")
    _cli("preparar", "--trabalho", t2, "--pasta", pasta, "--fanfarra", "Fanfateste")
    assert _cli("substituir", "--trabalho", t2, "--pasta", pasta, "--musica", "Lidio",
                "--imagens", ENTRADA / "Jonia.png") == 0  # fmt: skip
    estado = executar.Estado.abrir(t2)
    assert estado.dados["metodo_pdf"] == "incremental_pdf_patch"
    assert len(estado.dados["paginas_para_inspecao"]) == 1
    assert estado.cronometro.contadores["edicoes_html"] == 1
    pagina = estado.dados["paginas_para_inspecao"][0]
    _cli("aprovar", "--trabalho", t2, "--inspecionadas", pagina)
    assert _cli("promover", "--trabalho", t2, "--pasta", pasta) == 0
    capsys.readouterr()
    _cli("finalizar", "--trabalho", t2, "--pasta", pasta)
    assert capsys.readouterr().out.strip().splitlines()[-2:] == [
        "ENVIO AO KINDLE: NAO_SOLICITADO",
        "STATUS FINAL: SUCESSO",
    ]
    assert (pasta / "Fanfateste_v02.pdf").is_file()
    historico = (pasta / "automacao/historico_execucoes.jsonl").read_text().splitlines()
    assert len(historico) == 2
    assert len(list((pasta / "automacao/relatorios").iterdir())) == 2


def test_inspecao_reprovada_nao_promove(estados, tmp_path, capsys):
    """INS-07, PRO-01: achado na inspeção encerra com falha e sem gravar nada."""
    pasta = tmp_path / "partituras_claude"
    pasta.mkdir()
    (pasta / "Fanfateste.html").write_bytes(estados["04_Lidio"].para_bytes())
    t = tmp_path / "exec"
    _cli("iniciar", "--trabalho", t)
    _cli("preparar", "--trabalho", t, "--pasta", pasta, "--fanfarra", "Fanfateste")
    _cli("gerar", "--trabalho", t)
    assert _cli("aprovar", "--trabalho", t, "--inspecionadas", "1-8",
                "--achado", "4:partitura cortada") == 2  # fmt: skip
    assert _cli("promover", "--trabalho", t, "--pasta", pasta) == 2
    capsys.readouterr()
    _cli("finalizar", "--trabalho", t, "--pasta", pasta)
    saida = capsys.readouterr().out.strip().splitlines()
    assert saida[-3:] == [
        "PROCESSAMENTO DO PDF: FALHA",
        "ENVIO AO KINDLE: FALHA",
        "STATUS FINAL: FALHA",
    ]
    assert sorted(p.name for p in pasta.iterdir()) == ["Fanfateste.html", "automacao"]
