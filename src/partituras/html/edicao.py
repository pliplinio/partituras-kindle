"""Edições do HTML canônico.

Toda função recebe um `Documento` e devolve um novo `Documento` candidato, sem
gravar nada (HTML-07). Quem grava é a camada de casos de uso, depois das
validações.
"""

from __future__ import annotations

import base64
import hashlib
import mimetypes
import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

from partituras.dominio.erros import Inconsistencia
from partituras.dominio.indice import entradas_indice
from partituras.dominio.modelos import Papel, Repertorio
from partituras.dominio.nomes import normalizar, normalizar_forte, slug
from partituras.dominio.setlist import resolver
from partituras.html import render
from partituras.html.documento import META_VERSAO, Documento, Secao, atributos
from partituras.html.overlay import posicoes

_DATA_URI = re.compile(r'src=["\']data:image/[^;]+;base64,([^"\']+)["\']', re.I | re.S)
_CSS_SCORE_NATIVE = "/* score-native-layout-v1 */"
_REGRA_SCORE_NATIVE = re.compile(r"(?<![\w-])\.score-native\s*\{")


def sha256(dados: bytes) -> str:
    return hashlib.sha256(dados).hexdigest()


# --- Versão de template ----------------------------------------------------------------------


def gravar_versao_template(doc: Documento, versao: int) -> Documento:
    """Grava ou atualiza `<meta name="partituras-template-version">` (HTML-02).

    Usado na adoção dos HTMLs copiados e em mudanças de template.
    """
    if versao < 1:
        raise Inconsistencia(f"versão de template inválida: {versao}")
    valor = f"{versao:02d}"
    for m in re.finditer(r"<meta\b[^>]*>", doc.texto, re.I):
        if atributos(m.group(0)).get("name", "").lower() == META_VERSAO:
            novo = f'<meta content="{valor}" name="{META_VERSAO}"/>'
            return doc.substituir(m.start(), m.end(), novo)
    charset = re.search(r"<meta\b[^>]*\bcharset\b[^>]*>", doc.texto, re.I)
    if charset is None:
        raise Inconsistencia("HTML sem <meta charset>; não sei onde gravar a versão de template")
    tag = f'<meta content="{valor}" name="{META_VERSAO}"/>'
    return doc.substituir(charset.end(), charset.end(), tag)


# --- Índice ---------------------------------------------------------------------------------


def reconstruir_indice(doc: Documento) -> Documento:
    """Regenera o índice a partir das músicas do HTML (IDX-01 a IDX-04, MUS-08)."""
    secao = doc.secao(Papel.INDICE)
    if secao is None:
        return doc
    corpo = render.corpo_indice(entradas_indice(doc.repertorio()))
    inicio = secao.inicio + len(secao.abertura)
    return doc.substituir(inicio, inicio + len(secao.corpo), corpo)


# --- Set list -------------------------------------------------------------------------------


@dataclass
class RelatorioSetlist:
    itens: int = 0
    links: int = 0
    ausentes: list[dict] = field(default_factory=list)
    correspondencias: list[dict] = field(default_factory=list)


def reconstruir_setlist(
    doc: Documento, titulos: Sequence[str] | None = None
) -> tuple[Documento, RelatorioSetlist]:
    """Regenera o set list como texto HTML com links (SET-02 a SET-06, SET-09).

    Sem `titulos`, mantém os itens atuais e as ligações já declaradas. Com
    `titulos`, substitui o set list inteiro, resolvendo cada nome por
    correspondência; ambiguidade interrompe (NOM-04).
    """
    secao = doc.secao(Papel.SETLIST)
    if secao is None:
        if titulos is not None:
            raise Inconsistencia("o HTML não tem set list para receber os itens informados")
        return doc, RelatorioSetlist()

    repertorio = doc.repertorio()
    if titulos is None:
        atuais = repertorio.setlist or []
        titulos = [i.titulo for i in atuais]
        declarados = [i.grupo for i in atuais]
    else:
        declarados = None
    resolucoes = resolver(list(titulos), repertorio.musicas, declarados)

    relatorio = RelatorioSetlist(itens=len(resolucoes))
    itens_html = []
    for r in resolucoes:
        musica = repertorio.musica(r.item.grupo) if r.item.grupo else None
        pagina = musica.primeira_pagina if musica else None
        itens_html.append(render.item_setlist(r.item.posicao, r.item.titulo, r.item.grupo, pagina))
        if musica:
            relatorio.links += 1
        else:
            relatorio.ausentes.append({"posicao": r.item.posicao, "titulo": r.item.titulo})
        if r.correspondencia is not None:
            relatorio.correspondencias.append(
                {"posicao": r.item.posicao, **r.correspondencia.como_dict()}
            )

    inicio = secao.inicio + len(secao.abertura)
    novo = doc.substituir(inicio, inicio + len(secao.corpo), render.corpo_setlist(itens_html))
    return novo, relatorio


