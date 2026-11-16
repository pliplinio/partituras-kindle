"""Etapa 5: tempo, plano congelado, promoção, Kindle, histórico e relatório."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from partituras.adaptadores import historico
from partituras.adaptadores.pasta_local import PastaLocal
from partituras.casos_de_uso.promover import promover
from partituras.dominio.erros import Bloqueio, Inconsistencia
from partituras.dominio.execucao import (
    HISTORICO,
    Arquivo,
    conferir_acoes,
    conferir_pasta,
    conferir_plano,
    manifesto_de,
    planejar_execucao,
    sha256,
)
from partituras.dominio.kindle import (
    DESTINATARIO,
    LIMITE_ANEXO_CONECTOR_BYTES,
    Envio,
    Metodo,
    Status,
    caminhos,
    versoes_antigas,
)
from partituras.dominio.relatorio import estados_finais, montar, registro_historico
from partituras.dominio.tempo import INCOMPLETA, NAO_EXECUTADA, Cronometro

T0 = datetime(2026, 11, 16, 1, 0, tzinfo=UTC)


class Relogio:
    def __init__(self, inicio: datetime = T0) -> None:
        self.agora = inicio

    def __call__(self) -> datetime:
        return self.agora

    def avancar(self, segundos: float) -> None:
        self.agora += timedelta(seconds=segundos)


# --- Tempo --------------------------------------------------------------------------------------


def test_cronometro_comeca_antes_do_drive_e_nao_reinicia():
    """TMP-01, TMP-02."""
    r = Relogio()
    c = Cronometro.iniciar(r)
    r.avancar(2)
    c.leitura_drive(r)
    r.avancar(3)
    c.leitura_drive(r)
    assert c.workflow_started_at == T0 and c.first_drive_read_at == T0 + timedelta(seconds=2)
    assert c.request_received_at is None and c.contadores["descobertas_drive"] == 2
    copia = Cronometro.de_dict(json.loads(json.dumps(c.como_dict())))
    assert copia.workflow_started_at == T0
    with pytest.raises(ValueError):
        Cronometro.iniciar(r, request_received_at=datetime(2026, 1, 1))


def test_total_e_relogio_nao_soma_de_etapas():
    """TMP-03, TMP-04, TMP-05."""
    r = Relogio()
    c = Cronometro.iniciar(r, request_received_at=T0 - timedelta(seconds=10))
    c.comecar("pdf", r)
    r.avancar(4)
    c.terminar("pdf", "SUCESSO", r)
    r.avancar(6)
    c.registrar_nao_executada("kindle")
    c.finalizar(r)
    assert c.total == 10 and c.tempo_percebido == 20
    etapas = {e["nome"]: e for e in c.como_dict()["etapas"]}
    assert etapas["pdf"]["duracao_s"] == 4
    assert etapas["kindle"]["resultado"] == NAO_EXECUTADA and etapas["kindle"]["duracao_s"] is None
    assert c.como_dict()["latencia_de_exibicao"] == "excluída"


def test_contadores_previstos():
    """TMP-06."""
    c = Cronometro.iniciar()
    assert set(c.contadores) >= {"edicoes_html", "pdfs_candidatos", "fingerprints", "repeticoes"}
    with pytest.raises(KeyError):
        c.contar("inexistente")


def test_tempo_incompleto_reprova():
    """TMP-07: sem total confiável, STATUS FINAL: FALHA, PDF e Kindle separados."""
    c = Cronometro.iniciar()
    dados = {"processamento_ok": True, "kindle": {"status": "SUCESSO"}}
    estados = estados_finais(dados, c, [])
    assert estados["processamento_pdf"] == "SUCESSO" and estados["envio_kindle"] == "SUCESSO"
    assert estados["status_final"] == "FALHA" and INCOMPLETA in estados["motivos_falha"]


# --- Plano congelado e pasta ---------------------------------------------------------------------


def _listagem(*nomes: str) -> list[Arquivo]:
    return [Arquivo(n, f"id-{n}") for n in nomes]


def _planejar(nomes, versao_template=6):
    return planejar_execucao(
        "Skaravana",
        _listagem(*nomes),
        lambda nome: b"<html>" + nome.encode(),
        "G:/Meu Drive/Tuba/partituras_claude",
        lambda _: versao_template,
    )


def test_plano_congelado_com_anterior_aprovado():
    """FLX-01, FLX-02: uma listagem decide HTML, PDFs, anterior e próxima versão."""
    plano = _planejar(
        [
            "Skaravana.html",
            "Skaravana_v13.pdf",
            "Skaravana_v14.pdf",
            manifesto_de("Skaravana_v13.pdf"),
            "Xamego.html",
        ]
    )
    assert plano.html == "Skaravana.html" and plano.html_bytes == b"<html>Skaravana.html"
    assert plano.anterior_pdf == "Skaravana_v13.pdf"  # v14 sem manifesto não é referência
    assert plano.anterior_manifesto == "automacao/manifestos/Skaravana_v13.manifest.json"
    assert plano.nome_pdf == "Skaravana_v15.pdf"
    assert _planejar(["Skaravana.html"]).nome_pdf == "Skaravana_v01.pdf"
    with pytest.raises(Inconsistencia, match="versão de template"):
        _planejar(["Skaravana.html"], versao_template=None)


def test_descoberta_nova_exige_reiniciar():
    """FLX-01."""
    plano = _planejar(["Skaravana.html", "Skaravana_v14.pdf"])
    conferir_plano(plano, _listagem("Skaravana.html", "Skaravana_v14.pdf", "outro.txt"))
    with pytest.raises(Bloqueio, match="reiniciar"):
        conferir_plano(plano, _listagem("Skaravana.html", "Skaravana_v14.pdf", "Skaravana_v15.pdf"))


def test_pasta_chatgpt_proibida(tmp_path):
    """ARQ-01."""
    conferir_pasta(r"G:\Meu Drive\Tuba\partituras_claude")
    with pytest.raises(Bloqueio):
        conferir_pasta(r"G:\Meu Drive\Tuba\Partituras_kindle")
    proibida = tmp_path / "Partituras_kindle"
    proibida.mkdir()
    with pytest.raises(Bloqueio):
        PastaLocal(proibida)


def test_acoes_necessarias_antes_do_processamento():
    """PRO-06."""
    todas = {"gravar_html", "criar_pdf", "ler_confirmar", "enviar_kindle"}
    conferir_acoes(todas)
    conferir_acoes(todas - {"enviar_kindle"}, sem_envio=True)
    with pytest.raises(Bloqueio, match="enviar_kindle"):
        conferir_acoes(todas - {"enviar_kindle"})


def test_pasta_local_preserva_bytes_e_id(tmp_path):
    """ARQ-04, HTML-08, PDF-04: mesmo arquivo, bytes intactos, PDF nunca sobrescrito."""
    pasta = PastaLocal(tmp_path)
    crlf = b"<html>\r\n<body></body>\r\n</html>\r\n"
    original = pasta.gravar("Skaravana.html", crlf, novo=True)
    reescrito = pasta.gravar("Skaravana.html", crlf + b"<!-- x -->", novo=False)
    assert original.id == reescrito.id and pasta.ler("Skaravana.html").endswith(b"-->")
    pasta.gravar("Skaravana_v01.pdf", b"%PDF", novo=True)
    with pytest.raises(FileExistsError):
        pasta.gravar("Skaravana_v01.pdf", b"%PDF outro", novo=True)
    with pytest.raises(ValueError):
        pasta.ler("../fora.txt")


# --- Promoção -------------------------------------------------------------------------------------


class PastaQueFalhaNoPdf(PastaLocal):
    def gravar(self, nome, dados, *, novo):
        if nome.endswith(".pdf"):
            raise OSError("disco cheio")
        return super().gravar(nome, dados, novo=novo)


def _cenario(tmp_path: Path, classe=PastaLocal):
    pasta = classe(tmp_path)
    original = b"<html>\r\noriginal\r\n</html>"
    pasta.gravar("Skaravana.html", original, novo=True)
    plano = planejar_execucao("Skaravana", pasta.listar(), pasta.ler, pasta.local, lambda _: 6)
    pdf = b"%PDF-1.7 candidato"
    manifesto = {"pdf_sha256": sha256(pdf), "paginas": []}
    return pasta, plano, original, pdf, manifesto


def test_promocao_na_ordem_com_conferencia(tmp_path):
    """PRO-01, PRO-02, PRO-03."""
    pasta, plano, _, pdf, manifesto = _cenario(tmp_path)
    novo_html = b"<html>\r\nnovo\r\n</html>"
    r = promover(pasta, plano, novo_html, pdf, sha256(pdf), manifesto)
    assert [o["operacao"] for o in r.operacoes] == ["gravar_html", "gravar_pdf", "gravar_manifesto"]
    assert pasta.ler("Skaravana.html") == novo_html and pasta.ler("Skaravana_v01.pdf") == pdf
    assert r.pdf_sha256 == sha256(pdf) and r.html.id == plano.html_id
    assert json.loads(pasta.ler(manifesto_de("Skaravana_v01.pdf")))["pdf_sha256"] == sha256(pdf)


def test_promocao_recusa_bytes_nao_inspecionados(tmp_path):
    """PRO-01, PRO-02."""
    pasta, plano, original, pdf, manifesto = _cenario(tmp_path)
    with pytest.raises(Bloqueio, match="inspecionado"):
        promover(pasta, plano, b"novo", pdf + b"x", sha256(pdf), manifesto)
    assert pasta.ler("Skaravana.html") == original


def test_falha_no_pdf_restaura_html(tmp_path):
    """PRO-04."""
    pasta, plano, original, pdf, manifesto = _cenario(tmp_path, PastaQueFalhaNoPdf)
    with pytest.raises(OSError):
        promover(pasta, plano, b"<html>novo</html>", pdf, sha256(pdf), manifesto)
    assert pasta.ler("Skaravana.html") == original


def test_html_alterado_por_fora_bloqueia(tmp_path):
    """PRO-03: o HTML original precisa ser o mesmo do início."""
    pasta, plano, _, pdf, manifesto = _cenario(tmp_path)
    pasta.gravar("Skaravana.html", b"editado no Drive", novo=False)
    with pytest.raises(Bloqueio, match="mudou"):
        promover(pasta, plano, b"novo", pdf, sha256(pdf), manifesto)


# --- Kindle --------------------------------------------------------------------------------------


def test_caminho_de_envio_por_tamanho():
    """KIN-03, KIN-04."""
    assert caminhos(1_000_000) == [Metodo.ENVIO_DIRETO, Metodo.RASCUNHO, Metodo.NAVEGADOR]
    assert caminhos(LIMITE_ANEXO_CONECTOR_BYTES + 1) == [Metodo.NAVEGADOR]
    assert DESTINATARIO.endswith("@kindle.com")


def test_bloqueio_so_depois_de_todas_as_tentativas():
    """KIN-04, KIN-05, PRO-05."""
    e = Envio("Skaravana_v01.pdf", "a" * 64, 1_000_000)
    assert e.status is Status.FALHA and e.proximo_caminho() is Metodo.ENVIO_DIRETO
    e.registrar(Metodo.ENVIO_DIRETO, False, "limite")
    assert e.proximo_caminho() is Metodo.RASCUNHO
    e.registrar(Metodo.RASCUNHO, False, "limite")
    assert e.status is Status.FALHA
    e.registrar(Metodo.NAVEGADOR, False, "sem login")
    assert e.status is Status.BLOQUEADO
    with pytest.raises(ValueError, match="link"):
        e.registrar(Metodo.NAVEGADOR, True, anexo=False)
    grande = Envio("x.pdf", "a" * 64, 5_000_000)
    with pytest.raises(ValueError):
        grande.registrar(Metodo.ENVIO_DIRETO, True)
    grande.registrar(Metodo.NAVEGADOR, True)
    assert grande.status is Status.SUCESSO
    assert [t["metodo"] for t in grande.como_dict()["tentativas"]] == [Metodo.NAVEGADOR.value]


def test_envio_nao_solicitado():
    """KIN-01: processamento sem envio só a pedido."""
    assert Envio("x.pdf", "a" * 64, 1, solicitado=False).status is Status.NAO_SOLICITADO


def test_versoes_antigas_do_kindle():
    """KIN-06."""
    titulos = ["Skaravana_v13", "Skaravana_v14_entrega", "Skaravana_v01", "Xamego_v38", "Skaravana"]
    # Numeração recomeçada (PDF-03): v14 da versão ChatGPT também é antigo.
    assert versoes_antigas("Skaravana", titulos, "Skaravana_v01") == [
        "Skaravana_v13",
        "Skaravana_v14_entrega",
    ]
    assert versoes_antigas("Skaravana", ["Skaravanas_v02", "Skaravana_v1"], "Skaravana_v01") == []


# --- Histórico e relatório -------------------------------------------------------------------


def test_historico_so_acrescenta_e_sem_segredos(tmp_path):
    """HIS-01, HIS-03."""
    pasta = PastaLocal(tmp_path)
    historico.anexar(pasta, {"comando": "gerar", "token": "abc", "detalhes": {"senha": "x"}})
    primeiro = pasta.ler(HISTORICO)
    historico.anexar(pasta, {"comando": "promover"})
    linhas = pasta.ler(HISTORICO).decode().splitlines()
    assert pasta.ler(HISTORICO).startswith(primeiro) and len(linhas) == 2
    assert "abc" not in linhas[0] and "senha" not in linhas[0]
    assert json.loads(linhas[0]) == {"comando": "gerar", "detalhes": {}}


def _cronometro_completo(etapas: list[str], pedido: bool = False) -> Cronometro:
    r = Relogio()
    c = Cronometro.iniciar(r, request_received_at=T0 if pedido else None)
    for nome in etapas:
        c.comecar(nome, r)
        r.avancar(1)
        c.terminar(nome, "SUCESSO", r)
    c.finalizar(r)
    return c


def test_relatorio_formato():
    """REL-02, REL-03, REL-04, REL-05."""
    etapas = ["preparar", "pdf", "inspecao", "promocao", "kindle"]
    dados = {
        "processamento_ok": True,
        "fanfarra": "Skaravana",
        "versao_template": 6,
        "pdf": "Skaravana_v01.pdf",
        "kindle": {"status": "SUCESSO"},
    }
    texto = montar(dados, _cronometro_completo(etapas), etapas)
    linhas = texto.splitlines()
    assert linhas[0].startswith("Tempo medido desde o início do atendimento")
    assert linhas[-3:] == [
        "PROCESSAMENTO DO PDF: SUCESSO",
        "ENVIO AO KINDLE: SUCESSO",
        "STATUS FINAL: SUCESSO",
    ]
    ordem = ["Tempo do atendimento", "Início/fim", "Tempo do núcleo", "Fanfarra/música", "HTML:",
             "PDF:", "SHA-256", "Imagens", "Páginas/", "Set list/", "Fingerprint/", "Drive/Kindle",
             "Tempos por etapa", "Pendências"]  # fmt: skip
    posicoes = [next(i for i, linha in enumerate(linhas) if linha.startswith(o)) for o in ordem]
    assert posicoes == sorted(posicoes)
    com_pedido = montar(dados, _cronometro_completo(etapas, pedido=True), etapas)
    assert com_pedido.splitlines()[0].startswith("Tempo percebido pelo usuário: 5.0 s")


def test_status_final_exige_etapas_obrigatorias():
    """REL-05."""
    dados = {"processamento_ok": True, "kindle": {"status": "SUCESSO"}}
    c = _cronometro_completo(["pdf"])
    estados = estados_finais(dados, c, ["pdf", "promocao"])
    assert estados["status_final"] == "FALHA" and "promocao" in estados["motivos_falha"][0]
    bloqueado = estados_finais({**dados, "kindle": {"status": "BLOQUEADO"}}, c, ["pdf"])
    assert bloqueado["envio_kindle"] == "BLOQUEADO" and bloqueado["status_final"] == "FALHA"
    sem_envio = estados_finais({**dados, "kindle": {"status": "NAO_SOLICITADO"}}, c, ["pdf"])
    assert sem_envio["envio_kindle"] == "NAO_SOLICITADO" and sem_envio["status_final"] == "SUCESSO"


def test_registro_historico_completo_mesmo_em_falha():
    """HIS-02."""
    c = _cronometro_completo(["pdf"])
    dados = {"erro": "pdf: gate estrutural", "fanfarra": "Skaravana"}
    reg = registro_historico(dados, c, ["pdf"], "0.5.0", "f" * 64)
    assert reg["erro"] == "pdf: gate estrutural" and reg["estados"]["status_final"] == "FALHA"
    assert {"tempo", "versao_codigo", "sha_codigo", "paginas_inspecionadas", "escopo"} <= set(reg)
    assert reg["tempo"]["workflow_started_at_utc"].endswith("+00:00")
