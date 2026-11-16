"""Erros que interrompem o processamento (FLX-06).

Só três situações param uma execução: ambiguidade, inconsistência e bloqueio
real. Qualquer outra diferença é registrada e o processamento continua.
"""

from __future__ import annotations


class ErroPartituras(Exception):
    """Base de todos os erros do domínio."""


class Ambiguidade(ErroPartituras):
    """Mais de uma opção plausível; nunca resolvida silenciosamente (NOM-04)."""


class Inconsistencia(ErroPartituras):
    """Estrutura do repertório ou do pedido contradiz as regras."""


class Bloqueio(ErroPartituras):
    """Operação impossível sem intervenção: arquivo ausente, sobrescrita proibida etc."""
