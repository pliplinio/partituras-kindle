"""Ponto de entrada da linha de comando `partituras`."""

from __future__ import annotations

import argparse
from collections.abc import Sequence

from partituras.version import __version__


def construir_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="partituras",
        description="Organizador de Partituras para Kindle (versão Claude).",
    )
    parser.add_argument("--version", action="version", version=f"partituras {__version__}")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = construir_parser()
    parser.parse_args(argv)
    parser.print_help()
    return 0
