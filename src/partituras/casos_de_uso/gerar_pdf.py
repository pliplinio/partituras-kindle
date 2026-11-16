"""Gera o PDF candidato a partir do HTML canônico (PDF-05, PDF-07, PDF-10, VAL-01).

HTML → PDF cru (temporário) → materialização → reabertura e gate estrutural.
Se qualquer etapa falhar, o candidato é apagado e nenhum nome final é criado.
"""

from __future__ import annotations

import hashlib
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path

from partituras.dominio.plano import Plano, planejar, relatorio_pre_geracao
from partituras.html.documento import Documento
from partituras.pdf.conversao import ChromiumConversor, Conversor, conferir_pdf_cru
from partituras.pdf.gate import RelatorioGate, validar
from partituras.pdf.materializacao import RelatorioMaterializacao, materializar

SUFIXO_CANDIDATO = ".candidate.pdf"


@dataclass
class ResultadoGeracao:
    candidato: Path
    sha256: str
    plano: Plano
    pre_geracao: dict
    materializacao: RelatorioMaterializacao
    gate: RelatorioGate
    conversor: str
    tempos: dict[str, float] = field(default_factory=dict)


def nome_candidato(nome_final: str) -> str:
    if not nome_final.lower().endswith(".pdf"):
        raise ValueError(f"nome final de PDF inválido: {nome_final}")
    return nome_final[:-4] + SUFIXO_CANDIDATO


def gerar_candidato(
    html: bytes,
    pasta: Path,
    nome_final: str,
    conversor: Conversor | None = None,
) -> ResultadoGeracao:
    conversor = conversor or ChromiumConversor()
    tempos: dict[str, float] = {}

    def medir(etapa: str, inicio: float) -> None:
        tempos[etapa] = round(time.perf_counter() - inicio, 3)

    t = time.perf_counter()
    doc = Documento.de_bytes(html)
    repertorio = doc.repertorio()
    plano = planejar(repertorio)
    pre = relatorio_pre_geracao(plano, repertorio)
    medir("plano", t)

    candidato = pasta / nome_candidato(nome_final)
    pasta.mkdir(parents=True, exist_ok=True)
    try:
        with tempfile.TemporaryDirectory() as temporaria:
            cru = Path(temporaria) / "cru.pdf"
            t = time.perf_counter()
            conversor.converter(html, cru)
            conferir_pdf_cru(cru, len(repertorio.paginas))
            medir("conversao", t)

            t = time.perf_counter()
            rel_mat = materializar(cru, candidato, plano)
            medir("materializacao", t)

        t = time.perf_counter()
        rel_gate = validar(candidato, plano)
        medir("gate_estrutural", t)
    except Exception:
        candidato.unlink(missing_ok=True)
        raise

    return ResultadoGeracao(
        candidato=candidato,
        sha256=hashlib.sha256(candidato.read_bytes()).hexdigest(),
        plano=plano,
        pre_geracao=pre,
        materializacao=rel_mat,
        gate=rel_gate,
        conversor=f"{conversor.nome} {getattr(conversor, 'versao', '') or ''}".strip(),
        tempos=tempos,
    )
