"""Plano semântico de distribuição das páginas no PDF (PDF-08, PDF-09, SET, PRES, IDX-05).

O mesmo plano orienta a materialização e o gate estrutural. Páginas são
numeradas a partir de 0 (índice no PDF); relatórios somam 1.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from enum import StrEnum

from partituras.dominio.erros import Inconsistencia
from partituras.dominio.indice import EntradaIndice, entradas_indice
from partituras.dominio.modelos import Papel, Repertorio


class Origem(StrEnum):
    SETLIST = "setlist"
    CANONICA = "canonica"
    PRESERVADA = "preservada_ao_final"


@dataclass(frozen=True)
class PaginaFinal:
    pagina: int
    pagina_crua: int
    papel: Papel
    id: str
    grupo: str | None = None
    musica: str | None = None
    parte: int | None = None
    total: int | None = None
    ocorrencia: int | None = None
    origem: Origem | None = None


@dataclass(frozen=True)
class DestinoSetlist:
    posicao: int
    titulo: str
    grupo: str | None
    pagina: int | None


@dataclass(frozen=True)
class DestinoIndice:
    entrada: EntradaIndice
    pagina: int


@dataclass
class Plano:
    tem_setlist: bool
    paginas: list[PaginaFinal]
    setlist: list[DestinoSetlist] = field(default_factory=list)
    indice: list[DestinoIndice] = field(default_factory=list)
    paginas_cruas: int = 0

    @property
    def inicio_partituras(self) -> int:
        return 2 if self.tem_setlist else 1

    @property
    def pagina_indice(self) -> int:
        return 1 if self.tem_setlist else 0

    @property
    def paginas_partitura(self) -> list[PaginaFinal]:
        return [p for p in self.paginas if p.papel is Papel.PARTITURA]

    @property
    def ordem_crua(self) -> list[int]:
        return [p.pagina_crua for p in self.paginas]

    @property
    def ausentes(self) -> list[DestinoSetlist]:
        return [d for d in self.setlist if d.grupo is None]

    @property
    def preservadas(self) -> list[str]:
        vistos: list[str] = []
        for p in self.paginas:
            if p.origem is Origem.PRESERVADA and p.grupo not in vistos:
                vistos.append(p.grupo)
        return vistos


def planejar(repertorio: Repertorio) -> Plano:
    """Deriva a sequência final do PDF a partir do repertório canônico."""
    paginas = repertorio.paginas
    if not repertorio.musicas:
        raise Inconsistencia("HTML sem páginas de partitura")
    if not repertorio.tem_indice:
        raise Inconsistencia("HTML sem índice; geração do PDF bloqueada (VAL-07)")
    tem_setlist = repertorio.setlist is not None
    frente = [Papel.SETLIST, Papel.INDICE] if tem_setlist else [Papel.INDICE]
    if [p.papel for p in paginas[: len(frente)]] != frente:
        raise Inconsistencia(
            f"o HTML deve começar por {[str(f) for f in frente]}, "
            f"encontrado {[str(p.papel) for p in paginas[: len(frente)]]}"
        )

    crua = {p.id: i for i, p in enumerate(paginas)}
    resultado: list[PaginaFinal] = [
        PaginaFinal(i, i, p.papel, p.id) for i, p in enumerate(paginas[: len(frente)])
    ]
    contagem: Counter[str] = Counter()
    primeira: dict[str, int] = {}
    destinos_setlist: list[DestinoSetlist] = []

    def materializar(grupo: str, origem: Origem) -> int:
        musica = repertorio.musica(grupo)
        contagem[grupo] += 1
        inicio = len(resultado)
        primeira.setdefault(grupo, inicio)
        for parte, id_ in enumerate(musica.paginas, start=1):
            resultado.append(
                PaginaFinal(
                    pagina=len(resultado),
                    pagina_crua=crua[id_],
                    papel=Papel.PARTITURA,
                    id=id_,
                    grupo=grupo,
                    musica=musica.titulo,
                    parte=parte,
                    total=len(musica.paginas),
                    ocorrencia=contagem[grupo],
                    origem=origem,
                )
            )
        return inicio

    if tem_setlist:
        for item in repertorio.setlist:
            pagina = materializar(item.grupo, Origem.SETLIST) if item.grupo else None
            destinos_setlist.append(DestinoSetlist(item.posicao, item.titulo, item.grupo, pagina))
        for musica in repertorio.musicas:
            if musica.grupo not in contagem:
                materializar(musica.grupo, Origem.PRESERVADA)
    else:
        for musica in repertorio.musicas:
            materializar(musica.grupo, Origem.CANONICA)

    for i, p in enumerate(paginas):
        if p.papel is Papel.AUXILIAR:
            resultado.append(PaginaFinal(len(resultado), i, Papel.AUXILIAR, p.id))

    indice = [DestinoIndice(e, primeira[e.grupo]) for e in entradas_indice(repertorio)]
    plano = Plano(tem_setlist, resultado, destinos_setlist, indice, len(paginas))
    problemas = problemas_preservacao(plano, repertorio)
    if problemas:
        raise Inconsistencia("; ".join(problemas))
    return plano


def problemas_preservacao(plano: Plano, repertorio: Repertorio) -> list[str]:
    """Compara a sequência final com TODAS as páginas canônicas de origem (PRES-01, PRES-04)."""
    problemas: list[str] = []
    finais = Counter(p.id for p in plano.paginas)
    for pagina in repertorio.paginas:
        if finais[pagina.id] == 0:
            problemas.append(f"página canônica {pagina.id} ausente do PDF")
    auxiliares = [p.id for p in repertorio.paginas if p.papel is Papel.AUXILIAR]
    for id_ in auxiliares:
        if finais[id_] != 1:
            problemas.append(f"página auxiliar {id_} aparece {finais[id_]} vezes")
    return problemas


def relatorio_pre_geracao(plano: Plano, repertorio: Repertorio) -> dict:
    """Resumo antes de gerar (REL-06)."""
    repeticoes = sorted(
        {p.grupo for p in plano.paginas_partitura if p.ocorrencia and p.ocorrencia > 1}
    )
    return {
        "musicas_canonicas": len(repertorio.musicas),
        "paginas_canonicas": len(repertorio.paginas),
        "setlist": [
            {
                "posicao": d.posicao,
                "musica": d.titulo,
                "grupo": d.grupo,
                "paginas": _paginas_da_ocorrencia(plano, d.pagina),
            }
            for d in plano.setlist
        ],
        "repeticoes": repeticoes,
        "multipaginas": [m.grupo for m in repertorio.musicas if len(m.paginas) > 1],
        "ausentes": [{"posicao": d.posicao, "musica": d.titulo} for d in plano.ausentes],
        "fora_do_setlist": plano.preservadas,
        "auxiliares": [p.id for p in plano.paginas if p.papel is Papel.AUXILIAR],
        "sequencia": [
            {
                "pagina": p.pagina + 1,
                "papel": str(p.papel),
                "id": p.id,
                "musica": p.musica,
                "parte": p.parte,
                "ocorrencia": p.ocorrencia,
            }
            for p in plano.paginas
        ],
        "total_esperado": len(plano.paginas),
    }


def _paginas_da_ocorrencia(plano: Plano, inicio: int | None) -> list[int]:
    if inicio is None:
        return []
    primeira = plano.paginas[inicio]
    return [inicio + 1 + i for i in range(primeira.total or 1)]
