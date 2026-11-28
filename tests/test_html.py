from __future__ import annotations

import hashlib
import re

import pytest
from conftest import construir_html, png

from partituras.dominio.erros import Ambiguidade, Inconsistencia
from partituras.dominio.modelos import Papel
from partituras.html import escopo
from partituras.html.documento import Documento
from partituras.html.edicao import (
    PedidoMusica,
    gravar_musica,
    gravar_versao_template,
    ordenar_pelo_setlist,
    reconstruir_indice,
    reconstruir_setlist,
    sha256_imagem_incorporada,
)
from partituras.html.overlay import posicoes

# --- Documento e estrutura -------------------------------------------------------------------


@pytest.mark.parametrize("quebra", ["\n", "\r\n"])
def test_leitura_e_gravacao_preservam_bytes(quebra):
    """HTML-09."""
    dados = construir_html(quebra=quebra)
    assert Documento.de_bytes(dados).para_bytes() == dados


def test_estrutura_lida_dos_atributos(html_basico):
    """EST-04: o texto visível diferente de data-song não muda a estrutura."""
    texto = html_basico.texto.replace(">Simmer Down</a>", ">Outro Nome</a>", 1)
    musicas = [m.titulo for m in Documento(texto).repertorio().musicas]
    assert "Simmer Down" in musicas
    assert "Outro Nome" not in musicas


def test_papeis_das_secoes():
    """EST-05 e EST-06."""
    doc = Documento.de_bytes(construir_html(auxiliar=True))
    papeis = [s.papel for s in doc.secoes]
    assert papeis[:2] == [Papel.SETLIST, Papel.INDICE]
    assert papeis[-1] is Papel.AUXILIAR
    assert doc.secoes[0].attrs["id"] == "setlist"


def test_versao_de_template_gravada_no_arquivo():
    """HTML-02."""
    doc = Documento.de_bytes(construir_html(versao=None))
    assert doc.versao_template is None
    gravado = gravar_versao_template(doc, 6)
    assert gravado.versao_template == 6
    assert '<meta content="06" name="partituras-template-version"/>' in gravado.texto
    assert gravar_versao_template(gravado, 7).versao_template == 7
    assert gravado.texto.count("partituras-template-version") == 1


# --- Índice ---------------------------------------------------------------------------------


def _celulas_indice(doc: Documento) -> list[list[str]]:
    corpo = doc.secao(Papel.INDICE).corpo
    linhas = re.findall(r"<tr>(.*?)</tr>", corpo)
    return [re.findall(r"<td>(?:<a[^>]*>([^<]*)</a>)?</td>", linha) for linha in linhas]


def test_indice_em_tres_colunas_reais_coluna_a_coluna(html_basico):
    """IDX-04 e MUS-08: tabela real de 3 colunas, preenchida coluna a coluna."""
    celulas = _celulas_indice(html_basico)
    assert all(len(linha) == 3 for linha in celulas)
    colunas = [[linha[c] for linha in celulas if linha[c]] for c in range(3)]
    assert colunas == [
        ["Coisa Nº 5", "Garden of Love"],
        ["Simmer Down", "Ska Paralamas"],
        ["Skaravan"],
    ]


def test_indice_regenerado_e_idempotente(html_basico):
    assert reconstruir_indice(html_basico).texto == html_basico.texto


def test_indice_aponta_para_primeira_pagina(html_basico):
    corpo = html_basico.secao(Papel.INDICE).corpo
    assert 'data-index-group="garden-of-love" href="#slide-4"' in corpo


# --- Set list -------------------------------------------------------------------------------


def test_setlist_em_texto_real_com_links(html_basico):
    """SET-02 e SET-03."""
    corpo = html_basico.secao(Papel.SETLIST).corpo
    assert "<img" not in corpo
    assert (
        '<li data-setlist-pos="1"><a data-setlist-pos="1" data-setlist-group="garden-of-love" '
        'href="#slide-4" title="Garden of Love">Garden of Love</a></li>'
    ) in corpo


def test_setlist_segue_a_ordem_informada(html_basico):
    """SET-06."""
    titulos = ["Simmer Down", "Coisa Nº 5", "Skaravan", "Simmer Down"]
    novo, rel = reconstruir_setlist(html_basico, titulos)
    itens = novo.itens_setlist()
    assert [i.titulo for i in itens] == titulos
    assert [i.posicao for i in itens] == [1, 2, 3, 4]
    assert rel.links == 4


