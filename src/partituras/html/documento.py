"""Leitura do HTML canônico, preservando os bytes (HTML-09, EST-01 a EST-06).

O documento é decodificado sem traduzir quebras de linha, de modo que
`Documento.de_bytes(b).para_bytes() == b`. Toda edição troca apenas um trecho
delimitado do texto; o restante continua idêntico, inclusive CRLF.
"""

from __future__ import annotations

import html
import re
from dataclasses import dataclass
from functools import cached_property

from partituras.dominio.erros import Inconsistencia
from partituras.dominio.modelos import ItemSetlist, Pagina, Papel, Repertorio
from partituras.dominio.repertorio import montar_repertorio

META_VERSAO = "partituras-template-version"
META_TEMPLATE_PARTITURA = "partituras-score-template"
TEMPLATE_OVERLAY = "score-overlay-header-v2"

_SECAO = re.compile(r"<section\b(?P<attrs>[^>]*)>(?P<corpo>.*?)</section>", re.I | re.S)
_ATRIBUTO = re.compile(r'([\w:-]+)\s*=\s*(?:"([^"]*)"|\'([^\']*)\')', re.S)
_META = re.compile(r"<meta\b[^>]*>", re.I)
_ITEM_SETLIST = re.compile(
    r"<(?P<tag>a|span)\b(?P<attrs>[^>]*\bdata-setlist-pos\s*=[^>]*)>(?P<corpo>.*?)</(?P=tag)>",
    re.I | re.S,
)
_TAGS = re.compile(r"<[^>]+>")


def atributos(trecho: str) -> dict[str, str]:
    """Atributos de uma tag de abertura, com entidades HTML decodificadas."""
    return {
        nome.lower(): html.unescape(duplas if duplas is not None else simples)
        for nome, duplas, simples in _ATRIBUTO.findall(trecho)
    }


def texto_visivel(trecho: str) -> str:
    return html.unescape(_TAGS.sub("", trecho)).strip()


@dataclass(frozen=True)
class Secao:
    inicio: int
    fim: int
    abertura: str
    corpo: str
    attrs: dict[str, str]

    @property
    def texto(self) -> str:
        return self.abertura + self.corpo + "</section>"

    @property
    def classes(self) -> list[str]:
        return self.attrs.get("class", "").split()

    @property
    def papel(self) -> Papel:
        """Set list, índice, partitura; qualquer outra `section.slide` é auxiliar (EST-06)."""
        valor = self.attrs.get("data-role", "").lower()
        if valor == "setlist":
            return Papel.SETLIST
        if valor == "index":
            return Papel.INDICE
        if valor == "score":
            return Papel.PARTITURA
        return Papel.AUXILIAR

    @property
    def overlay(self) -> bool:
        return "score-overlay-v2" in self.classes


def _inteiro(valor: str | None) -> int | None:
    if valor is None or not valor.strip().isdigit():
        return None
    return int(valor)


class Documento:
    def __init__(self, texto: str):
        self.texto = texto

    @classmethod
    def de_bytes(cls, dados: bytes) -> Documento:
        if dados.startswith(b"\xef\xbb\xbf"):
            raise Inconsistencia("HTML com BOM não é suportado; a gravação mudaria os bytes")
        return cls(dados.decode("utf-8"))

    def para_bytes(self) -> bytes:
        return self.texto.encode("utf-8")

    @property
    def quebra_de_linha(self) -> str:
        return "\r\n" if "\r\n" in self.texto else "\n"

    def substituir(self, inicio: int, fim: int, novo: str) -> Documento:
        return Documento(self.texto[:inicio] + novo + self.texto[fim:])

    # --- Estrutura -----------------------------------------------------------------------

    @cached_property
    def secoes(self) -> list[Secao]:
        """Todas as `section.slide`, na ordem do arquivo (EST-01)."""
        resultado = []
        for m in _SECAO.finditer(self.texto):
            attrs = atributos(m.group("attrs"))
            if "slide" not in attrs.get("class", "").split():
                continue
            abertura = self.texto[m.start() : m.start("corpo")]
            resultado.append(Secao(m.start(), m.end(), abertura, m.group("corpo"), attrs))
        return resultado

    def secao(self, papel: Papel) -> Secao | None:
        return next((s for s in self.secoes if s.papel is papel), None)

    def secao_por_id(self, id_: str) -> Secao | None:
        return next((s for s in self.secoes if s.attrs.get("id") == id_), None)

    def paginas(self) -> list[Pagina]:
        """Estrutura lida dos atributos `data-*`, nunca do texto visível (EST-04)."""
        return [
            Pagina(
                id=s.attrs.get("id", ""),
                papel=s.papel,
                musica=s.attrs.get("data-song"),
                grupo=s.attrs.get("data-group"),
                parte=_inteiro(s.attrs.get("data-part")),
                total_partes=_inteiro(s.attrs.get("data-total-parts")),
            )
            for s in self.secoes
        ]

    def itens_setlist(self) -> list[ItemSetlist] | None:
        """Itens declarados com `data-setlist-pos`, na ordem das posições (SET-03, SET-06)."""
        secao = self.secao(Papel.SETLIST)
        if secao is None:
            return None
        por_posicao: dict[int, ItemSetlist] = {}
        for m in _ITEM_SETLIST.finditer(secao.corpo):
            attrs = atributos(m.group("attrs"))
            posicao = _inteiro(attrs.get("data-setlist-pos"))
            if posicao is None or posicao in por_posicao:
                continue
            titulo = attrs.get("title") or texto_visivel(m.group("corpo"))
            grupo = attrs.get("data-setlist-group") if m.group("tag").lower() == "a" else None
            por_posicao[posicao] = ItemSetlist(posicao, titulo, grupo or None)
        return [por_posicao[p] for p in sorted(por_posicao)]

    def repertorio(self) -> Repertorio:
        return montar_repertorio(
            self.paginas(),
            self.itens_setlist(),
            tem_indice=self.secao(Papel.INDICE) is not None,
        )

    # --- Metadados ---------------------------------------------------------------------

    def meta(self, nome: str) -> str | None:
        for tag in _META.findall(self.texto):
            attrs = atributos(tag)
            if attrs.get("name", "").lower() == nome:
                return attrs.get("content")
        return None

    @property
    def versao_template(self) -> int | None:
        """Versão de template gravada no arquivo (HTML-02)."""
        valor = self.meta(META_VERSAO)
        return _inteiro(valor)

    @property
    def usa_overlay(self) -> bool:
        return self.meta(META_TEMPLATE_PARTITURA) == TEMPLATE_OVERLAY
