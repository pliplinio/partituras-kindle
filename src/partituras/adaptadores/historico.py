"""Histórico de execuções em JSONL, só com acréscimos (HIS-01 a HIS-03)."""

from __future__ import annotations

import json
import re

from partituras.dominio.execucao import HISTORICO, Pasta

_SEGREDO = re.compile(r"senha|password|token|secret|segredo|cookie|credencia|api[_-]?key", re.I)


def sem_segredos(dados):
    """Remove chaves que possam conter segredos (HIS-03)."""
    if isinstance(dados, dict):
        return {k: sem_segredos(v) for k, v in dados.items() if not _SEGREDO.search(str(k))}
    if isinstance(dados, list):
        return [sem_segredos(v) for v in dados]
    return dados


def anexar(pasta: Pasta, registro: dict) -> None:
    """Acrescenta uma linha; as anteriores precisam continuar idênticas (HIS-01)."""
    linha = json.dumps(sem_segredos(registro), ensure_ascii=False, sort_keys=True) + "\n"
    nomes = {a.nome for a in pasta.listar()}
    if HISTORICO not in nomes:
        pasta.gravar(HISTORICO, linha.encode("utf-8"), novo=True)
        return
    anterior = pasta.ler(HISTORICO)
    if anterior and not anterior.endswith(b"\n"):
        anterior += b"\n"
    pasta.gravar(HISTORICO, anterior + linha.encode("utf-8"), novo=False)
    if not pasta.ler(HISTORICO).startswith(anterior):
        raise RuntimeError("histórico alterado fora do acréscimo")
