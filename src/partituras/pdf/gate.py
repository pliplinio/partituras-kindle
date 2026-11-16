"""Gate estrutural do PDF contra o plano derivado do HTML.

VAL-01 a VAL-03, VAL-07, LNK-05 a LNK-08.

Roda antes de qualquer inspeção visual e reprova em qualquer divergência.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import pymupdf

from partituras.dominio.erros import Inconsistencia
from partituras.dominio.indice import tamanhos_colunas
from partituras.dominio.modelos import Papel
from partituras.dominio.nomes import normalizar
from partituras.dominio.plano import Plano
from partituras.pdf.materializacao import MINIMO_SETLIST, TITULO_INDICE
from partituras.pdf.texto import (
    Linha,
    cobertura,
    destino,
    linha_exata,
    linhas,
    links_sobre,
    melhor_linha,
)

COBERTURA_MINIMA = 0.90


@dataclass
class RelatorioGate:
    paginas_esperadas: int
    paginas_reais: int = 0
    links: int = 0
    violacoes: list[str] = field(default_factory=list)
    setlist: list[dict] = field(default_factory=list)
    indice: list[dict] = field(default_factory=list)
    indice_colunas: list[int] = field(default_factory=list)
    partituras: list[dict] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.violacoes


def validar(pdf: Path, plano: Plano) -> RelatorioGate:
    """Confere o PDF e levanta `Inconsistencia` com todas as violações encontradas."""
    relatorio = RelatorioGate(paginas_esperadas=len(plano.paginas))
    try:
        doc = pymupdf.open(pdf)
    except Exception as exc:  # noqa: BLE001 - qualquer falha de leitura é saída corrompida
        relatorio.violacoes.append(f"PDF ilegível: {exc}")
        raise Inconsistencia("; ".join(relatorio.violacoes)) from exc
    try:
        _conferir(doc, plano, relatorio)
    finally:
        doc.close()
    if relatorio.violacoes:
        raise Inconsistencia("gate estrutural: " + "; ".join(relatorio.violacoes[:30]))
    return relatorio


def _conferir(doc: pymupdf.Document, plano: Plano, rel: RelatorioGate) -> None:
    v = rel.violacoes
    rel.paginas_reais = len(doc)
    if len(doc) != len(plano.paginas):
        v.append(f"páginas reais/esperadas: {len(doc)}/{len(plano.paginas)}")
        return

    # Links: todos internos e com destino existente (LNK-05, LNK-06)
    for numero, pagina in enumerate(doc):
        for link in pagina.get_links():
            rel.links += 1
            alvo = destino(link)
            if alvo is None:
                v.append(f"página {numero + 1}: link externo ou não interno")
            elif not 0 <= alvo < len(doc):
                v.append(f"página {numero + 1}: link para página inexistente {alvo + 1}")

    if plano.tem_setlist:
        _setlist(doc[0], plano, rel)
    _indice(doc[plano.pagina_indice], plano, rel)
    _partituras(doc, plano, rel)
    _auxiliares(doc, plano, rel)


def _conferir_link(pagina, linha: Linha, esperado: int | None) -> tuple[bool, list, float]:
    sobre = links_sobre(pagina, linha.rect)
    destinos = [destino(lk) for lk in sobre]
    if esperado is None:
        return not sobre, destinos, 0.0
    cob = max((cobertura(lk["from"], linha.rect) for lk in sobre), default=0.0)
    ok = bool(sobre) and all(d == esperado for d in destinos) and cob >= COBERTURA_MINIMA
    return ok, destinos, cob


def _setlist(pagina, plano: Plano, rel: RelatorioGate) -> None:
    """Cada item aponta para a sua ocorrência; ausente fica sem link (SET-04, SET-05, SET-09)."""
    candidatas, usadas = linhas(pagina), set()
    for item in plano.setlist:
        registro = {
            "posicao": item.posicao,
            "titulo": item.titulo,
            "esperado": _humano(item.pagina),
        }
        achado = melhor_linha(candidatas, item.titulo, usadas, MINIMO_SETLIST)
        if achado is None:
            rel.violacoes.append(f"set list {item.posicao}: texto não encontrado")
            rel.setlist.append({**registro, "ok": False})
            continue
        usadas.add(achado[0])
        ok, destinos, cob = _conferir_link(pagina, achado[1], item.pagina)
        rel.setlist.append(
            {
                **registro,
                "destinos": [_humano(d) for d in destinos],
                "cobertura": round(cob, 3),
                "ok": ok,
            }
        )
        if not ok:
            rel.violacoes.append(f"set list {item.posicao} ({item.titulo}): link divergente")


def _indice(pagina, plano: Plano, rel: RelatorioGate) -> None:
    """3 colunas reais, leitura coluna a coluna e destino exato (IDX-05 a IDX-07, VAL-03)."""
    candidatas = [ln for ln in linhas(pagina) if normalizar(ln.texto) != normalizar(TITULO_INDICE)]
    usadas: set[int] = set()
    localizadas: list[tuple[str, Linha]] = []
    for item in plano.indice:
        registro = {"titulo": item.entrada.titulo, "esperado": item.pagina + 1}
        achado = linha_exata(candidatas, item.entrada.rotulo_pdf, usadas)
        if achado is None:
            rel.violacoes.append(f"índice: {item.entrada.titulo} sem correspondência inequívoca")
            rel.indice.append({**registro, "ok": False})
            continue
        usadas.add(achado[0])
        if achado[1].texto.strip() != item.entrada.rotulo_pdf.strip():
            rel.violacoes.append(
                f"índice: texto desenhado {achado[1].texto.strip()!r} difere de "
                f"{item.entrada.rotulo_pdf!r} (IDX-08)"
            )
        localizadas.append((item.entrada.rotulo_pdf, achado[1]))
        ok, destinos, cob = _conferir_link(pagina, achado[1], item.pagina)
        rel.indice.append(
            {
                **registro,
                "destinos": [_humano(d) for d in destinos],
                "cobertura": round(cob, 3),
                "ok": ok,
            }
        )
        if not ok:
            rel.violacoes.append(f"índice ({item.entrada.titulo}): link divergente")

    # Colunas físicas pelos agrupamentos reais de x0
    xs = sorted(ln.rect.x0 for _, ln in localizadas)
    grupos: list[list[float]] = []
    limiar = max(24.0, pagina.rect.width * 0.10)
    for x in xs:
        if not grupos or x - grupos[-1][-1] > limiar:
            grupos.append([x])
        else:
            grupos[-1].append(x)
    centros = [sum(g) / len(g) for g in grupos]
    por_coluna: list[list[tuple[str, Linha]]] = [[] for _ in centros]
    for rotulo, ln in localizadas:
        c = min(range(len(centros)), key=lambda i: abs(ln.rect.x0 - centros[i]))
        por_coluna[c].append((rotulo, ln))
    for coluna in por_coluna:
        coluna.sort(key=lambda par: (par[1].rect.y0, par[1].rect.x0))
    rel.indice_colunas = [len(c) for c in por_coluna]
    esperado = tamanhos_colunas(len(plano.indice))
    ocupadas = [t for t in esperado if t > 0]
    if rel.indice_colunas != ocupadas:
        rel.violacoes.append(f"índice: colunas {rel.indice_colunas}, esperado {esperado}")
    leitura = [normalizar(ln.texto) for coluna in por_coluna for _, ln in coluna]
    if leitura != [normalizar(d.entrada.rotulo_pdf) for d in plano.indice]:
        rel.violacoes.append("índice: leitura coluna a coluna fora da ordem alfabética")


def _partituras(doc, plano: Plano, rel: RelatorioGate) -> None:
    """Título e parte de cada página e dois retornos para a página 1 (VAL-02, LNK-01, LNK-02)."""
    for p in plano.paginas_partitura:
        pagina = doc[p.pagina]
        texto = pagina.get_text("text") or ""
        titulo_ok = normalizar(p.musica) in normalizar(texto) if normalizar(p.musica) else False
        parte_ok = True
        if p.total > 1 and texto.strip():
            parte_ok = bool(re.search(rf"\(\s*{p.parte}\s*de\s*{p.total}\s*\)", texto, re.I))
        retornos = [lk for lk in pagina.get_links() if destino(lk) == 0]
        topo_ok = all(pymupdf.Rect(lk["from"]).y0 > 0 for lk in retornos)
        registro = {
            "pagina": p.pagina + 1,
            "musica": p.musica,
            "parte": p.parte,
            "total": p.total,
            "ocorrencia": p.ocorrencia,
            "titulo_ok": titulo_ok,
            "parte_ok": parte_ok,
            "retornos": len(retornos),
        }
        rel.partituras.append(registro)
        if not titulo_ok:
            rel.violacoes.append(f'página {p.pagina + 1}: título "{p.musica}" não confirmado')
        if not parte_ok:
            rel.violacoes.append(
                f"página {p.pagina + 1}: parte {p.parte} de {p.total} não confirmada"
            )
        if len(retornos) < 2:
            rel.violacoes.append(f"página {p.pagina + 1}: retornos título/ABC insuficientes")
        if not topo_ok:
            rel.violacoes.append(
                f"página {p.pagina + 1}: área de retorno encosta na margem superior"
            )


def _auxiliares(doc, plano: Plano, rel: RelatorioGate) -> None:
    """Auxiliares não recebem retornos de título/ABC (PRES-03, LNK-04)."""
    for p in plano.paginas:
        if p.papel is Papel.AUXILIAR and any(destino(lk) == 0 for lk in doc[p.pagina].get_links()):
            rel.violacoes.append(f"página auxiliar {p.pagina + 1} recebeu link de retorno")


def _humano(pagina: int | None) -> int | None:
    return None if pagina is None else pagina + 1
