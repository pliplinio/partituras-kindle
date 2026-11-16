"""Relatório final e registro de histórico (REL-01 a REL-05, HIS-02, TMP-07).

`dados` é o estado acumulado da execução (dicionário simples, serializável).
Chaves usadas, todas opcionais: comando, operacao, fanfarra, musica, html,
html_sha256, versao_template, pdf, pdf_sha256, anterior, imagens, paginas,
sequencia, preservacao, setlist, indice, retornos, escopo, inspecao, drive,
kindle (dict de `Envio.como_dict`), pendencias, erro, processamento_ok.
"""

from __future__ import annotations

from partituras.dominio.tempo import INCOMPLETA, Cronometro

SUCESSO, FALHA = "SUCESSO", "FALHA"


def _s(segundos: float | None) -> str:
    if segundos is None:
        return "não medido"
    minutos, resto = divmod(segundos, 60)
    return f"{int(minutos)} min {resto:04.1f} s" if minutos else f"{resto:.1f} s"


def estados_finais(dados: dict, cronometro: Cronometro, etapas_obrigatorias: list[str]) -> dict:
    """Três estados finais, mantendo PDF e Kindle separados (REL-04, REL-05, TMP-07)."""
    processamento = SUCESSO if dados.get("processamento_ok") and not dados.get("erro") else FALHA
    kindle = (dados.get("kindle") or {}).get("status", "FALHA")
    if kindle == "NAO_SOLICITADO":
        kindle_final = "NAO_SOLICITADO"
    else:
        kindle_final = kindle if kindle in ("SUCESSO", "BLOQUEADO") else FALHA
    motivos = []
    if processamento != SUCESSO:
        motivos.append("processamento do PDF")
    if kindle_final not in (SUCESSO, "NAO_SOLICITADO"):
        motivos.append("envio ao Kindle")
    nao_feitas = [
        e
        for e in etapas_obrigatorias
        if e not in cronometro.etapas or cronometro.etapas[e].resultado != SUCESSO
    ]
    if nao_feitas:
        motivos.append(f"etapas não concluídas: {', '.join(nao_feitas)}")
    if cronometro.problemas() or cronometro.total is None:
        motivos.append(INCOMPLETA)
    return {
        "processamento_pdf": processamento,
        "envio_kindle": kindle_final,
        "status_final": SUCESSO if not motivos else FALHA,
        "motivos_falha": motivos,
    }


def montar(dados: dict, cronometro: Cronometro, etapas_obrigatorias: list[str]) -> str:
    """Texto do relatório na ordem de REL-02, terminando com as três linhas de REL-04."""
    c = cronometro
    estados = estados_finais(dados, c, etapas_obrigatorias)
    linhas = []
    if c.request_received_at is None:  # REL-03
        linhas.append(
            "Tempo medido desde o início do atendimento (horário do pedido não disponível)."
        )
        linhas.append("Tempo percebido pelo usuário: não medido")
    else:
        linhas.append(f"Tempo percebido pelo usuário: {_s(c.tempo_percebido)}")
    linhas += [
        f"Tempo do atendimento: {_s(c.total)}",
        f"Início/fim: {c.como_dict()['workflow_started_at_utc']} → "
        f"{c.como_dict()['workflow_finished_at_utc'] or 'não registrado'}",
        f"Tempo do núcleo: {_s(dados.get('tempo_nucleo_s'))}",
        f"Fanfarra/música: {dados.get('fanfarra', '—')} / {dados.get('musica') or '—'}",
        f"HTML: {dados.get('html', '—')} (template v{dados.get('versao_template', 0):02d})",
        f"PDF: {dados.get('pdf', '—')}",
        f"SHA-256: {dados.get('pdf_sha256', '—')}",
        f"Imagens: {dados.get('imagens', '—')}",
        f"Páginas/preservação/sequência: {dados.get('paginas', '—')} / "
        f"{dados.get('preservacao', '—')} / {dados.get('sequencia', '—')}",
        f"Set list/índice/retornos: {dados.get('setlist', '—')} / "
        f"{dados.get('indice', '—')} / {dados.get('retornos', '—')}",
        f"Fingerprint/inspeção: {dados.get('inspecao', '—')}",
        f"Drive/Kindle: {dados.get('drive', '—')} / "
        f"{(dados.get('kindle') or {}).get('status', '—')}",
        "Tempos por etapa:",
    ]
    for e in c.etapas.values():
        linhas.append(f"  - {e.nome}: {_s(e.duracao)} ({e.resultado}, {e.tentativas}x)")
    pendencias = list(dados.get("pendencias") or [])
    if dados.get("erro"):
        pendencias.insert(0, f"erro: {dados['erro']}")
    pendencias += [m for m in estados["motivos_falha"] if m == INCOMPLETA]
    linhas.append("Pendências: " + ("; ".join(pendencias) if pendencias else "nenhuma"))
    linhas += [
        f"PROCESSAMENTO DO PDF: {estados['processamento_pdf']}",
        f"ENVIO AO KINDLE: {estados['envio_kindle']}",
        f"STATUS FINAL: {estados['status_final']}",
    ]
    return "\n".join(linhas)


def registro_historico(
    dados: dict,
    cronometro: Cronometro,
    etapas_obrigatorias: list[str],
    versao_codigo: str,
    sha_codigo: str,
) -> dict:
    """Linha do histórico, gravada inclusive em falha (HIS-02)."""
    campos = (
        "comando", "operacao", "fanfarra", "musica", "versao_template", "html", "html_sha256",
        "pdf", "pdf_sha256", "anterior", "escopo", "inspecao", "kindle", "erro",
    )  # fmt: skip
    return {
        **{k: dados.get(k) for k in campos},
        "tempo": cronometro.como_dict(),
        "versao_codigo": versao_codigo,
        "sha_codigo": sha_codigo,
        "paginas_inspecionadas": dados.get("paginas_inspecionadas", []),
        "paginas_reutilizadas": dados.get("paginas_reutilizadas", []),
        "estados": estados_finais(dados, cronometro, etapas_obrigatorias),
    }