# --- Música ---------------------------------------------------------------------------------


@dataclass(frozen=True)
class PedidoMusica:
    """Fanfarra, nome da música e imagens na ordem das partes (MUS-01)."""

    fanfarra: str
    titulo: str
    imagens: tuple[Path, ...]

    def __post_init__(self) -> None:
        if not self.fanfarra.strip():
            raise Inconsistencia("informe a fanfarra")
        if not self.titulo.strip():
            raise Inconsistencia("informe o nome da música")
        if not self.imagens:
            raise Inconsistencia("informe ao menos uma imagem da partitura")


def data_uri(caminho: Path) -> tuple[str, bytes]:
    """Imagem incorporada como data URI (MUS-06)."""
    if not caminho.is_file():
        raise Inconsistencia(f"imagem não encontrada: {caminho}")
    tipo = mimetypes.guess_type(caminho.name)[0] or ""
    if not tipo.startswith("image/"):
        raise Inconsistencia(f"arquivo não é imagem: {caminho}")
    dados = caminho.read_bytes()
    return f"data:{tipo};base64," + base64.b64encode(dados).decode("ascii"), dados


def sha256_imagem_incorporada(secao_html: str) -> str:
    m = _DATA_URI.search(secao_html)
    if not m:
        raise Inconsistencia("página sem imagem incorporada como data URI")
    try:
        return sha256(base64.b64decode(m.group(1), validate=True))
    except ValueError as exc:
        raise Inconsistencia("imagem incorporada com base64 inválido") from exc


def localizar_musica(repertorio: Repertorio, titulo: str) -> str | None:
    """Grupo da música pelo título normalizado ou pelo `data-group` (MUS-02).

    Só identificação inequívoca: mais de uma música com o mesmo nome bloqueia (MUS-04).
    """
    alvo, grupo_alvo = normalizar(titulo), slug(titulo)
    candidatas = [
        m for m in repertorio.musicas if m.grupo == grupo_alvo or normalizar(m.titulo) == alvo
    ]
    if len(candidatas) > 1:
        forte = normalizar_forte(titulo)
        candidatas = [m for m in candidatas if normalizar_forte(m.titulo) == forte] or candidatas
    achados = [m.grupo for m in candidatas]
    if len(achados) > 1:
        raise Inconsistencia(f'"{titulo}" identifica mais de uma música: {achados}')
    return achados[0] if achados else None


def _proximos_ids(doc: Documento, quantidade: int, reservados: Sequence[str]) -> list[str]:
    usados = set(re.findall(r'\bid=["\']([^"\']+)["\']', doc.texto, re.I)) | set(reservados)
    numeros = [int(n) for n in re.findall(r'\bid=["\']slide-(\d+)["\']', doc.texto, re.I)]
    n = max(numeros, default=0) + 1
    ids: list[str] = []
    while len(ids) < quantidade:
        candidato = f"slide-{n}"
        if candidato not in usados:
            ids.append(candidato)
            usados.add(candidato)
        n += 1
    return ids


