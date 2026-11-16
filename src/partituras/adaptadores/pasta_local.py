"""Pasta operacional acessada pelo sistema de arquivos.

Serve para a pasta sincronizada `G:\\Meu Drive\\Tuba\\partituras_claude` quando o
código roda no computador do usuário, e para cópias locais nos testes. Lê e
grava sempre em bytes, preservando CRLF.
"""

from __future__ import annotations

import os
from pathlib import Path

from partituras.dominio.execucao import Arquivo, conferir_pasta


class PastaLocal:
    def __init__(self, raiz: Path) -> None:
        conferir_pasta(str(raiz))
        self.raiz = Path(raiz).resolve()
        self.local = str(raiz)

    def _caminho(self, nome: str) -> Path:
        caminho = (self.raiz / nome).resolve()
        if self.raiz.resolve() not in caminho.parents:
            raise ValueError(f"{nome} sai da pasta operacional")
        return caminho

    def _arquivo(self, caminho: Path) -> Arquivo:
        info = caminho.stat()
        nome = caminho.relative_to(self.raiz).as_posix()
        return Arquivo(nome=nome, id=f"{info.st_dev}:{info.st_ino}", tamanho=info.st_size)

    def listar(self) -> list[Arquivo]:
        return sorted(
            (self._arquivo(p) for p in self.raiz.rglob("*") if p.is_file()),
            key=lambda a: a.nome,
        )

    def ler(self, nome: str) -> bytes:
        return self._caminho(nome).read_bytes()

    def gravar(self, nome: str, dados: bytes, *, novo: bool) -> Arquivo:
        caminho = self._caminho(nome)
        caminho.parent.mkdir(parents=True, exist_ok=True)
        if novo:
            with open(caminho, "xb") as f:  # nunca sobrescreve (PDF-04)
                f.write(dados)
        else:
            if not caminho.is_file():
                raise FileNotFoundError(nome)
            # Reescreve o mesmo arquivo (mesmo ID), sem apagar e recriar.
            with open(caminho, "r+b") as f:
                f.write(dados)
                f.truncate()
                f.flush()
                os.fsync(f.fileno())
        return self._arquivo(caminho)
