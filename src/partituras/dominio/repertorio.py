"""Montagem e validação estrutural do repertório (EST-01, EST-02, MULTI-01 a MULTI-04, SET-10)."""

from __future__ import annotations

from partituras.dominio.erros import Inconsistencia
from partituras.dominio.modelos import ItemSetlist, Musica, Pagina, Papel, Repertorio


def problemas_estruturais(paginas: list[Pagina]) -> list[str]:
    """Lista todas as inconsistências; vazia quando o repertório é válido."""
    problemas: list[str] = []

    vistos: set[str] = set()
    for pagina in paginas:
        if not pagina.id:
            problemas.append("página sem id")
        elif pagina.id in vistos:
            problemas.append(f"id repetido: {pagina.id}")
        vistos.add(pagina.id)

    partituras = [p for p in paginas if p.papel is Papel.PARTITURA]
    for p in partituras:
        faltando = [
            nome
            for nome, valor in (
                ("data-song", p.musica),
                ("data-group", p.grupo),
                ("data-part", p.parte),
                ("data-total-parts", p.total_partes),
            )
            if valor in (None, "")
        ]
        if faltando:
            problemas.append(f"{p.id}: faltam {', '.join(faltando)}")

    if problemas:
        return problemas

    # Grupos: páginas consecutivas na ordem do arquivo, partes 1..N, mesmo total.
    sequencia = [p for p in paginas if p.papel is Papel.PARTITURA]
    blocos: list[list[Pagina]] = []
    for p in sequencia:
        if blocos and blocos[-1][0].grupo == p.grupo:
            blocos[-1].append(p)
        else:
            blocos.append([p])

    vistos_grupos: set[str] = set()
    for bloco in blocos:
        grupo = bloco[0].grupo
        if grupo in vistos_grupos:
            problemas.append(f"grupo {grupo}: páginas não consecutivas")
            continue
        vistos_grupos.add(grupo)
        totais = {p.total_partes for p in bloco}
        if len(totais) != 1:
            problemas.append(f"grupo {grupo}: data-total-parts diferentes {sorted(totais)}")
            continue
        total = totais.pop()
        partes = [p.parte for p in bloco]
        if partes != list(range(1, total + 1)):
            problemas.append(f"grupo {grupo}: partes {partes}, esperado 1..{total}")
        titulos = {p.musica for p in bloco}
        if len(titulos) != 1:
            problemas.append(f"grupo {grupo}: títulos diferentes {sorted(titulos)}")

    return problemas


def montar_repertorio(
    paginas: list[Pagina],
    setlist: list[ItemSetlist] | None,
    tem_indice: bool,
) -> Repertorio:
    """Valida e agrupa. Levanta `Inconsistencia` com todos os problemas encontrados."""
    problemas = problemas_estruturais(paginas)
    if setlist is not None:
        posicoes = [i.posicao for i in setlist]
        if len(set(posicoes)) != len(posicoes):
            problemas.append(f"set list com posições repetidas: {posicoes}")
    if problemas:
        raise Inconsistencia("; ".join(problemas))

    musicas: list[Musica] = []
    for p in paginas:
        if p.papel is not Papel.PARTITURA:
            continue
        if musicas and musicas[-1].grupo == p.grupo:
            ultimo = musicas[-1]
            musicas[-1] = Musica(ultimo.grupo, ultimo.titulo, (*ultimo.paginas, p.id))
        else:
            musicas.append(Musica(p.grupo, p.musica, (p.id,)))

    if setlist is not None:
        grupos = {m.grupo for m in musicas}
        orfaos = [i for i in setlist if i.grupo and i.grupo not in grupos]
        if orfaos:
            raise Inconsistencia(
                "set list aponta para grupos inexistentes: "
                + ", ".join(f"{i.posicao}:{i.grupo}" for i in orfaos)
            )

    return Repertorio(
        paginas=list(paginas),
        setlist=sorted(setlist, key=lambda i: i.posicao) if setlist is not None else None,
        tem_indice=tem_indice,
        musicas=musicas,
    )


def ordem_pelo_setlist(repertorio: Repertorio) -> list[str]:
    """IDs das páginas na ordem física que o HTML canônico deve ter (SET-10).

    Com set list: set list, índice, as músicas na ordem da primeira ocorrência no set
    list, depois as músicas fora do set list na ordem atual e, por fim, as páginas
    auxiliares na ordem atual. Música repetida no set list não duplica páginas no HTML
    (a duplicação acontece só no PDF, SET-05). Sem set list, a ordem atual vale (SET-08).
    """
    paginas = repertorio.paginas
    if repertorio.setlist is None:
        return [p.id for p in paginas]
    frente = [p.id for papel in (Papel.SETLIST, Papel.INDICE) for p in paginas if p.papel is papel]
    grupos: list[str] = []
    for item in repertorio.setlist:
        if item.grupo and item.grupo not in grupos:
            grupos.append(item.grupo)
    grupos += [m.grupo for m in repertorio.musicas if m.grupo not in grupos]
    meio = [id_ for g in grupos for id_ in repertorio.musica(g).paginas]
    auxiliares = [p.id for p in paginas if p.papel is Papel.AUXILIAR]
    return frente + meio + auxiliares


def problemas_ordem(repertorio: Repertorio) -> list[str]:
    """Divergência entre a ordem do arquivo e a exigida pelo set list (SET-11)."""
    atual = [p.id for p in repertorio.paginas]
    esperada = ordem_pelo_setlist(repertorio)
    if atual == esperada:
        return []
    i = next(i for i, (a, e) in enumerate(zip(atual, esperada, strict=True)) if a != e)
    return [
        f"HTML fora da ordem do set list (SET-10): a página {i + 1} é {atual[i]}, "
        f"esperado {esperada[i]}"
    ]