def _garantir_css_score_native(doc: Documento) -> Documento:
    """Inclui o CSS mínimo da página raw-score só quando o HTML ainda não tem uma regra
    `.score-native{...}` (com ou sem o comentário-marcador); nunca duplica (VAL-04)."""
    if _CSS_SCORE_NATIVE in doc.texto or _REGRA_SCORE_NATIVE.search(doc.texto):
        return doc
    nl = doc.quebra_de_linha
    css = (
        f"{nl}{_CSS_SCORE_NATIVE}{nl}.score-native{{aspect-ratio:880/650;display:flex;"
        f"flex-direction:column;overflow:hidden;background:#fff;line-height:normal}}{nl}"
    )
    pos = doc.texto.find("</style>")
    if pos < 0:
        raise Inconsistencia("HTML sem bloco <style>; não sei onde incluir o CSS da página")
    return doc.substituir(pos, pos, css + nl)


@dataclass
class RelatorioMusica:
    acao: str
    musica: str
    grupo: str
    partes: int
    ids: list[str]
    modo: str
    imagens_entrada_sha256: list[str]
    imagens_incorporadas_sha256: list[str]
    setlist: RelatorioSetlist
    indice_regenerado: bool


def gravar_musica(
    doc: Documento, pedido: PedidoMusica, substituir: bool
) -> tuple[Documento, RelatorioMusica]:
    """Inclui (`substituir=False`) ou troca (`substituir=True`) uma música (MUS-02 a MUS-08).

    Na troca, só o grupo selecionado muda; IDs existentes são reaproveitados.
    Na inclusão, o grupo novo entra no fim, sem tocar nos existentes.
    """
    versao_antes = doc.versao_template
    repertorio = doc.repertorio()
    grupo_existente = localizar_musica(repertorio, pedido.titulo)
    if substituir and grupo_existente is None:
        raise Inconsistencia(f'"{pedido.titulo}" não existe no repertório; use inclusão')
    if not substituir and grupo_existente is not None:
        raise Inconsistencia(f'"{pedido.titulo}" já existe no repertório; use substituição')

    grupo = grupo_existente or slug(pedido.titulo)
    musica = repertorio.musica(grupo) if grupo_existente else None
    titulo = musica.titulo if musica else pedido.titulo
    secoes_antigas: list[Secao] = []
    if musica:
        secoes_antigas = [s for s in doc.secoes if s.attrs.get("id") in musica.paginas]

    total = len(pedido.imagens)
    ids = list(musica.paginas[:total]) if musica else []
    ids += _proximos_ids(doc, total - len(ids), ids)
    destino = "#" + repertorio.pagina_inicial

    # Modo do grupo: overlay continua overlay, raw-score continua raw-score (LAY-06).
    modo_overlay = all(s.overlay for s in secoes_antigas) if secoes_antigas else doc.usa_overlay

    imagens = [data_uri(p) for p in pedido.imagens]
    blocos = []
    for i, (uri, dados) in enumerate(imagens, start=1):
        if modo_overlay:
            esquerda_titulo, esquerda_abc = posicoes(dados, render.rotulo_pagina(titulo, i, total))
            blocos.append(
                render.secao_overlay(
                    titulo, grupo, i, total, ids[i - 1], uri, destino, esquerda_titulo, esquerda_abc
                )
            )
        else:
            blocos.append(
                render.secao_raw_score(
                    titulo, grupo, i, total, ids[i - 1], uri, destino, doc.usa_overlay
                )
            )
    # O bloco gerado segue a quebra de linha do arquivo (CRLF ou LF).
    novo_bloco = "".join(blocos).replace("\n", doc.quebra_de_linha)

    if secoes_antigas:
        inicio, fim = secoes_antigas[0].inicio, secoes_antigas[-1].fim
        intermediarias = [
            s
            for s in doc.secoes
            if inicio <= s.inicio < fim and s.attrs.get("id") not in musica.paginas
        ]
        if intermediarias:
            raise Inconsistencia(
                f'as páginas de "{titulo}" não são contíguas; edição bloqueada (MUS-04)'
            )
        novo = doc.substituir(inicio, fim, novo_bloco)
        acao = "alterada"
    else:
        texto_baixo = doc.texto.lower()
        pos = texto_baixo.rfind("</main>")
        if pos < 0:
            pos = texto_baixo.rfind("</body>")
        if pos < 0:
            raise Inconsistencia("HTML sem </main> nem </body>; não sei onde incluir a música")
        novo = doc.substituir(pos, pos, novo_bloco)
        acao = "adicionada"

    if not modo_overlay:
        novo = _garantir_css_score_native(novo)
    novo, rel_setlist = reconstruir_setlist(novo)
    novo = reconstruir_indice(novo)

    relatorio = RelatorioMusica(
        acao=acao,
        musica=titulo,
        grupo=grupo,
        partes=total,
        ids=ids,
        modo="overlay" if modo_overlay else "raw-score",
        imagens_entrada_sha256=[sha256(d) for _, d in imagens],
        imagens_incorporadas_sha256=[],
        setlist=rel_setlist,
        indice_regenerado=novo.secao(Papel.INDICE) is not None,
    )
    relatorio.imagens_incorporadas_sha256 = validar_edicao_musica(
        doc, novo, grupo, total, relatorio.imagens_entrada_sha256, versao_antes
    )
    return novo, relatorio


