"""Nomes de arquivo e versões de template e de PDF.

HTML-01, HTML-05, HTML-06, HTML-10, PDF-01 a PDF-04, ARQ-03.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from enum import StrEnum

from partituras.dominio.erros import Bloqueio, Inconsistencia

_PDF = re.compile(r"^(?P<nome>.+?)_v(?P<versao>\d+)\.pdf$", re.I)
_HTML_LEGADO = re.compile(r"^(?P<nome>.+?)_v(?P<versao>\d+)\.html$", re.I)


class TipoAlteracao(StrEnum):
    CONTEUDO = "conteudo"
    TEMPLATE = "template"


def nome_html(fanfarra: str) -> str:
    """Nome fixo do HTML canônico, sem sufixo de versão (HTML-01)."""
    if not fanfarra or "/" in fanfarra or "\\" in fanfarra:
        raise Inconsistencia(f"nome de fanfarra inválido: {fanfarra!r}")
    return f"{fanfarra}.html"


def nome_html_arquivado(fanfarra: str, versao_template: int) -> str:
    """Onde a versão anterior é guardada antes de uma mudança de template (HTML-06)."""
    return f"old/{fanfarra}_v{versao_template:02d}.html"


def nome_pdf(fanfarra: str, versao: int) -> str:
    """`<NOME>_vNN.pdf`, com underscore e pelo menos dois dígitos (PDF-01)."""
    if versao < 1:
        raise Inconsistencia(f"versão de PDF inválida: {versao}")
    return f"{fanfarra}_v{versao:02d}.pdf"


def versao_do_pdf(nome_arquivo: str, fanfarra: str) -> int | None:
    m = _PDF.match(nome_arquivo)
    if not m or m.group("nome").casefold() != fanfarra.casefold():
        return None
    return int(m.group("versao"))


def proxima_versao_pdf(
    fanfarra: str,
    versao_template: int,
    arquivos_existentes: Iterable[str],
    versao_minima: int = 0,
) -> int:
    """max(template, PDFs existentes, versão mínima) + 1, pulando nomes ocupados (PDF-02).

    `versao_minima` continua a numeração da versão ChatGPT (PDF-03).
    """
    existentes = set(arquivos_existentes)
    versoes = [v for a in existentes if (v := versao_do_pdf(a, fanfarra)) is not None]
    versao = max([versao_template, versao_minima, *versoes]) + 1
    ocupados = {a.casefold() for a in existentes}
    while nome_pdf(fanfarra, versao).casefold() in ocupados:
        versao += 1
    return versao


def garantir_nao_sobrescreve(nome_arquivo: str, arquivos_existentes: Iterable[str]) -> None:
    """Nenhum PDF existente é sobrescrito (PDF-04)."""
    if nome_arquivo.casefold() in {a.casefold() for a in arquivos_existentes}:
        raise Bloqueio(f"{nome_arquivo} já existe; PDF nunca é sobrescrito")


def nova_versao_template(versao_atual: int) -> int:
    """Versão vigente + 1 (HTML-05)."""
    return versao_atual + 1


def conferir_versao_template(antes: int, depois: int, tipo: TipoAlteracao) -> None:
    """Conteúdo mantém a versão; template incrementa exatamente uma (HTML-10)."""
    if tipo is TipoAlteracao.CONTEUDO and depois != antes:
        raise Inconsistencia(
            f"alteração de conteúdo não pode mudar a versão de template ({antes} → {depois})"
        )
    if tipo is TipoAlteracao.TEMPLATE and depois != nova_versao_template(antes):
        raise Inconsistencia(
            f"alteração de template deve ir de v{antes:02d} para v{antes + 1:02d}, "
            f"não v{depois:02d}"
        )


def selecionar_fonte(fanfarra: str, arquivos: Iterable[str]) -> str:
    """Escolhe o HTML canônico da fanfarra; PPTX e Slides nunca são fonte (ARQ-03)."""
    alvo = nome_html(fanfarra).casefold()
    for arquivo in arquivos:
        if arquivo.casefold() == alvo:
            return arquivo
    legados = sorted(
        a for a in arquivos if (m := _HTML_LEGADO.match(a)) and m.group("nome") == fanfarra
    )
    detalhe = f" Há HTMLs no formato antigo: {legados}." if legados else ""
    raise Bloqueio(f"HTML canônico {nome_html(fanfarra)} não encontrado.{detalhe}")
