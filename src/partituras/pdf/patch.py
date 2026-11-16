"""Patch incremental: troca só a imagem das páginas da música alterada (PDF-11, PDF-12).

Reaproveita o PDF anterior aprovado. A imagem é trocada no próprio objeto do
PDF, mantendo posição e tamanho; o texto do cabeçalho por cima fica intacto
(inclusive no template overlay, em que a imagem ocupa a página inteira).
Qualquer incompatibilidade levanta `PatchIncompativel`, e o chamador cai para
a geração integral registrando o motivo.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import pymupdf

from partituras.dominio.erros import Bloqueio
from partituras.dominio.nomes import normalizar
from partituras.dominio.plano import Plano
from partituras.pdf.fingerprint import sha256_arquivo

METODO = "incremental_pdf_patch"


class PatchIncompativel(Exception):
    """O patch não se aplica; usar geração integral."""


@dataclass
class RelatorioPatch:
    metodo: str = METODO
    paginas: list[int] = field(default_factory=list)
    ocorrencias: int = 0


def _imagem_principal(pagina: pymupdf.Page) -> int:
    """xref da maior imagem da página: a partitura."""
    melhor, area = None, 0.0
    for info in pagina.get_images(full=True):
        for rect in pagina.get_image_rects(info[0]):
            if rect.get_area() > area:
                melhor, area = info[0], rect.get_area()
    if melhor is None:
        raise PatchIncompativel(f"página {pagina.number + 1} sem imagem de partitura")
    return melhor


def aplicar(
    anterior: Path,
    sha256_aprovado: str,
    plano: Plano,
    grupo: str,
    imagens: list[bytes],
    saida: Path,
) -> RelatorioPatch:
    if sha256_arquivo(anterior) != sha256_aprovado.lower():
        raise Bloqueio("PDF anterior não corresponde ao SHA-256 aprovado; patch bloqueado")
    alvo = [p for p in plano.paginas_partitura if p.grupo == grupo]
    if not alvo:
        raise PatchIncompativel(f"grupo {grupo} não está no plano")
    if any(p.total != len(imagens) for p in alvo):
        raise PatchIncompativel(f"quantidade de partes mudou ({alvo[0].total} → {len(imagens)})")
    relatorio = RelatorioPatch(ocorrencias=max(p.ocorrencia for p in alvo))
    with pymupdf.open(anterior) as doc:
        if len(doc) != len(plano.paginas):
            raise PatchIncompativel(
                f"PDF anterior com {len(doc)} páginas; o plano atual tem {len(plano.paginas)}"
            )
        xrefs_alvo: dict[int, int] = {}
        for p in alvo:
            pagina = doc[p.pagina]
            if normalizar(p.musica) not in normalizar(pagina.get_text("text") or ""):
                raise PatchIncompativel(f'página {p.pagina + 1} do PDF anterior não é "{p.musica}"')
            xrefs_alvo[p.pagina] = _imagem_principal(pagina)
        paginas_alvo = set(xrefs_alvo)
        for numero, pagina in enumerate(doc):
            if numero in paginas_alvo:
                continue
            compartilhadas = {i[0] for i in pagina.get_images(full=True)} & set(xrefs_alvo.values())
            if compartilhadas:
                raise PatchIncompativel(f"imagem compartilhada com a página {numero + 1}")
        trocadas: set[int] = set()
        for p in alvo:
            xref = xrefs_alvo[p.pagina]
            if xref not in trocadas:
                doc[p.pagina].replace_image(xref, stream=imagens[p.parte - 1])
                trocadas.add(xref)
            relatorio.paginas.append(p.pagina + 1)
        # Os links do PDF aprovado já são GoTo na camada de anotações (LNK-02) e
        # podem ser objetos compartilhados entre páginas; apagá-los numa página
        # removeria o link das outras. O patch não mexe em links; o gate confere.
        saida.parent.mkdir(parents=True, exist_ok=True)
        doc.save(saida, garbage=4, deflate=True, clean=True)
    return relatorio