def validar_edicao_musica(
    antes: Documento,
    depois: Documento,
    grupo: str,
    total: int,
    hashes_entrada: list[str],
    versao_antes: int | None,
) -> list[str]:
    """Validações da edição (VAL-06, MUS-07, EST-03). Devolve os SHA-256 incorporados."""
    repertorio = depois.repertorio()  # IDs únicos, partes 1..N, grupos contíguos
    musica = repertorio.musica(grupo)
    if musica is None or len(musica.paginas) != total:
        raise Inconsistencia(f"grupo {grupo}: esperado {total} páginas no candidato")
    secoes = [depois.secao_por_id(i) for i in musica.paginas]
    for s in secoes:
        problemas = problemas_pagina_partitura(s)
        if problemas:
            raise Inconsistencia(f"{s.attrs.get('id')}: " + "; ".join(problemas))
    incorporados = [sha256_imagem_incorporada(s.texto) for s in secoes]
    if incorporados != hashes_entrada:
        raise Inconsistencia(
            "SHA-256 das imagens incorporadas difere das imagens de entrada (MUS-07)"
        )
    if depois.versao_template != versao_antes:
        raise Inconsistencia("a edição de música mudou a versão de template (HTML-10)")
    grupos_antes = [m.grupo for m in antes.repertorio().musicas]
    grupos_depois = [m.grupo for m in repertorio.musicas]
    if [g for g in grupos_antes if g != grupo] != [g for g in grupos_depois if g != grupo]:
        raise Inconsistencia("a edição alterou a ordem ou o conjunto de outras músicas (MUS-04)")
    return incorporados


def problemas_pagina_partitura(secao: Secao) -> list[str]:
    """Título e `ABC` visíveis, imagem incorporada e área conforme o modo.

    EST-03, LAY-02 e LAY-04.
    """
    texto = secao.texto
    compacto = texto.replace(" ", "").lower()
    problemas = []
    if secao.overlay:
        exigidos = ("score-header-overlay", "score-title-overlay", "score-abc-overlay")
        problemas += [f"falta {c}" for c in exigidos if c not in compacto]
        if "clip-path" in compacto:
            problemas.append("imagem overlay com clip-path")
    else:
        if "object-fit:fill" not in compacto:
            problemas.append("imagem não preenche a área abaixo do cabeçalho")
        problemas += [f"falta {c}" for c in ("score-title", "score-abc") if c not in compacto]
    if ">abc</a>" not in compacto:
        problemas.append("ABC não visível")
    titulo = re.search(r'class="score-title(?:-overlay)?"[^>]*>([^<]+)</a>', texto)
    if not titulo or not titulo.group(1).strip():
        problemas.append("título não visível")
    if not _DATA_URI.search(texto):
        problemas.append("imagem não incorporada")
    return problemas


__all__ = [
    "PedidoMusica",
    "RelatorioMusica",
    "RelatorioSetlist",
    "gravar_musica",
    "gravar_versao_template",
    "reconstruir_indice",
    "reconstruir_setlist",
]
