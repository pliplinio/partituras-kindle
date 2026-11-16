"""Fixtures: HTMLs canônicos sintéticos no mesmo formato dos repertórios reais."""

from __future__ import annotations

import base64
import io
import os
from pathlib import Path

import pytest
from PIL import Image

from partituras.dominio.nomes import slug
from partituras.html import render
from partituras.html.documento import Documento
from partituras.html.edicao import reconstruir_indice, reconstruir_setlist


def png(cor: tuple[int, int, int] = (255, 255, 255), tamanho=(88, 65), tinta_topo=None) -> bytes:
    """PNG pequeno; `tinta_topo=(x0, x1)` pinta de preto a faixa do cabeçalho nessa largura (%)."""
    img = Image.new("RGB", tamanho, cor)
    if tinta_topo:
        w, h = tamanho
        x0, x1 = int(w * tinta_topo[0] / 100), int(w * tinta_topo[1] / 100)
        y0, y1 = round(h * 17 / 650), round(h * 35 / 650)
        for x in range(x0, x1):
            for y in range(y0, max(y0 + 1, y1)):
                img.putpixel((x, y), (0, 0, 0))
    saida = io.BytesIO()
    img.save(saida, format="PNG")
    return saida.getvalue()


def uri(dados: bytes) -> str:
    return "data:image/png;base64," + base64.b64encode(dados).decode("ascii")


# Tamanho de página do template de teste da Fanfateste, mais o mínimo do overlay.
CSS = (
    "@page{size:880px 650px;margin:0}html,body{margin:0;padding:0;background:#fff}"
    "body{font-family:Arial,sans-serif}"
    ".slide{width:880px;height:650px;box-sizing:border-box;overflow:hidden;"
    "break-after:page;page-break-after:always}"
    ".slide:last-child{break-after:auto;page-break-after:auto}"
    ".setlist-native,.index-native{padding:40px 48px}"
    ".score-image{width:100%;height:100%}"
    ".score-overlay-v2{position:relative}"
    ".score-overlay-v2 .score-image{position:absolute;inset:0}"
    ".score-header-overlay{position:absolute;top:17px;left:0;right:0;height:18px}"
    ".score-header-overlay a{position:absolute;transform:translateX(-50%);font-size:17px}"
)

MUSICAS_PADRAO = [
    ("Coisa Nº 5", 1),
    ("Garden of Love", 2),
    ("Ska Paralamas", 1),
    ("Skaravan", 1),
    ("Simmer Down", 1),
]


def construir_html(
    musicas=MUSICAS_PADRAO,
    setlist: list[str] | None = ("Garden of Love", "Ska Paralamas"),
    com_indice: bool = True,
    overlay: bool = False,
    auxiliar: bool = False,
    quebra: str = "\n",
    versao: int | None = 3,
) -> bytes:
    """Monta um HTML canônico pelo mesmo caminho de geração do código, com índice e set list."""
    secoes: list[str] = []
    n = 3
    primeira: dict[str, str] = {}
    destino = "#setlist" if setlist is not None else "#index"
    for i, (titulo, partes) in enumerate(musicas):
        grupo = slug(titulo)
        for parte in range(1, partes + 1):
            id_ = f"slide-{n}"
            n += 1
            primeira.setdefault(grupo, id_)
            imagem = uri(png((250 - i * 10, 250, 250)))
            if overlay:
                secoes.append(
                    render.secao_overlay(
                        titulo, grupo, parte, partes, id_, imagem, destino, 50.0, 91.5
                    )
                )
            else:
                secoes.append(
                    render.secao_raw_score(
                        titulo, grupo, parte, partes, id_, imagem, destino, False
                    )
                )
    if auxiliar:
        secoes.append(
            f'<section class="slide auxiliary-native" id="slide-{n}" data-role="auxiliary">'
            f'<img alt="aux" src="{uri(png())}"/></section>'
        )
    abertura = []
    if setlist is not None:
        abertura.append(
            '<section class="slide setlist-native" id="setlist" data-role="setlist">'
            '<h1>Set list</h1><ol class="setlist-list"></ol></section>'
        )
    if com_indice:
        abertura.append(
            '<section class="slide index-native" id="index" data-role="index"></section>'
        )
    metas = '<meta charset="utf-8"/>'
    if versao is not None:
        metas += f'<meta content="{versao:02d}" name="partituras-template-version"/>'
    if overlay:
        metas += '<meta content="score-overlay-header-v2" name="partituras-score-template"/>'
    texto = (
        f"<!DOCTYPE html>\n<html><head>{metas}\n<style>\n{CSS}\n"
        "/* score-native-layout-v1 */\n"
        ".score-native{display:flex;flex-direction:column}\n</style>\n</head>\n"
        "<body><main>\n" + "\n".join(abertura + secoes) + "\n</main></body></html>\n"
    )
    doc = Documento(texto)
    if setlist is not None:
        doc, _ = reconstruir_setlist(doc, list(setlist))
    doc = reconstruir_indice(doc)
    return doc.para_bytes().replace(b"\n", quebra.encode())


@pytest.fixture
def html_basico() -> Documento:
    return Documento.de_bytes(construir_html())


@pytest.fixture
def imagens(tmp_path: Path):
    def criar(*cores: tuple[int, int, int]) -> tuple[Path, ...]:
        caminhos = []
        for i, cor in enumerate(cores):
            p = tmp_path / f"parte{i + 1}.png"
            p.write_bytes(png(cor))
            caminhos.append(p)
        return tuple(caminhos)

    return criar


PASTA_REAIS = os.environ.get("PARTITURAS_HTML_REAIS")


def html_real(nome: str) -> bytes:
    """HTML real da pasta indicada em PARTITURAS_HTML_REAIS; o teste é pulado sem ela."""
    if not PASTA_REAIS:
        pytest.skip("PARTITURAS_HTML_REAIS não definida")
    caminho = Path(PASTA_REAIS) / nome
    if not caminho.is_file():
        pytest.skip(f"{caminho} não encontrado")
    return caminho.read_bytes()
