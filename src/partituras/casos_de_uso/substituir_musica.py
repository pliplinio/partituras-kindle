"""Substituição simples de uma música (caminho rápido).

Uma edição de HTML, um PDF candidato e um fingerprint (FLX-03):

1. edita o HTML e passa no gate de escopo (VAL-04);
2. tenta o patch incremental sobre o PDF anterior aprovado (PDF-11);
   se não couber, gera o PDF integral e registra o motivo (PDF-12);
3. gate estrutural (VAL-01) e gate nominal da música (VAL-05);
4. fingerprint de 100% das páginas, uma vez, e delta com o manifesto anterior
   (INS-01, INS-09), reaproveitando o mesmo manifesto (FLX-03);
5. renderiza só as páginas que exigem inspeção (INS-05).

Nada é promovido aqui: o candidato aguarda a inspeção.
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from pathlib import Path

from partituras.casos_de_uso.gerar_pdf import gerar_candidato, nome_candidato
from partituras.dominio.plano import planejar
from partituras.html import escopo
from partituras.html.documento import Documento
from partituras.html.edicao import (
    PedidoMusica,
    RelatorioMusica,
    gravar_musica,
    ordenar_pelo_setlist,
)
from partituras.pdf import patch
from partituras.pdf.conversao import Conversor
from partituras.pdf.fingerprint import Delta, carregar_manifesto_aprovado, delta, manifesto
from partituras.pdf.gate import validar
from partituras.pdf.inspecao import Alerta, folhas_de_contato, gate_nominal, pre_validar, renderizar


@dataclass(frozen=True)
class Anterior:
    """PDF aprovado anterior: manifesto (preferido) e/ou arquivo, com o SHA-256 aprovado."""

    sha256: str
    manifesto: Path | None = None
    pdf: Path | None = None


@dataclass
class ResultadoSubstituicao:
    html: bytes
    edicao: RelatorioMusica
    candidato: Path
    sha256: str
    metodo: str
    motivo_integral: str | None
    nominal: dict
    manifesto: dict
    delta: Delta
    alertas: list[Alerta]
    renders: list[Path]
    folhas: list[Path]
    tempos: dict[str, float] = field(default_factory=dict)
    reordenado: bool = False


def substituir(
    html: bytes,
    pedido: PedidoMusica,
    pasta: Path,
    nome_final: str,
    anterior: Anterior | None = None,
    conversor: Conversor | None = None,
) -> ResultadoSubstituicao:
    tempos: dict[str, float] = {}
    t = time.perf_counter()

    original = Documento.de_bytes(html)
    # SET-10: um HTML fora da ordem do set list é reordenado antes da troca; o gate de
    # escopo compara com o HTML já ordenado, e a ordem final do PDF não muda.
    antes = ordenar_pelo_setlist(original)
    depois, edicao = gravar_musica(antes, pedido, substituir=True)
    escopo.exigir(antes, depois, edicao.grupo)
    plano = planejar(depois.repertorio())
    tempos["edicao_html"] = round(time.perf_counter() - t, 3)

    candidato = pasta / nome_candidato(nome_final)
    metodo, motivo = patch.METODO, None
    t = time.perf_counter()
    try:
        if anterior is None or anterior.pdf is None:
            raise patch.PatchIncompativel("sem PDF anterior aprovado disponível")
        imagens = [p.read_bytes() for p in pedido.imagens]
        patch.aplicar(anterior.pdf, anterior.sha256, plano, edicao.grupo, imagens, candidato)
        validar(candidato, plano)
    except patch.PatchIncompativel as exc:
        candidato.unlink(missing_ok=True)
        metodo, motivo = "geracao_integral", str(exc)
        gerar_candidato(depois.para_bytes(), pasta, nome_final, conversor)
    except Exception:
        candidato.unlink(missing_ok=True)
        raise
    tempos["pdf"] = round(time.perf_counter() - t, 3)

    try:
        t = time.perf_counter()
        nominal = gate_nominal(candidato, plano, edicao.grupo)
        alertas = pre_validar(candidato, plano)
        tempos["gates"] = round(time.perf_counter() - t, 3)

        t = time.perf_counter()
        man = manifesto(candidato)
        anterior_man = _manifesto_anterior(anterior)
        d = delta(man, anterior_man)
        tempos["fingerprint_delta"] = round(time.perf_counter() - t, 3)

        t = time.perf_counter()
        paginas = sorted(d.para_inspecao)
        renders = renderizar(candidato, paginas, pasta / "renders") if paginas else []
        folhas = folhas_de_contato(renders, pasta / "renders") if renders else []
        tempos["renderizacao"] = round(time.perf_counter() - t, 3)
    except Exception:
        candidato.unlink(missing_ok=True)
        raise

    return ResultadoSubstituicao(
        html=depois.para_bytes(),
        edicao=edicao,
        candidato=candidato,
        sha256=hashlib.sha256(candidato.read_bytes()).hexdigest(),
        metodo=metodo,
        motivo_integral=motivo,
        nominal=nominal,
        manifesto=man,
        delta=d,
        alertas=alertas,
        renders=renders,
        folhas=folhas,
        tempos=tempos,
        reordenado=antes.texto != original.texto,
    )


def _manifesto_anterior(anterior: Anterior | None) -> dict | None:
    """Manifesto primeiro; o PDF anterior só é renderizado como alternativa (INS-09)."""
    if anterior is None:
        return None
    if anterior.manifesto is not None:
        dados = json.loads(anterior.manifesto.read_text(encoding="utf-8"))
        return carregar_manifesto_aprovado(dados, anterior.sha256)
    if anterior.pdf is not None:
        return carregar_manifesto_aprovado(manifesto(anterior.pdf), anterior.sha256)
    return None
