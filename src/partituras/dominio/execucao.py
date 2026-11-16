"""Plano congelado da execução e pré-condições (FLX-01, FLX-02, PRO-06, ARQ-05).

Uma única listagem da pasta operacional decide tudo o que a execução vai usar:
HTML canônico, PDFs existentes, PDF aprovado anterior com o seu manifesto e a
próxima versão. Qualquer descoberta nova invalida o plano.
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Protocol

from partituras.dominio.erros import Bloqueio, Inconsistencia
from partituras.dominio.versoes import (
    garantir_nao_sobrescreve,
    nome_pdf,
    proxima_versao_pdf,
    selecionar_fonte,
    versao_do_pdf,
)

AUTOMACAO = "automacao"
MANIFESTOS = f"{AUTOMACAO}/manifestos"
RELATORIOS = f"{AUTOMACAO}/relatorios"
HISTORICO = f"{AUTOMACAO}/historico_execucoes.jsonl"
PASTA_PROIBIDA = "partituras_kindle"  # pasta da versão ChatGPT (ARQ-01)


@dataclass(frozen=True)
class Arquivo:
    nome: str
    id: str
    tamanho: int | None = None


class Pasta(Protocol):
    """Pasta operacional (`partituras_claude`). Nomes são relativos à raiz, com `/`."""

    local: str

    def listar(self) -> list[Arquivo]: ...

    def ler(self, nome: str) -> bytes: ...

    def gravar(self, nome: str, dados: bytes, *, novo: bool) -> Arquivo:
        """Com `novo=True`, falha se o arquivo já existir."""
        ...


def sha256(dados: bytes) -> str:
    return hashlib.sha256(dados).hexdigest()


def manifesto_de(nome_pdf_: str) -> str:
    return f"{MANIFESTOS}/{nome_pdf_.removesuffix('.pdf')}.manifest.json"


def conferir_pasta(local: str) -> None:
    """A versão Claude nunca grava na pasta da versão ChatGPT (ARQ-01)."""
    partes = local.replace("\\", "/").casefold().split("/")
    if PASTA_PROIBIDA in partes:
        raise Bloqueio(f"{local} pertence à versão ChatGPT; a versão Claude não grava lá")


@dataclass(frozen=True)
class PlanoExecucao:
    fanfarra: str
    pasta: str
    html: str
    html_id: str
    html_bytes: bytes = field(repr=False)
    html_sha256: str
    pdfs_existentes: tuple[str, ...]
    anterior_pdf: str | None
    anterior_manifesto: str | None
    versao_template: int
    versao_pdf: int
    nome_pdf: str

    def como_dict(self) -> dict:
        return {
            "fanfarra": self.fanfarra,
            "pasta": self.pasta,
            "html": self.html,
            "html_id": self.html_id,
            "html_sha256": self.html_sha256,
            "pdfs_existentes": list(self.pdfs_existentes),
            "anterior_pdf": self.anterior_pdf,
            "anterior_manifesto": self.anterior_manifesto,
            "versao_template": self.versao_template,
            "versao_pdf": self.versao_pdf,
            "nome_pdf": self.nome_pdf,
        }


def planejar_execucao(
    fanfarra: str,
    listagem: list[Arquivo],
    ler: Callable[[str], bytes],
    local: str,
    versao_template_de: Callable[[bytes], int],
    versao_minima: int = 0,
) -> PlanoExecucao:
    """Monta o plano a partir de uma única listagem (FLX-01).

    `ler` é chamado só para o HTML; os bytes ficam no plano e são reaproveitados
    pela execução inteira (FLX-02).
    """
    conferir_pasta(local)
    nomes = [a.nome for a in listagem]
    raiz = [n for n in nomes if "/" not in n]
    html = selecionar_fonte(fanfarra, raiz)
    html_arquivo = next(a for a in listagem if a.nome == html)
    dados = ler(html)
    versao_template = versao_template_de(dados)
    if versao_template is None:
        raise Inconsistencia(
            f"{html} não declara a versão de template (meta partituras-template-version, HTML-02)"
        )
    pdfs = sorted(
        (n for n in raiz if versao_do_pdf(n, fanfarra) is not None),
        key=lambda n: versao_do_pdf(n, fanfarra),
    )
    manifestos = set(nomes)
    aprovados = [p for p in pdfs if manifesto_de(p) in manifestos]
    anterior = aprovados[-1] if aprovados else None
    versao = proxima_versao_pdf(fanfarra, versao_template, raiz, versao_minima)
    final = nome_pdf(fanfarra, versao)
    garantir_nao_sobrescreve(final, raiz)
    return PlanoExecucao(
        fanfarra=fanfarra,
        pasta=local,
        html=html,
        html_id=html_arquivo.id,
        html_bytes=dados,
        html_sha256=sha256(dados),
        pdfs_existentes=tuple(pdfs),
        anterior_pdf=anterior,
        anterior_manifesto=manifesto_de(anterior) if anterior else None,
        versao_template=versao_template,
        versao_pdf=versao,
        nome_pdf=final,
    )


def conferir_plano(plano: PlanoExecucao, listagem: list[Arquivo]) -> None:
    """Uma descoberta nova exige reiniciar com novo plano (FLX-01)."""
    raiz = {a.nome for a in listagem if "/" not in a.nome}
    novos = sorted(
        n for n in raiz if versao_do_pdf(n, plano.fanfarra) and n not in plano.pdfs_existentes
    )
    if novos:
        raise Bloqueio(f"PDFs novos apareceram durante a execução ({novos}); reiniciar")


ACOES = ("gravar_html", "criar_pdf", "ler_confirmar", "enviar_kindle")


def conferir_acoes(disponiveis: set[str], sem_envio: bool = False) -> None:
    """As ações necessárias existem antes do processamento pesado (PRO-06)."""
    exigidas = [a for a in ACOES if not (sem_envio and a == "enviar_kindle")]
    faltando = [a for a in exigidas if a not in disponiveis]
    if faltando:
        raise Bloqueio(f"ações indisponíveis: {faltando}")
