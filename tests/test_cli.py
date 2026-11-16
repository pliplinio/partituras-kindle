from __future__ import annotations

import subprocess
import sys

import pytest

from partituras import __version__
from partituras.cli import main


def test_version(capsys: pytest.CaptureFixture[str]):
    with pytest.raises(SystemExit) as saida:
        main(["--version"])
    assert saida.value.code == 0
    assert capsys.readouterr().out.strip() == f"partituras {__version__}"


def test_modulo_executavel():
    resultado = subprocess.run(
        [sys.executable, "-m", "partituras", "--version"],
        capture_output=True,
        text=True,
        check=True,
    )
    assert resultado.stdout.strip() == f"partituras {__version__}"
