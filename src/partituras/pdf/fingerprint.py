"""Fingerprint de páginas e reaproveitamento de inspeção visual (INS-01 a INS-04, INS-08, INS-09).

Algoritmo e formato idênticos aos da versão anterior
(`partituras-pdf-page-manifest-v1`), para que manifestos de PDFs já aprovados
continuem servindo de referência.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

import pymupdf

from partituras.dominio.erros import Bloqueio, Inconsistencia

SCHEMA_MANIFESTO = "partituras-pdf-page-manifest-v1"
DPI = 110


def sha256_arquivo(caminho: Path) -> str:
    return hashlib.sha256(Path(caminho).read_bytes()).hexdigest()


def _texto_normalizado(pagina: pymupdf.Page) -> str:
    return "\n".join(
        linha.strip() for linha in (pagina.get_text("text") or "").splitlines() if linha.strip()
    )


def _links(pagina: pymupdf.Page) -> dict:
    itens = []
    for link in pagina.get_links():
        rect = link.get("from")
        para = link.get("to")
        try:
            para_valor = (
                [round(float(para.x), 3), round(float(para.y), 3)] if para is not None else None
            )
        except AttributeError:
            para_valor = str(para)
        itens.append(
            {
                "kind": link.get("kind"),
                "page": link.get("page"),
                "from": [round(float(x), 3) for x in tuple(rect)] if rect is not None else None,
                "to": para_valor,
                "uri": link.get("uri"),
                "file": link.get("file"),
            }
        )
    dados = json.dumps(itens, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return {"links_sha256": hashlib.sha256(dados.encode()).hexdigest(), "links_count": len(itens)}


def fingerprint_pagina(pagina: pymupdf.Page, dpi: int = DPI) -> dict:
    pix = pagina.get_pixmap(matrix=pymupdf.Matrix(dpi / 72.0, dpi / 72.0), alpha=False, annots=True)
    h = hashlib.sha256()
    h.update(f"{pix.width}x{pix.height}x{pix.n}|".encode("ascii"))
    h.update(pix.samples)
    texto = _texto_normalizado(pagina)
    return {
        "visual_sha256": h.hexdigest(),
        "text_sha256": hashlib.sha256(texto.encode("utf-8")).hexdigest(),
        "render_width": int(pix.width),
        "render_height": int(pix.height),
        "channels": int(pix.n),
        "page_width": round(float(pagina.rect.width), 4),
        "page_height": round(float(pagina.rect.height), 4),
    }


def manifesto(pdf: Path, dpi: int = DPI) -> dict:
    """Fingerprint de 100% das páginas (INS-01)."""
    with pymupdf.open(pdf) as doc:
        paginas = [
            {"pagina": i + 1, **fingerprint_pagina(p, dpi), **_links(p)} for i, p in enumerate(doc)
        ]
        total = len(doc)
    return {
        "schema": SCHEMA_MANIFESTO,
        "pdf": str(pdf),
        "pdf_sha256": sha256_arquivo(pdf),
        "dpi": dpi,
        "total_paginas": total,
        "paginas": paginas,
    }


def carregar_manifesto_aprovado(dados: dict, sha256_aprovado: str, dpi: int = DPI) -> dict:
    """Aceita um manifesto anterior só se schema, DPI e SHA-256 conferem (INS-02, INS-09).

    Aceita também o JSON de validação completo da versão anterior, que guarda o
    manifesto em `delta.candidate_manifest`.
    """
    if dados.get("schema") != SCHEMA_MANIFESTO:
        aninhado = (dados.get("delta") or {}).get("candidate_manifest")
        if not aninhado:
            raise Inconsistencia("manifesto anterior incompatível")
        dados = aninhado
        if dados.get("schema") != SCHEMA_MANIFESTO:
            raise Inconsistencia("manifesto anterior incompatível")
    aprovado = (sha256_aprovado or "").strip().lower()
    if not re.fullmatch(r"[0-9a-f]{64}", aprovado):
        raise Inconsistencia("SHA-256 aprovado inválido")
    if int(dados.get("dpi") or 0) != dpi:
        raise Inconsistencia(f"manifesto anterior em {dados.get('dpi')} DPI; esperado {dpi}")
    if str(dados.get("pdf_sha256", "")).lower() != aprovado:
        raise Bloqueio("manifesto anterior não corresponde ao SHA-256 aprovado; reuso bloqueado")
    return dados


def _chave(p: dict) -> tuple:
    return (
        p.get("visual_sha256"),
        p.get("text_sha256"),
        p.get("render_width"),
        p.get("render_height"),
        p.get("page_width"),
        p.get("page_height"),
    )


@dataclass
class Delta:
    reutilizaveis: dict[int, list[int]] = field(default_factory=dict)
    para_inspecao: dict[int, str] = field(default_factory=dict)
    links_mudaram: list[int] = field(default_factory=list)
    integral: bool = False
    motivo_integral: str | None = None

    def como_dict(self) -> dict:
        return {
            "paginas_com_inspecao_visual_reutilizavel": sorted(self.reutilizaveis),
            "paginas_para_inspecao_visual": sorted(self.para_inspecao),
            "paginas_reutilizadas_com_links_diferentes": self.links_mudaram,
            "inspecao_integral": self.integral,
            "motivo_inspecao_integral": self.motivo_integral,
            "detalhes_reuso": {str(k): v for k, v in sorted(self.reutilizaveis.items())},
            "detalhes_inspecao": {str(k): v for k, v in sorted(self.para_inspecao.items())},
        }


def delta(
    candidato: dict,
    anterior: dict | None,
    mudanca_template: bool = False,
    mudanca_renderizador: bool = False,
    pedido_integral: bool = False,
) -> Delta:
    """Separa páginas reutilizáveis das que exigem inspeção (INS-02 a INS-04).

    A correspondência independe da posição da página. Mudança só de links não
    impede o reuso, mas é registrada (INS-03).
    """
    resultado = Delta()
    motivo = None
    if mudanca_template:
        motivo = "mudança de template"
    elif mudanca_renderizador:
        motivo = "mudança do mecanismo de renderização"
    elif pedido_integral:
        motivo = "pedido do usuário"
    elif anterior is None:
        motivo = "sem PDF anterior aprovado verificável"
    if motivo:
        resultado.integral, resultado.motivo_integral = True, motivo
        resultado.para_inspecao = {p["pagina"]: motivo for p in candidato["paginas"]}
        return resultado

    if candidato.get("pdf_sha256") and candidato.get("pdf_sha256") == anterior.get("pdf_sha256"):
        # Mesmos bytes (só o nome mudou): toda a inspeção é reaproveitada (FLX-05).
        resultado.reutilizaveis = {p["pagina"]: [p["pagina"]] for p in candidato["paginas"]}
        return resultado

    tamanhos_anteriores = {(p["page_width"], p["page_height"]) for p in anterior["paginas"]}
    tamanhos_candidato = {(p["page_width"], p["page_height"]) for p in candidato["paginas"]}
    if not tamanhos_candidato <= tamanhos_anteriores:
        motivo = "mudança de tamanho de página"
        resultado.integral, resultado.motivo_integral = True, motivo
        resultado.para_inspecao = {p["pagina"]: motivo for p in candidato["paginas"]}
        return resultado

    por_chave: dict[tuple, list[dict]] = defaultdict(list)
    for p in anterior["paginas"]:
        por_chave[_chave(p)].append(p)
    for p in candidato["paginas"]:
        iguais = por_chave.get(_chave(p), [])
        if not iguais:
            resultado.para_inspecao[p["pagina"]] = "sem correspondência exata na versão aprovada"
            continue
        resultado.reutilizaveis[p["pagina"]] = [q["pagina"] for q in iguais]
        if not any(q.get("links_sha256") == p.get("links_sha256") for q in iguais):
            resultado.links_mudaram.append(p["pagina"])
    if not resultado.reutilizaveis:
        resultado.integral, resultado.motivo_integral = True, "nenhuma página corresponde"
    return resultado


def manifesto_aprovado(
    manifesto_candidato: dict,
    delta_: Delta,
    inspecionadas: list[int],
    origem_reuso: str | None,
) -> dict:
    """Manifesto do PDF aprovado, guardado para a próxima versão (INS-08)."""
    return {
        **manifesto_candidato,
        "paginas_inspecionadas": sorted(inspecionadas),
        "paginas_reutilizadas": sorted(delta_.reutilizaveis),
        "origem_reuso": origem_reuso,
        "detalhes_reuso": {str(k): v for k, v in sorted(delta_.reutilizaveis.items())},
    }