def test_setlist_sem_partitura_fica_visivel_sem_link(html_basico):
    """SET-09."""
    novo, rel = reconstruir_setlist(html_basico, ["Garden of Love", "Música Inédita"])
    corpo = novo.secao(Papel.SETLIST).corpo
    assert '<span class="setlist-missing" data-setlist-pos="2" title="Música Inédita">' in corpo
    assert rel.ausentes == [{"posicao": 2, "titulo": "Música Inédita"}]


def test_setlist_ambiguo_interrompe():
    """NOM-04: nenhuma escolha silenciosa."""
    doc = Documento.de_bytes(
        construir_html(musicas=[("Festa no Mar", 1), ("Festa no Bar", 1)], setlist=["Festa no Mar"])
    )
    with pytest.raises(Ambiguidade):
        reconstruir_setlist(doc, ["Festa no Par"])


def test_sem_setlist_pagina_inicial_e_indice():
    """SET-08: sem set list, retornos vão para o índice e nada é inventado."""
    doc = Documento.de_bytes(construir_html(setlist=None))
    assert doc.repertorio().setlist is None
    assert doc.repertorio().pagina_inicial == "index"
    assert 'href="#index"' in doc.secoes[1].texto
    novo, rel = reconstruir_setlist(doc)
    assert novo.texto == doc.texto and rel.itens == 0


# --- Música ---------------------------------------------------------------------------------


def test_pedido_exige_fanfarra_nome_e_imagens(tmp_path):
    """MUS-01."""
    with pytest.raises(Inconsistencia):
        PedidoMusica("Skaravana", "Nova", ())
    with pytest.raises(Inconsistencia):
        PedidoMusica("", "Nova", (tmp_path / "a.png",))


def test_inclusao_adiciona_grupo_sem_remover_nenhum(html_basico, imagens):
    """MUS-03, MUS-05, MUS-06, MUS-07, MUS-08 e LAY-03."""
    antes = [m.grupo for m in html_basico.repertorio().musicas]
    novo, rel = gravar_musica(
        html_basico,
        PedidoMusica("X", "Música Nova", imagens((1, 2, 3), (4, 5, 6))),
        substituir=False,
    )
    depois = novo.repertorio()
    assert [m.grupo for m in depois.musicas] == [*antes, "musica-nova"]
    assert rel.acao == "adicionada"
    assert rel.ids == ["slide-9", "slide-10"]
    assert rel.imagens_entrada_sha256 == rel.imagens_incorporadas_sha256
    secao = novo.secao_por_id("slide-9").texto
    assert "data:image/png;base64," in secao
    assert ">Música Nova (1 de 2)</a>" in secao
    assert ">ABC</a>" in novo.secao_por_id("slide-10").texto
    assert "Música Nova" in novo.secao(Papel.INDICE).corpo


def test_inclusao_de_musica_existente_e_bloqueada(html_basico, imagens):
    with pytest.raises(Inconsistencia, match="já existe"):
        gravar_musica(html_basico, PedidoMusica("X", "simmer down", imagens((1, 1, 1))), False)


def test_troca_substitui_so_o_grupo_e_reaproveita_ids(html_basico, imagens):
    """MUS-02, MUS-03, MUS-04 e MUS-05."""
    novo, rel = gravar_musica(
        html_basico, PedidoMusica("X", "garden of love", imagens((9, 9, 9))), substituir=True
    )
    assert rel.acao == "alterada" and rel.ids == ["slide-4"]
    assert rel.musica == "Garden of Love"
    garden = novo.repertorio().musica("garden-of-love")
    assert garden.paginas == ("slide-4",)
    for id_ in ("slide-3", "slide-6", "slide-7", "slide-8"):
        assert novo.secao_por_id(id_).texto == html_basico.secao_por_id(id_).texto


def test_troca_de_musica_inexistente_e_bloqueada(html_basico, imagens):
    with pytest.raises(Inconsistencia, match="não existe"):
        gravar_musica(html_basico, PedidoMusica("X", "Inexistente", imagens((1, 1, 1))), True)


def test_troca_preserva_bytes_fora_do_grupo_com_crlf(imagens):
    """HTML-09: CRLF preservado, inclusive no bloco gerado."""
    doc = Documento.de_bytes(construir_html(quebra="\r\n"))
    novo, _ = gravar_musica(doc, PedidoMusica("X", "Simmer Down", imagens((7, 7, 7))), True)
    dados = novo.para_bytes()
    assert dados.count(b"\n") == dados.count(b"\r\n")
    antes = doc.secao_por_id("slide-8")
    assert dados.startswith(doc.texto[: antes.inicio].encode())


