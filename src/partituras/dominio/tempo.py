"""Medição de tempo da execução (TMP-01 a TMP-07).

O cronômetro é um dado puro: começa antes da primeira leitura do Drive, é
serializado a cada passo pelo chamador e nunca é reiniciado. O total é sempre
fim − início por relógio.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime

NAO_EXECUTADA = "NAO_EXECUTADA"
INCOMPLETA = "MEDICAO_DE_TEMPO_INCOMPLETA"

CONTADORES = (
    "descobertas_drive",
    "downloads",
    "edicoes_html",
    "pdfs_candidatos",
    "fingerprints",
    "paginas_renderizadas",
    "paginas_reutilizadas",
    "repeticoes",
)

Relogio = Callable[[], datetime]


def agora() -> datetime:
    return datetime.now(UTC)


def _iso(momento: datetime | None) -> str | None:
    return momento.isoformat(timespec="milliseconds") if momento else None


def _de_iso(texto: str | None) -> datetime | None:
    if not texto:
        return None
    momento = datetime.fromisoformat(texto)
    if momento.tzinfo is None:
        raise ValueError(f"timestamp sem timezone: {texto}")
    return momento


@dataclass
class Etapa:
    nome: str
    inicio: datetime | None = None
    fim: datetime | None = None
    resultado: str = NAO_EXECUTADA
    tentativas: int = 0

    @property
    def duracao(self) -> float | None:
        if self.inicio is None or self.fim is None:
            return None
        return round((self.fim - self.inicio).total_seconds(), 3)

    def como_dict(self) -> dict:
        return {
            "nome": self.nome,
            "inicio": _iso(self.inicio),
            "fim": _iso(self.fim),
            "duracao_s": self.duracao,
            "resultado": self.resultado,
            "tentativas": self.tentativas,
        }


@dataclass
class Cronometro:
    workflow_started_at: datetime
    request_received_at: datetime | None = None
    first_drive_read_at: datetime | None = None
    workflow_finished_at: datetime | None = None
    etapas: dict[str, Etapa] = field(default_factory=dict)
    contadores: dict[str, int] = field(default_factory=lambda: dict.fromkeys(CONTADORES, 0))

    @classmethod
    def iniciar(
        cls, relogio: Relogio = agora, request_received_at: datetime | None = None
    ) -> Cronometro:
        """TMP-01, TMP-02: o pedido só é registrado quando informado, nunca inferido."""
        if request_received_at is not None and request_received_at.tzinfo is None:
            raise ValueError("request_received_at precisa de timezone")
        return cls(workflow_started_at=relogio(), request_received_at=request_received_at)

    def leitura_drive(self, relogio: Relogio = agora) -> None:
        if self.first_drive_read_at is None:
            self.first_drive_read_at = relogio()
        self.contar("descobertas_drive")

    def contar(self, contador: str, quantidade: int = 1) -> None:
        if contador not in self.contadores:
            raise KeyError(contador)
        self.contadores[contador] += quantidade

    def comecar(self, nome: str, relogio: Relogio = agora) -> Etapa:
        etapa = self.etapas.get(nome) or Etapa(nome)
        etapa.inicio = etapa.inicio or relogio()
        etapa.tentativas += 1
        self.etapas[nome] = etapa
        return etapa

    def terminar(self, nome: str, resultado: str, relogio: Relogio = agora) -> Etapa:
        etapa = self.etapas[nome]
        etapa.fim = relogio()
        etapa.resultado = resultado
        return etapa

    def registrar_nao_executada(self, nome: str) -> None:
        self.etapas.setdefault(nome, Etapa(nome))

    def finalizar(self, relogio: Relogio = agora) -> None:
        """TMP-03: chamado depois da entrega e do relatório, logo antes da resposta."""
        self.workflow_finished_at = relogio()

    @property
    def total(self) -> float | None:
        """TMP-04: fim − início por relógio."""
        if self.workflow_finished_at is None:
            return None
        return round((self.workflow_finished_at - self.workflow_started_at).total_seconds(), 3)

    @property
    def tempo_percebido(self) -> float | None:
        if self.workflow_finished_at is None or self.request_received_at is None:
            return None
        return round((self.workflow_finished_at - self.request_received_at).total_seconds(), 3)

    def problemas(self) -> list[str]:
        """TMP-07: o que impede um total confiável."""
        p = []
        if self.workflow_finished_at is None:
            p.append("fim não registrado")
        elif self.workflow_finished_at < self.workflow_started_at:
            p.append("fim anterior ao início")
        if self.first_drive_read_at and self.first_drive_read_at < self.workflow_started_at:
            p.append("leitura do Drive antes do início do cronômetro")
        for etapa in self.etapas.values():
            if etapa.inicio is not None and etapa.fim is None:
                p.append(f"etapa {etapa.nome} sem fim")
        return p

    def como_dict(self) -> dict:
        return {
            "request_received_at_utc": _iso(self.request_received_at),
            "workflow_started_at_utc": _iso(self.workflow_started_at),
            "first_drive_read_at_utc": _iso(self.first_drive_read_at),
            "workflow_finished_at_utc": _iso(self.workflow_finished_at),
            "total_s": self.total,
            "tempo_percebido_s": self.tempo_percebido,
            "latencia_de_exibicao": "excluída",
            "etapas": [e.como_dict() for e in self.etapas.values()],
            "contadores": dict(self.contadores),
        }

    @classmethod
    def de_dict(cls, dados: dict) -> Cronometro:
        c = cls(
            workflow_started_at=_de_iso(dados["workflow_started_at_utc"]),
            request_received_at=_de_iso(dados.get("request_received_at_utc")),
            first_drive_read_at=_de_iso(dados.get("first_drive_read_at_utc")),
            workflow_finished_at=_de_iso(dados.get("workflow_finished_at_utc")),
        )
        for e in dados.get("etapas", []):
            c.etapas[e["nome"]] = Etapa(
                e["nome"], _de_iso(e["inicio"]), _de_iso(e["fim"]), e["resultado"], e["tentativas"]
            )
        c.contadores.update(dados.get("contadores", {}))
        return c
