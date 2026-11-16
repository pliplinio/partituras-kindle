"""Posição horizontal do título e do `ABC` em páginas overlay novas (LAY-06).

Escolhe, na faixa aprovada de 17 a 35 px (em 880×650), as posições com menos
tinta. Não altera nenhum pixel da imagem: só decide onde ficam os links
transparentes. A inspeção visual continua obrigatória (LAY-07).
"""

from __future__ import annotations

import io

from PIL import Image, ImageChops

TOPO_PX = 17
ALTURA_PX = 18
ALTURA_REFERENCIA = 650
LARGURA_REFERENCIA = 880
CENTROS_TITULO = (50.0, 45.0, 55.0, 40.0, 60.0, 35.0, 65.0, 30.0, 70.0, 25.0, 75.0, 20.0)
CENTROS_ABC = (91.5, 94.0, 88.5, 85.0, 81.5, 78.0, 74.5)
PADRAO = (50.0, 91.5)


def _largura_titulo_pct(rotulo: str) -> float:
    return min(48.0, max(14.0, (len(rotulo) * 9.5 + 8) / LARGURA_REFERENCIA * 100))


def posicoes(imagem: bytes, rotulo: str) -> tuple[float, float]:
    """Retorna (centro do título, centro do `ABC`) em porcentagem da largura."""
    try:
        img = Image.open(io.BytesIO(imagem)).convert("RGB")
    except OSError:
        return PADRAO
    w, h = img.size
    if w <= 0 or h <= 0:
        return PADRAO
    y0 = max(0, min(h - 1, round(h * TOPO_PX / ALTURA_REFERENCIA)))
    y1 = max(y0 + 1, min(h, round(h * (TOPO_PX + ALTURA_PX) / ALTURA_REFERENCIA)))
    # Pixel com tinta: o menor dos canais RGB abaixo de 215 (mesmo critério da versão anterior).
    r, g, b = img.crop((0, y0, w, y1)).split()
    faixa = ImageChops.darker(r, ImageChops.darker(g, b)).point(lambda v: 255 if v < 215 else 0)

    def tinta(centro_pct: float, largura_pct: float) -> int:
        cx = w * centro_pct / 100.0
        meia = w * largura_pct / 200.0
        x0, x1 = max(0, int(cx - meia)), min(w, int(cx + meia))
        if x1 <= x0:
            return 0
        return faixa.crop((x0, 0, x1, y1 - y0)).histogram()[255]

    largura = _largura_titulo_pct(rotulo)
    titulo = min(CENTROS_TITULO, key=lambda c: (tinta(c, largura), abs(c - 50.0)))
    abc = min(CENTROS_ABC, key=lambda c: (tinta(c, 5.5), abs(c - 91.5)))
    return round(titulo, 4), round(abc, 4)