def test_raw_score_preenche_area_abaixo_do_cabecalho(html_basico, imagens):
    """LAY-01 e LAY-02."""
    novo, rel = gravar_musica(html_basico, PedidoMusica("X", "Nova", imagens((1, 1, 1))), False)
    secao = novo.secao_por_id(rel.ids[0]).texto
    assert rel.modo == "raw-score"
    assert "width:100%;height:100%;object-fit:fill" in secao
    assert secao.index('class="score-header"') < secao.index('class="score-image"')
    assert "justify-self:center" in secao and "justify-self:end" in secao


def test_overlay_imagem_inteira_e_cabecalho_transparente(imagens):
    """LAY-04."""
    doc = Documento.de_bytes(construir_html(overlay=True))
    novo, rel = gravar_musica(doc, PedidoMusica("X", "Nova", imagens((1, 1, 1))), False)
    secao = novo.secao_por_id(rel.ids[0]).texto
    assert rel.modo == "overlay"
    assert 'class="score-header-overlay"' in secao
    assert "clip-path" not in secao and "object-fit" not in secao


def test_imagem_recebida_entra_sem_alteracao_de_pixels(imagens):
    """LAY-05: o código não limpa nem altera a imagem; os bytes entram como vieram."""
    doc = Documento.de_bytes(construir_html(overlay=True))
    arquivos = imagens((1, 1, 1))
    novo, rel = gravar_musica(doc, PedidoMusica("X", "Nova", arquivos), False)
    secao = novo.secao_por_id(rel.ids[0]).texto
    assert sha256_imagem_incorporada(secao) == hashlib.sha256(arquivos[0].read_bytes()).hexdigest()


def test_modo_do_grupo_e_preservado(imagens):
    """LAY-06: raw-score num HTML overlay continua raw-score, com fontes aprovadas."""
    doc = Documento.de_bytes(construir_html(overlay=False))
    meta_overlay = '<meta content="score-overlay-header-v2" name="partituras-score-template"/>'
    texto = doc.texto.replace('<meta charset="utf-8"/>', '<meta charset="utf-8"/>' + meta_overlay)
    doc = Documento(texto)
    novo, rel = gravar_musica(doc, PedidoMusica("X", "Simmer Down", imagens((1, 1, 1))), True)
    secao = novo.secao_por_id(rel.ids[0]).texto
    assert rel.modo == "raw-score"
    assert "font-size:17px" in secao and "font-size:14px" in secao


def test_overlay_escolhe_posicao_sem_tinta():
    """LAY-06: título sai do centro quando há tinta no meio da faixa do cabeçalho."""
    livre = posicoes(png(tamanho=(880, 650)), "Título")
    assert livre == (50.0, 91.5)
    com_tinta = posicoes(png(tamanho=(880, 650), tinta_topo=(35, 65)), "Título")
    assert com_tinta[0] != 50.0


def test_edicao_nao_muda_versao_de_template(html_basico, imagens):
    """HTML-04 e HTML-10."""
    novo, _ = gravar_musica(html_basico, PedidoMusica("X", "Nova", imagens((1, 1, 1))), False)
    assert novo.versao_template == html_basico.versao_template == 3


def test_edicao_gera_candidato_sem_alterar_o_original(html_basico, imagens):
    """HTML-07: a edição devolve um novo documento; o original continua igual."""
    original = html_basico.texto
    gravar_musica(html_basico, PedidoMusica("X", "Nova", imagens((1, 1, 1))), False)
    assert html_basico.texto == original


def test_html_canonico_continua_com_o_mesmo_nome(tmp_path, imagens):
    """HTML-08: em alteração de conteúdo, o candidato substitui o mesmo arquivo."""
    from partituras.dominio.versoes import nome_html

    destino = tmp_path / nome_html("Skaravana")
    destino.write_bytes(construir_html())
    doc = Documento.de_bytes(destino.read_bytes())
    novo, _ = gravar_musica(doc, PedidoMusica("Skaravana", "Nova", imagens((1, 1, 1))), False)
    destino.write_bytes(novo.para_bytes())
    assert sorted(p.name for p in tmp_path.iterdir() if p.suffix == ".html") == ["Skaravana.html"]


