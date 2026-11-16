"""Envio ao Kindle: escolha do caminho, tentativas e limpeza de versões antigas.

KIN-01 a KIN-06. O envio em si é feito fora do código (conector Gmail ou Gmail
no navegador do app); aqui ficam as decisões e o registro.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from partituras.dominio.versoes import versao_do_pdf

DESTINATARIO = "plinio.plinio_GuQd3r@kindle.com"
LIMITE_CONECTOR_BYTES = 4_200_000
LIMITE_ANEXO_CONECTOR_BYTES = 3_100_000  # base64 + cabeçalhos cabem em 4,2 MB


class Metodo(StrEnum):
    ENVIO_DIRETO = "gmail_conector_envio"
    RASCUNHO = "gmail_conector_rascunho"
    NAVEGADOR = "gmail_navegador_anexo_drive"


class Status(StrEnum):
    SUCESSO = "SUCESSO"
    FALHA = "FALHA"
    BLOQUEADO = "BLOQUEADO"
    NAO_SOLICITADO = "NAO_SOLICITADO"


def caminhos(tamanho_pdf: int) -> list[Metodo]:
    """Ordem de tentativas (KIN-03, KIN-04): conector só se o anexo couber."""
    if tamanho_pdf <= LIMITE_ANEXO_CONECTOR_BYTES:
        return [Metodo.ENVIO_DIRETO, Metodo.RASCUNHO, Metodo.NAVEGADOR]
    return [Metodo.NAVEGADOR]


@dataclass
class Tentativa:
    metodo: Metodo
    sucesso: bool
    mensagem: str = ""
    anexo: bool = True


@dataclass
class Envio:
    """Registro das tentativas de envio (KIN-05)."""

    arquivo: str
    sha256: str
    tamanho: int
    solicitado: bool = True
    tentativas: list[Tentativa] = field(default_factory=list)

    def registrar(self, metodo: Metodo, sucesso: bool, mensagem: str = "", anexo: bool = True):
        if not anexo:
            raise ValueError("o PDF vai como anexo, nunca como link do Drive (KIN-05)")
        if metodo not in caminhos(self.tamanho):
            raise ValueError(f"{metodo} não é um caminho válido para {self.tamanho} bytes")
        self.tentativas.append(Tentativa(metodo, sucesso, mensagem, anexo))

    @property
    def status(self) -> Status:
        """BLOQUEADO só depois de tentar todos os caminhos de verdade (KIN-04, PRO-05)."""
        if not self.solicitado:
            return Status.NAO_SOLICITADO
        if any(t.sucesso for t in self.tentativas):
            return Status.SUCESSO
        tentados = {t.metodo for t in self.tentativas}
        if self.tentativas and tentados >= set(caminhos(self.tamanho)):
            return Status.BLOQUEADO
        return Status.FALHA

    def proximo_caminho(self) -> Metodo | None:
        if self.status is not Status.FALHA:
            return None
        # Próximo caminho ainda não tentado. Após erro transitório, repetir o mesmo
        # caminho uma vez continua permitido (KIN-04): basta registrar de novo.
        tentados = {t.metodo for t in self.tentativas}
        return next((m for m in caminhos(self.tamanho) if m not in tentados), None)

    def como_dict(self) -> dict:
        return {
            "destinatario": DESTINATARIO,
            "arquivo": self.arquivo,
            "sha256": self.sha256,
            "tamanho": self.tamanho,
            "status": self.status.value,
            "tentativas": [
                {"metodo": t.metodo.value, "sucesso": t.sucesso, "mensagem": t.mensagem}
                for t in self.tentativas
            ],
        }


def versoes_antigas(fanfarra: str, titulos: list[str], enviado: str) -> list[str]:
    """Outros documentos versionados da mesma fanfarra, além do recém-enviado (KIN-06).

    Como a numeração da versão Claude recomeçou (PDF-03), um documento antigo pode
    ter número maior que o novo; por isso não se compara versão. A lista só
    sugere; a exclusão exige confirmação do usuário.
    """
    atual = enviado.removesuffix(".pdf").casefold()
    antigas = []
    for titulo in titulos:
        nome = titulo if titulo.lower().endswith(".pdf") else f"{titulo}.pdf"
        if (
            versao_do_pdf(nome, fanfarra) is not None
            and titulo.removesuffix(".pdf").casefold() != atual
        ):
            antigas.append(titulo)
    return antigas
