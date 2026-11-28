"""Ponto de entrada da linha de comando `partituras`.

Fluxo de uma execução (o diretório de trabalho guarda o estado entre passos):

    partituras iniciar   --trabalho T [--pedido ISO] [--sem-envio]
    partituras preparar  --trabalho T --pasta P --fanfarra F
    partituras gerar     --trabalho T [--setlist arquivo.txt] [--musica M --imagens a.png ...]
    partituras substituir --trabalho T --pasta P --musica M --imagens a.png [b.png ...]
    partituras aprovar   --trabalho T --inspecionadas 1-5,9 [--achado 3:texto]
    partituras promover  --trabalho T --pasta P
    partituras kindle    --trabalho T --metodo M --resultado sucesso|erro [--mensagem X]
    partituras finalizar --trabalho T [--pasta P]
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from partituras.adaptadores.pasta_local import PastaLocal
from partituras.casos_de_uso import executar
from partituras.dominio.erros import ErroPartituras
from partituras.dominio.kindle import Metodo
from partituras.version import __version__


def paginas(texto: str) -> list[int]:
    """`1-3,7` → [1, 2, 3, 7]."""
    saida: list[int] = []
    for parte in filter(None, (p.strip() for p in texto.split(","))):
        inicio, _, fim = parte.partition("-")
        saida += range(int(inicio), int(fim or inicio) + 1)
    return saida


def construir_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="partituras",
        description="Organizador de Partituras para Kindle (versão Claude).",
    )
    parser.add_argument("--version", action="version", version=f"partituras {__version__}")
    sub = parser.add_subparsers(dest="comando")

    def comando(nome: str, ajuda: str, pasta: bool = False) -> argparse.ArgumentParser:
        p = sub.add_parser(nome, help=ajuda)
        p.add_argument("--trabalho", type=Path, required=True)
        if pasta:
            p.add_argument("--pasta", type=Path, required=True)
        return p

    p = comando("iniciar", "inicia o cronômetro, antes de qualquer leitura do Drive")
    p.add_argument("--pedido", help="horário do pedido (ISO 8601 com timezone)")
    p.add_argument("--sem-envio", action="store_true", help="processar sem enviar ao Kindle")

    p = comando("preparar", "lista a pasta uma vez e congela o plano", pasta=True)
    p.add_argument("--fanfarra", required=True)
    p.add_argument(
        "--sem-kindle-disponivel",
        action="store_true",
        help="declara que não há como enviar ao Kindle nesta execução",
    )

    p = comando("gerar", "gera o PDF integral, com set list novo opcional")
    p.add_argument("--setlist", type=Path, help="arquivo de texto com o set list")
    p.add_argument("--musica", help="música a trocar no mesmo candidato (com --imagens)")
    p.add_argument("--imagens", type=Path, nargs="+", help="imagens da música, na ordem")

    p = comando("substituir", "troca uma música pelo caminho rápido", pasta=True)
    p.add_argument("--musica", required=True)
    p.add_argument("--imagens", type=Path, nargs="+", required=True)

    p = comando("aprovar", "registra a inspeção visual feita")
    p.add_argument("--inspecionadas", required=True, type=paginas)
    p.add_argument("--achado", action="append", default=[], help="PAGINA:descrição")

    comando("promover", "grava HTML, PDF e manifesto na pasta operacional", pasta=True)

    p = comando("kindle", "registra uma tentativa de envio ao Kindle")
    p.add_argument("--metodo", required=True, choices=[m.value for m in Metodo])
    p.add_argument("--resultado", required=True, choices=["sucesso", "erro"])
    p.add_argument("--mensagem", default="")

    p = sub.add_parser("finalizar", help="grava histórico e relatório e encerra o cronômetro")
    p.add_argument("--trabalho", type=Path, required=True)
    p.add_argument("--pasta", type=Path)
    return parser


def executar_comando(args: argparse.Namespace) -> object:
    if args.comando == "iniciar":
        executar.iniciar(args.trabalho, args.pedido, args.sem_envio)
        return {"iniciado": str(args.trabalho)}
    estado = executar.Estado.abrir(args.trabalho)
    if args.comando == "preparar":
        acoes = {"gravar_html", "criar_pdf", "ler_confirmar"}
        if not args.sem_kindle_disponivel:
            acoes.add("enviar_kindle")
        plano = executar.preparar(estado, PastaLocal(args.pasta), args.fanfarra, acoes)
        return plano.como_dict()
    if args.comando == "gerar":
        texto = args.setlist.read_text(encoding="utf-8") if args.setlist else None
        return _resumo(executar.gerar(estado, texto, musica=args.musica, imagens=args.imagens))
    if args.comando == "substituir":
        dados = executar.substituir_musica(
            estado, args.musica, args.imagens, PastaLocal(args.pasta)
        )
        return _resumo(dados)
    if args.comando == "aprovar":
        achados = dict((int(a.split(":", 1)[0]), a.split(":", 1)[1]) for a in args.achado)
        return _resumo(executar.aprovar(estado, args.inspecionadas, achados))
    if args.comando == "promover":
        return executar.promover_resultado(estado, PastaLocal(args.pasta))["promocao"]
    if args.comando == "kindle":
        dados = executar.registrar_kindle(
            estado, args.metodo, args.resultado == "sucesso", args.mensagem
        )
        return dados["kindle"]
    if args.comando == "finalizar":
        return executar.finalizar(estado, PastaLocal(args.pasta) if args.pasta else None)
    raise ValueError(args.comando)


def _resumo(dados: dict) -> dict:
    chaves = (
        "operacao", "candidato", "candidato_sha256", "metodo_pdf", "motivo_integral",
        "paginas_para_inspecao", "alertas", "inspecao", "setlist", "nominal", "html_reordenado",
        "erro",
    )  # fmt: skip
    return {k: dados[k] for k in chaves if k in dados}


def main(argv: Sequence[str] | None = None) -> int:
    parser = construir_parser()
    args = parser.parse_args(argv)
    if not args.comando:
        parser.print_help()
        return 0
    try:
        saida = executar_comando(args)
    except ErroPartituras as exc:
        print(f"ERRO ({type(exc).__name__}): {exc}", file=sys.stderr)
        return 2
    print(saida if isinstance(saida, str) else json.dumps(saida, ensure_ascii=False, indent=1))
    return 0
