"""Execução completa, passo a passo, com estado persistido (FLX, TMP, PRO, KIN, HIS, REL).

Cada passo é um comando separado porque a inspeção visual e o envio ao Kindle
acontecem fora do código. O estado fica em `<trabalho>/estado.json` (diretório
local e temporário, ARQ-04); só a promoção e a finalização gravam na pasta
operacional.

Passos: iniciar → preparar → gerar | substituir → aprovar → promover → kindle → finalizar.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from partituras.adaptadores import historico
from partituras.casos_de_uso.gerar_pdf import gerar_candidato
from partituras.casos_de_uso.promover import promover
from partituras.casos_de_uso.substituir_musica import Anterior, substituir
from partituras.dominio.erros import Bloqueio, Inconsistencia
from partituras.dominio.execucao import (
    RELATORIOS,
    Pasta,
    PlanoExecucao,
    conferir_acoes,
    conferir_plano,
    planejar_execucao,
)
from partituras.dominio.kindle import Envio, Metodo
from partituras.dominio.relatorio import estados_finais, montar, registro_historico
from partituras.dominio.setlist import ler_texto
from partituras.dominio.tempo import Cronometro
from partituras.html.documento import Documento
from partituras.html.edicao import PedidoMusica, reconstruir_setlist
from partituras.pdf.fingerprint import (
    carregar_manifesto_aprovado,
    delta,
    manifesto,
    manifesto_aprovado,
)
from partituras.pdf.inspecao import folhas_de_contato, pre_validar, registrar_inspecao, renderizar
from partituras.version import __version__

ESTADO = "estado.json"
OBRIGATORIAS = ["preparar", "pdf", "inspecao", "promocao"]
OBRIGATORIAS_COM_ENVIO = [*OBRIGATORIAS, "kindle"]


def sha_codigo() -> str:
    """SHA-256 do código-fonte do pacote, para o histórico (HIS-02)."""
    raiz = Path(__file__).resolve().parent.parent
    h = hashlib.sha256()
    for arquivo in sorted(raiz.rglob("*.py")):
        h.update(arquivo.relative_to(raiz).as_posix().encode())
        h.update(arquivo.read_bytes())
    return h.hexdigest()


@dataclass
class Estado:
    trabalho: Path
    cronometro: Cronometro
    dados: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.trabalho = Path(self.trabalho).resolve()

    @classmethod
    def abrir(cls, trabalho: Path) -> Estado:
        bruto = json.loads((trabalho / ESTADO).read_text(encoding="utf-8"))
        return cls(trabalho, Cronometro.de_dict(bruto["cronometro"]), bruto["dados"])

    def salvar(self) -> None:
        bruto = {"cronometro": self.cronometro.como_dict(), "dados": self.dados}
        tmp = self.trabalho / (ESTADO + ".tmp")
        tmp.write_text(json.dumps(bruto, ensure_ascii=False, indent=1), encoding="utf-8")
        tmp.replace(self.trabalho / ESTADO)

    @property
    def sem_envio(self) -> bool:
        return bool(self.dados.get("sem_envio"))

    def etapa(self, nome: str):
        return _Etapa(self, nome)


class _Etapa:
    """Mede a etapa e persiste o estado também em caso de erro (TMP-05)."""

    def __init__(self, estado: Estado, nome: str) -> None:
        self.estado, self.nome = estado, nome

    def __enter__(self):
        self.estado.cronometro.comecar(self.nome)
        self.estado.salvar()
        return self

    def __exit__(self, tipo, exc, tb):
        resultado = "SUCESSO" if exc is None else "FALHA"
        self.estado.cronometro.terminar(self.nome, resultado)
        if exc is not None:
            self.estado.dados["erro"] = f"{self.nome}: {exc}"
        elif str(self.estado.dados.get("erro", "")).startswith(f"{self.nome}:"):
            # A etapa foi refeita com sucesso; a tentativa falha fica nas tentativas.
            del self.estado.dados["erro"]
        self.estado.salvar()
        return False


# --- Passos ------------------------------------------------------------------------------------


def iniciar(trabalho: Path, pedido: str | None = None, sem_envio: bool = False) -> Estado:
    """TMP-01: primeiro passo, antes de qualquer leitura do Drive."""
    trabalho.mkdir(parents=True, exist_ok=True)
    if (trabalho / ESTADO).exists():
        raise Bloqueio(f"já existe uma execução em {trabalho}; o cronômetro não é reiniciado")
    recebido = datetime.fromisoformat(pedido) if pedido else None
    estado = Estado(trabalho, Cronometro.iniciar(request_received_at=recebido))
    estado.dados["sem_envio"] = sem_envio
    estado.salvar()
    return estado


def _plano(estado: Estado) -> dict:
    if "plano" not in estado.dados:
        raise Inconsistencia("execução sem plano; rode `preparar` primeiro")
    return estado.dados["plano"]


def preparar(
    estado: Estado,
    pasta: Pasta,
    fanfarra: str,
    acoes: set[str],
) -> PlanoExecucao:
    """PRO-06 e FLX-01: confere ações, lista a pasta uma vez e congela o plano."""
    with estado.etapa("preparar"):
        conferir_acoes(acoes, estado.sem_envio)
        estado.cronometro.leitura_drive()
        listagem = pasta.listar()
        estado.cronometro.contar("downloads")
        plano = planejar_execucao(
            fanfarra,
            listagem,
            pasta.ler,
            pasta.local,
            lambda b: Documento.de_bytes(b).versao_template,
        )
        (estado.trabalho / "original.html").write_bytes(plano.html_bytes)
        manifesto_anterior = None
        if plano.anterior_manifesto:
            manifesto_anterior = estado.trabalho / "anterior.manifest.json"
            manifesto_anterior.write_bytes(pasta.ler(plano.anterior_manifesto))
            estado.cronometro.contar("downloads")
        estado.dados.update(
            plano=plano.como_dict(),
            fanfarra=fanfarra,
            html=plano.html,
            html_sha256=plano.html_sha256,
            versao_template=plano.versao_template,
            anterior=plano.anterior_pdf,
        )
    return plano


def _anterior(estado: Estado) -> dict | None:
    caminho = estado.trabalho / "anterior.manifest.json"
    if not caminho.exists():
        return None
    dados = json.loads(caminho.read_text(encoding="utf-8"))
    return carregar_manifesto_aprovado(dados, dados.get("pdf_sha256", ""))


def _depois_do_candidato(estado: Estado, candidato: Path, html: bytes, d, alertas) -> None:
    estado.cronometro.contar("pdfs_candidatos")
    estado.cronometro.contar("fingerprints")
    estado.cronometro.contar("paginas_reutilizadas", len(d.reutilizaveis))
    (estado.trabalho / "candidato.html").write_bytes(html)
    estado.dados.update(
        candidato=str(candidato),
        candidato_sha256=hashlib.sha256(candidato.read_bytes()).hexdigest(),
        paginas_para_inspecao=sorted(d.para_inspecao),
        paginas_reutilizadas=sorted(d.reutilizaveis),
        delta=d.como_dict(),
        alertas=[a.__dict__ for a in alertas],
        inspecao=(
            f"{len(d.para_inspecao)} a inspecionar, {len(d.reutilizaveis)} reutilizadas"
            + (f" (integral: {d.motivo_integral})" if d.integral else "")
        ),
    )


def gerar(estado: Estado, setlist_texto: str | None = None, conversor=None) -> dict:
    """Geração integral, com novo set list opcional (PDF-05)."""
    plano = _plano(estado)
    html = (estado.trabalho / "original.html").read_bytes()
    with estado.etapa("pdf"):
        estado.dados["operacao"] = "setlist" if setlist_texto else "geracao_integral"
        if setlist_texto is not None:
            titulos = [linha.titulo for linha in ler_texto(setlist_texto)]
            doc, rel = reconstruir_setlist(Documento.de_bytes(html), titulos)
            html = doc.para_bytes()
            estado.cronometro.contar("edicoes_html")
            estado.dados["setlist"] = (
                f"{rel.itens} itens, {rel.links} links, {len(rel.ausentes)} sem partitura"
            )
        r = gerar_candidato(html, estado.trabalho, plano["nome_pdf"], conversor)
        m = manifesto(r.candidato)
        d = delta(m, _anterior(estado))
        alertas = pre_validar(r.candidato, r.plano)
        _salvar_manifesto(estado, m)
        renders = renderizar(r.candidato, sorted(d.para_inspecao), estado.trabalho / "renders")
        if renders:
            folhas_de_contato(renders, estado.trabalho / "renders")
        estado.cronometro.contar("paginas_renderizadas", len(renders))
        _depois_do_candidato(estado, r.candidato, html, d, alertas)
        estado.dados.update(
            processamento_ok=True,
            paginas=len(r.plano.paginas),
            sequencia="conforme plano",
            indice=f"{len(r.gate.indice)} entradas em {r.gate.indice_colunas} por coluna",
            retornos=f"{len(r.gate.partituras)} páginas com retorno",
            preservacao="grupos fora do set list anexados ao final",
            tempo_nucleo_s=round(sum(r.tempos.values()), 3),
        )
    return estado.dados


def substituir_musica(estado: Estado, musica: str, imagens: list[Path], pasta: Pasta) -> dict:
    """Substituição simples pelo caminho rápido (PDF-11, FLX-03)."""
    plano = _plano(estado)
    html = (estado.trabalho / "original.html").read_bytes()
    with estado.etapa("pdf"):
        estado.dados.update(operacao="substituicao_musica", musica=musica)
        anterior = None
        if plano["anterior_pdf"]:
            sha = json.loads((estado.trabalho / "anterior.manifest.json").read_text())["pdf_sha256"]
            pdf_anterior = estado.trabalho / "anterior.pdf"
            pdf_anterior.write_bytes(pasta.ler(plano["anterior_pdf"]))
            estado.cronometro.contar("downloads")
            anterior = Anterior(sha, estado.trabalho / "anterior.manifest.json", pdf_anterior)
        pedido = PedidoMusica(plano["fanfarra"], musica, tuple(imagens))
        r = substituir(html, pedido, estado.trabalho, plano["nome_pdf"], anterior)
        estado.cronometro.contar("edicoes_html")
        estado.cronometro.contar("paginas_renderizadas", len(r.renders))
        _salvar_manifesto(estado, r.manifesto)
        _depois_do_candidato(estado, r.candidato, r.html, r.delta, r.alertas)
        estado.dados.update(
            processamento_ok=True,
            metodo_pdf=r.metodo,
            motivo_integral=r.motivo_integral,
            imagens=", ".join(p.name for p in imagens),
            escopo="aprovado",
            nominal=r.nominal,
            tempo_nucleo_s=round(sum(r.tempos.values()), 3),
        )
    return estado.dados


def _salvar_manifesto(estado: Estado, m: dict) -> None:
    (estado.trabalho / "candidato.manifest.json").write_text(
        json.dumps(m, ensure_ascii=False), encoding="utf-8"
    )


def aprovar(estado: Estado, inspecionadas: list[int], achados: dict[int, str]) -> dict:
    """Registra a inspeção feita (INS-07); achados reprovam o candidato."""
    with estado.etapa("inspecao"):
        candidato = Path(estado.dados["candidato"])
        m = json.loads((estado.trabalho / "candidato.manifest.json").read_text())
        d = delta(m, _anterior(estado))
        overlay = Documento.de_bytes((estado.trabalho / "candidato.html").read_bytes()).usa_overlay
        reg = registrar_inspecao(candidato, d, inspecionadas, achados, overlay)
        if reg.sha256 != estado.dados["candidato_sha256"]:
            raise Bloqueio("o candidato mudou depois do fingerprint")
        estado.dados.update(
            inspecao_sha256=reg.sha256,
            paginas_inspecionadas=reg.inspecionadas,
            achados={str(k): v for k, v in reg.achados.items()},
            checklist_inspecao=list(reg.checklist),
        )
        if not reg.aprovada:
            estado.dados["processamento_ok"] = False
            raise Inconsistencia(f"inspeção reprovou as páginas {sorted(reg.achados)}")
        aprovado = manifesto_aprovado(m, d, reg.inspecionadas, estado.dados.get("anterior"))
        (estado.trabalho / "aprovado.manifest.json").write_text(
            json.dumps(aprovado, ensure_ascii=False), encoding="utf-8"
        )
    return estado.dados


def promover_resultado(estado: Estado, pasta: Pasta) -> dict:
    """PRO-01 a PRO-04, depois de reconferir que nada novo apareceu (FLX-01)."""
    with estado.etapa("promocao"):
        if "inspecao_sha256" not in estado.dados or estado.dados.get("achados"):
            raise Bloqueio("sem inspeção aprovada; nada é promovido")
        plano_dict = _plano(estado)
        original = (estado.trabalho / "original.html").read_bytes()
        plano = PlanoExecucao(
            **{k: v for k, v in plano_dict.items() if k != "pdfs_existentes"},
            pdfs_existentes=tuple(plano_dict["pdfs_existentes"]),
            html_bytes=original,
        )
        conferir_plano(plano, pasta.listar())
        r = promover(
            pasta,
            plano,
            (estado.trabalho / "candidato.html").read_bytes(),
            Path(estado.dados["candidato"]).read_bytes(),
            estado.dados["inspecao_sha256"],
            json.loads((estado.trabalho / "aprovado.manifest.json").read_text()),
        )
        estado.dados.update(
            promocao=r.como_dict(),
            pdf=r.pdf.nome,
            pdf_sha256=r.pdf_sha256,
            drive=f"{r.pdf.nome} gravado e conferido (ID {r.pdf.id})",
        )
    return estado.dados


def registrar_kindle(estado: Estado, metodo: str, sucesso: bool, mensagem: str = "") -> dict:
    """KIN-05: cada tentativa fica registrada."""
    if "pdf_sha256" not in estado.dados:
        raise Bloqueio("PDF não confirmado no Drive; não há o que enviar (PRO-03)")
    candidato = Path(estado.dados["candidato"])
    if hashlib.sha256(candidato.read_bytes()).hexdigest() != estado.dados["pdf_sha256"]:
        raise Bloqueio("o PDF a enviar difere do SHA-256 confirmado (PRO-02)")
    if "kindle" not in estado.cronometro.etapas:
        estado.cronometro.comecar("kindle")
    envio = Envio(estado.dados["pdf"], estado.dados["pdf_sha256"], candidato.stat().st_size)
    for t in (estado.dados.get("kindle") or {}).get("tentativas", []):
        envio.registrar(Metodo(t["metodo"]), t["sucesso"], t["mensagem"])
    envio.registrar(Metodo(metodo), sucesso, mensagem)
    estado.dados["kindle"] = envio.como_dict()
    if envio.status.value in ("SUCESSO", "BLOQUEADO"):
        estado.cronometro.terminar("kindle", envio.status.value)
    estado.salvar()
    return estado.dados


def finalizar(estado: Estado, pasta: Pasta | None) -> str:
    """Histórico e relatório, inclusive em falha (HIS-03, REL-01); o fim é o último passo."""
    obrigatorias = OBRIGATORIAS if estado.sem_envio else OBRIGATORIAS_COM_ENVIO
    if estado.sem_envio:
        estado.dados["kindle"] = {"status": "NAO_SOLICITADO"}
    for nome in obrigatorias:
        estado.cronometro.registrar_nao_executada(nome)
    for etapa in estado.cronometro.etapas.values():
        if etapa.inicio is not None and etapa.fim is None:  # etapa interrompida
            estado.cronometro.terminar(etapa.nome, "FALHA")
    estado.cronometro.finalizar()
    texto = montar(estado.dados, estado.cronometro, obrigatorias)
    registro = registro_historico(
        estado.dados, estado.cronometro, obrigatorias, __version__, sha_codigo()
    )
    estado.dados["estados"] = estados_finais(estado.dados, estado.cronometro, obrigatorias)
    estado.salvar()
    (estado.trabalho / "relatorio.md").write_text(texto + "\n", encoding="utf-8")
    if pasta is not None:
        carimbo = estado.cronometro.workflow_started_at.strftime("%Y%m%dT%H%M%SZ")
        nome = f"{RELATORIOS}/{carimbo}_{estado.dados.get('fanfarra', 'execucao')}.md"
        pasta.gravar(nome, (texto + "\n").encode("utf-8"), novo=True)
        historico.anexar(pasta, registro)
    return texto