def test_validacao_detecta_imagem_trocada(html_basico, imagens, monkeypatch):
    """MUS-07 e VAL-06: SHA-256 da imagem incorporada precisa ser o da entrada."""
    from partituras.html import edicao

    original = edicao.data_uri

    def adulterado(caminho):
        uri, dados = original(caminho)
        return uri, dados + b"x"

    monkeypatch.setattr(edicao, "data_uri", adulterado)
    with pytest.raises(Inconsistencia, match="SHA-256"):
        gravar_musica(html_basico, PedidoMusica("X", "Nova", imagens((1, 1, 1))), False)


def test_validacao_detecta_pagina_sem_abc(html_basico, imagens, monkeypatch):
    """EST-03 e VAL-06."""
    from partituras.html import render

    original = render.secao_raw_score
    monkeypatch.setattr(
        render, "secao_raw_score", lambda *a, **k: original(*a, **k).replace(">ABC</a>", "></a>")
    )
    with pytest.raises(Inconsistencia, match="ABC"):
        gravar_musica(html_basico, PedidoMusica("X", "Nova", imagens((1, 1, 1))), False)


def test_grupo_nao_contiguo_bloqueia_edicao(imagens):
    """MUS-04."""
    doc = Documento.de_bytes(construir_html(musicas=[("Alfa", 2), ("Beta", 1)], setlist=None))
    alfa2 = doc.secao_por_id("slide-4")
    beta = doc.secao_por_id("slide-5")
    texto = (
        doc.texto[: alfa2.inicio]
        + beta.texto
        + doc.texto[alfa2.fim : beta.inicio]
        + alfa2.texto
        + doc.texto[beta.fim :]
    )
    with pytest.raises(Inconsistencia, match="não consecutivas"):
        gravar_musica(Documento(texto), PedidoMusica("X", "Alfa", imagens((1, 1, 1))), True)


def test_css_da_pagina_raw_score_incluido_quando_falta(imagens):
    """O CSS mínimo da página raw-score entra uma vez, seguindo a quebra de linha do arquivo."""
    dados = construir_html(quebra="\r\n").replace(
        b"/* score-native-layout-v1 */\r\n.score-native{display:flex;flex-direction:column}\r\n",
        b"",
    )
    doc = Documento.de_bytes(dados)
    assert ".score-native{" not in doc.texto
    novo, _ = gravar_musica(doc, PedidoMusica("X", "Nova", imagens((1, 1, 1))), False)
    assert novo.texto.count("/* score-native-layout-v1 */") == 1
    novo2, _ = gravar_musica(novo, PedidoMusica("X", "Outra", imagens((2, 2, 2))), False)
    assert novo2.texto.count("/* score-native-layout-v1 */") == 1
    assert novo2.para_bytes().count(b"\n") == novo2.para_bytes().count(b"\r\n")


def test_css_raw_score_existente_sem_marcador_nao_duplica(imagens):
    """VAL-04: HTML que já tem a regra `.score-native{...}` sem o comentário-marcador
    (caso do Fanfarock) não ganha cópia do CSS; o <head> fica igual e o gate de escopo passa."""
    dados = construir_html(quebra="\r\n").replace(b"/* score-native-layout-v1 */\r\n", b"")
    doc = Documento.de_bytes(dados)
    assert ".score-native{" in doc.texto.replace(" ", "")
    cabeca = doc.texto[: doc.texto.lower().find("</head>")]
    novo, rel = gravar_musica(doc, PedidoMusica("X", "Simmer Down", imagens((3, 3, 3))), True)
    assert novo.texto[: novo.texto.lower().find("</head>")] == cabeca
    assert "/* score-native-layout-v1 */" not in novo.texto
    escopo.exigir(doc, novo, rel.grupo)


def test_troca_desempata_titulos_com_parenteses(imagens):
    """MUS-02: "Coração Partido" e "Coração Partido (graus)" são músicas distintas."""
    doc = Documento.de_bytes(
        construir_html(
            musicas=[("Coração Partido", 1), ("Coração Partido (graus)", 1)], setlist=None
        )
    )
    novo, rel = gravar_musica(doc, PedidoMusica("X", "Coração Partido", imagens((3, 3, 3))), True)
    assert rel.grupo == "coracao-partido"
    _, rel = gravar_musica(
        doc, PedidoMusica("X", "Coração Partido (graus)", imagens((4, 4, 4))), True
    )
    assert rel.grupo == "coracao-partido-graus"


# --- Ordem do set list (SET-10) ----------------------------------------------------------------


