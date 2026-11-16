"""Conversão HTML → PDF cru com o conversor oficial (PDF-06).

Chromium headless na versão fixada pelo Playwright do `pyproject.toml`. O papel
é fixo em 880 px × 487,92 pt, a geometria dos PDFs aprovados (v13 e v14 do
Skaravana). Cada `section.slide` deve virar exatamente uma página.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Protocol

import pymupdf

from partituras.dominio.erros import Inconsistencia

LARGURA_PAPEL = "880px"
ALTURA_PAPEL = "650.56px"  # 487,92 pt
LARGURA_PT = 660.0
ALTURA_PT = 487.92


class Conversor(Protocol):
    """Contrato: escreve o PDF cru em `destino` ou levanta exceção."""

    nome: str

    def converter(self, html: bytes, destino: Path) -> None: ...


class ChromiumConversor:
    nome = "chromium-playwright"

    def __init__(self, tempo_limite_ms: int = 180_000):
        self.tempo_limite_ms = tempo_limite_ms
        self.versao: str | None = None

    def converter(self, html: bytes, destino: Path) -> None:
        from playwright.sync_api import sync_playwright

        with tempfile.TemporaryDirectory() as pasta:
            arquivo = Path(pasta) / "entrada.html"
            arquivo.write_bytes(html)
            with sync_playwright() as p:
                navegador = p.chromium.launch(args=["--no-sandbox"])
                try:
                    self.versao = navegador.version
                    pagina = navegador.new_page(viewport={"width": 880, "height": 651})
                    pagina.goto(arquivo.as_uri(), wait_until="load", timeout=self.tempo_limite_ms)
                    pagina.emulate_media(media="print")
                    pagina.pdf(
                        path=str(destino),
                        width=LARGURA_PAPEL,
                        height=ALTURA_PAPEL,
                        print_background=True,
                        margin={"top": "0", "right": "0", "bottom": "0", "left": "0"},
                    )
                finally:
                    navegador.close()


def conferir_pdf_cru(caminho: Path, paginas_esperadas: int) -> None:
    """Uma página por `section.slide`, com a geometria fixa (PDF-06)."""
    with pymupdf.open(caminho) as doc:
        if len(doc) != paginas_esperadas:
            raise Inconsistencia(
                f"PDF cru com {len(doc)} páginas; o HTML tem {paginas_esperadas} slides"
            )
        for i, pagina in enumerate(doc):
            w, h = pagina.rect.width, pagina.rect.height
            if abs(w - LARGURA_PT) > 0.5 or abs(h - ALTURA_PT) > 0.5:
                raise Inconsistencia(
                    f"página crua {i + 1} com {w:.2f}×{h:.2f} pt; esperado "
                    f"{LARGURA_PT}×{ALTURA_PT} pt"
                )
