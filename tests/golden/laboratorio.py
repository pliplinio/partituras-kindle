"""Referências golden do laboratório da Fanfateste (TST-03, TST-04).

- `snapshot` resume um PDF de cenário: sequência e fingerprint de cada página.
- `comparar` devolve SEM_GOLDEN, OK ou DIVERGENTE contra `expected/<cenario>`.
- `resumo` só declara `regression_validated_against_golden` quando todos os
  cenários positivos têm golden e coincidem.
- `promover` grava `expected/` apenas com aprovação visual explícita, que cobre
  todos os cenários positivos. A execução normal nunca escreve em `expected/`.

Os pixels dependem do Chromium, do PyMuPDF e das fontes do sistema; por isso a
comparação golden é feita no ambiente em que as referências foram aprovadas.
"""

from __future__ import annotations

import json
from pathlib import Path

POSITIVOS = (
    "01_Jonia", "02_Doria", "03_Frigia", "04_Lidio", "05_replace_fast_1p",
    "06_replace_fast_multipage", "07_setlist_reorder", "08_setlist_repeat",
    "09_non_setlist_preserved", "10_missing_score",
)  # fmt: skip
NEGATIVOS = ("11_bad_external_link", "12_wrong_internal_target")
EXPECTED = Path(__file__).parent / "expected"


def snapshot(manifesto: dict, sequencia: list) -> dict:
    return {
        "total_paginas": manifesto["total_paginas"],
        "sequencia": sequencia,
        "paginas": [
            {k: p[k] for k in ("pagina", "visual_sha256", "text_sha256", "links_sha256")}
            for p in manifesto["paginas"]
        ],
    }


def comparar(cenario: str, atual: dict, expected: Path = EXPECTED) -> dict:
    arquivo = expected / cenario / "snapshot.json"
    if not arquivo.is_file():
        return {"cenario": cenario, "golden": "SEM_GOLDEN", "divergentes": []}
    referencia = json.loads(arquivo.read_text(encoding="utf-8"))
    if referencia.get("total_paginas") != atual["total_paginas"]:
        return {"cenario": cenario, "golden": "DIVERGENTE", "divergentes": ["total_paginas"]}
    divergentes = [
        a["pagina"] for a, r in zip(atual["paginas"], referencia["paginas"], strict=True) if a != r
    ]
    if referencia.get("sequencia") != atual["sequencia"]:
        divergentes.append("sequencia")
    return {
        "cenario": cenario,
        "golden": "OK" if not divergentes else "DIVERGENTE",
        "divergentes": divergentes,
    }


def resumo(positivos: dict[str, dict], negativos_rejeitados: dict[str, bool]) -> dict:
    """PASS = gates positivos aprovados e negativos rejeitados (TST-03)."""
    passou = all(negativos_rejeitados.get(n) for n in NEGATIVOS) and set(positivos) == set(
        POSITIVOS
    )
    divergentes = [c for c, r in positivos.items() if r["golden"] == "DIVERGENTE"]
    return {
        "status": "PASS" if passou and not divergentes else "FAIL",
        "regression_validated_against_golden": passou
        and all(positivos[c]["golden"] == "OK" for c in POSITIVOS),
        "sem_golden": sorted(c for c, r in positivos.items() if r["golden"] == "SEM_GOLDEN"),
        "divergentes": divergentes,
    }


def promover(snapshots: dict[str, dict], aprovacao: dict, expected: Path = EXPECTED) -> list[Path]:
    """Grava as referências só com aprovação visual que cubra todos os positivos (TST-04)."""
    if aprovacao.get("approved") is not True:
        raise PermissionError("promoção exige aprovação visual explícita (approved=true)")
    cobertos = set(aprovacao.get("scenarios") or [])
    faltando = sorted(set(POSITIVOS) - cobertos)
    if faltando:
        raise PermissionError(f"aprovação não cobre os cenários: {faltando}")
    if set(snapshots) != set(POSITIVOS):
        raise ValueError("promoção exige snapshots de todos os cenários positivos")
    gravados = []
    for cenario, dados in snapshots.items():
        destino = expected / cenario / "snapshot.json"
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_text(json.dumps(dados, ensure_ascii=False, indent=1), encoding="utf-8")
        gravados.append(destino)
    return gravados
