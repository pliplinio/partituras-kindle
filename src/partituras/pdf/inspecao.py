"""Gate nominal, pré-validação visual, renderização seletiva e registro de inspeção.

VAL-05, VAL-08, INS-05, INS-06, INS-07.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

import pymupdf
from PIL import Image

from partituras.dominio.erros import Bloqueio, Inconsistencia
from partituras.dominio.modelos import Papel
from partituras.dominio.nomes import normalizar
from partituras.dominio.plano import Plano
from partituras.pdf.conversao import ALTURA_PT, LARGURA_PT
from partituras.pdf.fingerprint import DPI, Delta, sha256_arquivo

# --- Gate nominal -----------------------------------------------------------------------------


def gate_nominal(pdf: Path, plano: Plano, grupo: str) -> dict:
    """Título e todas as partes 1..N da música em cada ocorrência, antes da inspeção (VAL-05)."""
    alvo = [p for p in plano.paginas_partitura if p.grupo == grupo]
    if not alvo:
        raise Inconsistencia(f"música {grupo} ausente do plano")
    encontradas = []
    with pymupdf.open(pdf) as doc:
        for p in alvo:
            texto = doc[p.pagina].get_text("text") or ""
            titulo = normalizar(p.musica) in normalizar(texto)
            parte = p.total == 1 or bool(
                re.search(rf"\(\s*{p.parte}\s*de\s*{p.total}\s*\)", texto, re.I)
            )
            encontradas.append(
                {"pagina": p.pagina + 1, "parte": p.parte, "ocorrencia": p.ocorrencia,
                 "titulo_ok": titulo, "parte_ok": parte}
            )  # fmt: skip
    partes = sorted({e["parte"] for e in encontradas if e["titulo_ok"] and e["parte_ok"]})
    resultado = {
        "musica": alvo[0].musica,
        "pdf_sha256": sha256_arquivo(pdf),
        "partes_esperadas": alvo[0].total,
        "partes_encontradas": partes,
        "paginas": encontradas,
        "presenca_ok": partes == list(range(1, alvo[0].total + 1))
        and all(e["titulo_ok"] and e["parte_ok"] for e in encontradas),
    }
    if not resultado["presenca_ok"]:
        raise Inconsistencia(f'gate nominal: "{alvo[0].musica}" não confirmada no PDF')
    return resultado


# --- Pré-validação visual ---------------------------------------------------------------------

DPI_PREVIA = 36
BRANCO = 245


@dataclass
class Alerta:
    pagina: int
    tipo: str
    detalhe: str = ""


def _tinta(pagina: pymupdf.Page) -> float:
    pix = pagina.get_pixmap(dpi=DPI_PREVIA, colorspace=pymupdf.csGRAY, alpha=False)
    amostras = pix.samples
    escuros = sum(1 for v in amostras if v < BRANCO)
    return escuros / max(1, len(amostras))


def pre_validar(pdf: Path, plano: Plano) -> list[Alerta]:
    """Sinaliza páginas que merecem atenção na inspeção; não substitui a inspeção (VAL-08)."""
    alertas: list[Alerta] = []
    proporcao = LARGURA_PT / ALTURA_PT
    with pymupdf.open(pdf) as doc:
        for p in plano.paginas:
            pagina = doc[p.pagina]
            numero = p.pagina + 1
            r = pagina.rect
            limite = pymupdf.Rect(r.x0 - 1, r.y0 - 1, r.x1 + 1, r.y1 + 1)
            if abs(r.width / r.height - proporcao) > 0.01 * proporcao:
                detalhe = f"{r.width:.1f}×{r.height:.1f}"
                alertas.append(Alerta(numero, "proporcao_inesperada", detalhe))
            tinta = _tinta(pagina)
            if tinta < 0.002:
                alertas.append(Alerta(numero, "pagina_vazia"))
            elif p.papel is Papel.PARTITURA and tinta < 0.03:
                alertas.append(Alerta(numero, "pouco_conteudo", f"{tinta:.1%} de tinta"))
            if p.papel is Papel.PARTITURA:
                imagens = pagina.get_images(full=True)
                if not imagens:
                    alertas.append(Alerta(numero, "imagem_ausente"))
                for info in imagens:
                    for rect in pagina.get_image_rects(info[0]):
                        if not limite.contains(rect):
                            alertas.append(Alerta(numero, "fora_da_pagina", "imagem"))
            for bloco in pagina.get_text("blocks"):
                if not limite.contains(pymupdf.Rect(bloco[:4])):
                    alertas.append(Alerta(numero, "fora_da_pagina", "texto"))
    return alertas


# --- Renderização seletiva --------------------------------------------------------------------


def renderizar(pdf: Path, paginas: Sequence[int], pasta: Path, dpi: int = DPI) -> list[Path]:
    """Só as páginas pedidas, numeradas a partir de 1 (INS-05)."""
    pasta.mkdir(parents=True, exist_ok=True)
    saidas = []
    with pymupdf.open(pdf) as doc:
        for numero in sorted(set(paginas)):
            if not 1 <= numero <= len(doc):
                raise Inconsistencia(f"página {numero} fora do PDF")
            pix = doc[numero - 1].get_pixmap(
                matrix=pymupdf.Matrix(dpi / 72.0, dpi / 72.0), alpha=False, annots=True
            )
            destino = pasta / f"pagina-{numero:03d}.png"
            pix.save(destino)
            saidas.append(destino)
    return saidas


def folhas_de_contato(imagens: Sequence[Path], pasta: Path, por_folha: int = 6) -> list[Path]:
    """Até 6 páginas por folha, em 2 colunas (INS-05)."""
    if not 1 <= por_folha <= 6:
        raise ValueError("folha de contato tem de 1 a 6 páginas")
    folhas = []
    for i in range(0, len(imagens), por_folha):
        grupo = [Image.open(p) for p in imagens[i : i + por_folha]]
        w = max(im.width for im in grupo)
        h = max(im.height for im in grupo)
        linhas = (len(grupo) + 1) // 2
        folha = Image.new("RGB", (w * 2 + 10, h * linhas + 10 * (linhas - 1)), "gray")
        for j, im in enumerate(grupo):
            folha.paste(im, ((j % 2) * (w + 10), (j // 2) * (h + 10)))
        destino = pasta / f"folha-{i // por_folha + 1:02d}.png"
        folha.save(destino)
        folhas.append(destino)
    return folhas


# --- Registro de inspeção ---------------------------------------------------------------------

CHECKLIST = (
    "página em branco",
    "cortes",
    "conteúdo fora da página",
    "deformações",
    "baixa resolução",
    "ilegibilidade",
    "orientação",
    "duplicações",
    "páginas ausentes",
)


# Cinco itens extras do template score-overlay-header-v2 (LAY-07).
CHECKLIST_OVERLAY = (
    "imagem sem corte ou redução indevida",
    "título legível sem sobreposição",
    "sem resíduo do cabeçalho antigo",
    "ABC legível sem duplicação",
    "nenhuma cifra ou marcação apagada",
)


@dataclass
class RegistroInspecao:
    sha256: str
    exigidas: list[int]
    inspecionadas: list[int]
    reutilizadas: list[int]
    achados: dict[int, str] = field(default_factory=dict)
    checklist: tuple[str, ...] = CHECKLIST

    @property
    def aprovada(self) -> bool:
        return not self.achados


def registrar_inspecao(
    pdf: Path,
    delta: Delta,
    inspecionadas: Sequence[int],
    achados: dict[int, str] | None = None,
    overlay: bool = False,
) -> RegistroInspecao:
    """Só declara inspeção das páginas realmente inspecionadas (INS-06, INS-07).

    Exige que todas as páginas pedidas pelo delta tenham sido vistas e associa o
    registro ao SHA-256 exato do arquivo inspecionado.
    """
    exigidas = sorted(delta.para_inspecao)
    faltando = sorted(set(exigidas) - set(inspecionadas))
    if faltando:
        raise Bloqueio(f"inspeção incompleta: faltam as páginas {faltando}")
    return RegistroInspecao(
        sha256=sha256_arquivo(pdf),
        exigidas=exigidas,
        inspecionadas=sorted(set(inspecionadas)),
        reutilizadas=sorted(delta.reutilizaveis),
        achados=dict(achados or {}),
        checklist=CHECKLIST + CHECKLIST_OVERLAY if overlay else CHECKLIST,
    )