def _ordem(doc: Documento) -> list[str]:
    return [s.attrs.get("data-group") or s.attrs.get("id") for s in doc.secoes]


def test_html_fica_na_ordem_do_setlist():
    """SET-10: set list, índice, músicas do set list, as demais na ordem anterior, auxiliares."""
    doc = Documento.de_bytes(construir_html(setlist=["Skaravan", "Garden of Love"], auxiliar=True))
    assert _ordem(doc) == [
        "setlist", "index",
        "skaravan", "garden-of-love", "garden-of-love",
        "coisa-no-5", "ska-paralamas", "simmer-down",
        "slide-9",
    ]  # fmt: skip
    novo, _ = reconstruir_setlist(doc, ["Simmer Down", "Coisa Nº 5"])
    assert _ordem(novo)[2:5] == ["simmer-down", "coisa-no-5", "skaravan"]
    assert _ordem(novo)[-1] == "slide-9"


def test_ordenar_html_antigo_so_move_paginas_inteiras():
    """SET-10 e HTML-09: IDs, páginas e bytes fora delas não mudam; CRLF preservado."""
    dados = construir_html(quebra="\r\n", auxiliar=True, ordenar=False)
    antigo = Documento.de_bytes(dados)
    assert _ordem(antigo)[2] == "coisa-no-5"
    novo = ordenar_pelo_setlist(antigo)
    assert _ordem(novo)[2:5] == ["garden-of-love", "garden-of-love", "ska-paralamas"]
    assert sorted(s.texto for s in novo.secoes) == sorted(s.texto for s in antigo.secoes)
    a, n = antigo.secoes, novo.secoes
    assert antigo.texto[: a[0].inicio] == novo.texto[: n[0].inicio]
    assert antigo.texto[a[-1].fim :] == novo.texto[n[-1].fim :]
    assert novo.para_bytes().count(b"\n") == novo.para_bytes().count(b"\r\n")
    assert novo.repertorio().setlist == antigo.repertorio().setlist
    assert ordenar_pelo_setlist(novo).texto == novo.texto


def test_ordem_com_repeticao_e_musica_sem_partitura():
    """SET-10 com SET-05 e SET-09: páginas uma vez só, pela primeira ocorrência."""
    doc = Documento.de_bytes(
        construir_html(setlist=["Simmer Down", "Inédita", "Skaravan", "Simmer Down"])
    )
    assert _ordem(doc)[2:4] == ["simmer-down", "skaravan"]
    assert _ordem(doc).count("simmer-down") == 1


def test_sem_setlist_a_ordem_nao_muda():
    """SET-08: sem set list não há ordem a impor."""
    doc = Documento.de_bytes(construir_html(setlist=None))
    assert ordenar_pelo_setlist(doc).texto == doc.texto


def test_conteudo_entre_paginas_bloqueia_reordenacao():
    """HTML-09: reordenar não pode carregar texto solto para outro lugar."""
    dados = construir_html(ordenar=False).replace(
        b'<section class="slide score-native', b'<p>solto</p><section class="slide score-native', 1
    )
    with pytest.raises(Inconsistencia, match="HTML-09"):
        ordenar_pelo_setlist(Documento.de_bytes(dados))


def test_inclusao_entra_na_posicao_do_setlist(imagens):
    """SET-10 e MUS-03: música do set list que ganha partitura vai para a posição dela."""
    doc = Documento.de_bytes(construir_html(setlist=["Skaravan", "Música Nova", "Simmer Down"]))
    novo, _ = gravar_musica(
        doc, PedidoMusica("X", "Música Nova", imagens((1, 2, 3))), substituir=False
    )
    assert _ordem(novo)[2:5] == ["skaravan", "musica-nova", "simmer-down"]
    item = novo.itens_setlist()[1]
    assert item.grupo == "musica-nova"


def test_troca_em_html_fora_de_ordem_deixa_na_ordem(imagens):
    """SET-10: a troca de música também corrige um HTML antigo fora da ordem."""
    antigo = Documento.de_bytes(construir_html(ordenar=False))
    novo, rel = gravar_musica(antigo, PedidoMusica("X", "Skaravan", imagens((5, 5, 5))), True)
    assert _ordem(novo)[2:5] == ["garden-of-love", "garden-of-love", "ska-paralamas"]
    assert rel.ids == ["slide-7"]
    for id_ in ("slide-3", "slide-4", "slide-5", "slide-6", "slide-8"):
        assert novo.secao_por_id(id_).texto == antigo.secao_por_id(id_).texto
