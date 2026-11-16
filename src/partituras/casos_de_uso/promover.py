"""Promoção do resultado aprovado para a pasta operacional (PRO-01 a PRO-05).

Ordem: guardar bytes e SHA-256 originais do HTML → gravar o HTML → confirmar
SHA-256 → gravar o PDF como arquivo novo → confirmar nome, versão, pasta, ID e
SHA-256 → gravar manifesto aprovado. Só depois disso o Kindle pode ser acionado.
Se o PDF falhar depois do HTML, o HTML original é restaurado e conferido.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

from partituras.dominio.erros import Bloqueio
from partituras.dominio.execucao import Arquivo, Pasta, PlanoExecucao, manifesto_de, sha256


@dataclass
class ResultadoPromocao:
    html: Arquivo | None = None
    html_sha256: str | None = None
    pdf: Arquivo | None = None
    pdf_sha256: str | None = None
    manifesto: Arquivo | None = None
    restaurado: bool = False
    operacoes: list[dict] = field(default_factory=list)

    def como_dict(self) -> dict:
        return {
            "html": self.html.nome if self.html else None,
            "html_id": self.html.id if self.html else None,
            "html_sha256": self.html_sha256,
            "pdf": self.pdf.nome if self.pdf else None,
            "pdf_id": self.pdf.id if self.pdf else None,
            "pdf_sha256": self.pdf_sha256,
            "manifesto": self.manifesto.nome if self.manifesto else None,
            "html_restaurado": self.restaurado,
            "operacoes": self.operacoes,
        }


def _conferir(pasta: Pasta, nome: str, esperado: str, o_que: str) -> str:
    lido = sha256(pasta.ler(nome))
    if lido != esperado:
        raise Bloqueio(f"{o_que} gravado com SHA-256 {lido[:12]}…, esperado {esperado[:12]}…")
    return lido


def promover(
    pasta: Pasta,
    plano: PlanoExecucao,
    html_novo: bytes,
    pdf: bytes,
    sha256_inspecionado: str,
    manifesto_aprovado: dict,
) -> ResultadoPromocao:
    """Grava exatamente os bytes inspecionados (PRO-01), na ordem de PRO-03."""
    r = ResultadoPromocao()

    def registrar(operacao: str, resultado: str, mensagem: str = "") -> None:
        r.operacoes.append({"operacao": operacao, "resultado": resultado, "mensagem": mensagem})

    if sha256(pdf) != sha256_inspecionado:  # PRO-02
        registrar("conferir_sha_pdf", "FALHA", "bytes diferentes do inspecionado")
        raise Bloqueio("PDF a promover difere do SHA-256 inspecionado")
    if manifesto_aprovado.get("pdf_sha256") != sha256_inspecionado:
        raise Bloqueio("manifesto aprovado não corresponde ao PDF inspecionado")

    original = pasta.ler(plano.html)
    if sha256(original) != plano.html_sha256:
        raise Bloqueio("o HTML mudou na pasta desde o início da execução; reiniciar")

    html_sha = sha256(html_novo)
    if html_sha != plano.html_sha256:
        r.html = pasta.gravar(plano.html, html_novo, novo=False)
        if r.html.id != plano.html_id:
            raise Bloqueio("o HTML ganhou outro ID; deveria manter o mesmo arquivo (HTML-08)")
        r.html_sha256 = _conferir(pasta, plano.html, html_sha, "HTML")
        registrar("gravar_html", "SUCESSO")
    else:
        r.html = Arquivo(plano.html, plano.html_id)
        r.html_sha256 = html_sha
        registrar("gravar_html", "INALTERADO")

    try:
        if sha256(pdf) != sha256_inspecionado:  # PRO-02, imediatamente antes de gravar
            raise Bloqueio("PDF mudou antes da gravação")
        r.pdf = pasta.gravar(plano.nome_pdf, pdf, novo=True)
        if r.pdf.nome != plano.nome_pdf:
            raise Bloqueio(f"PDF gravado como {r.pdf.nome}, esperado {plano.nome_pdf}")
        r.pdf_sha256 = _conferir(pasta, plano.nome_pdf, sha256_inspecionado, "PDF")
        registrar("gravar_pdf", "SUCESSO")
    except Exception as exc:
        registrar("gravar_pdf", "FALHA", str(exc))
        if r.html_sha256 != plano.html_sha256:  # PRO-04
            pasta.gravar(plano.html, original, novo=False)
            _conferir(pasta, plano.html, plano.html_sha256, "HTML restaurado")
            r.restaurado = True
            registrar("restaurar_html", "SUCESSO")
        raise

    dados = json.dumps(manifesto_aprovado, ensure_ascii=False, indent=1).encode("utf-8")
    r.manifesto = pasta.gravar(manifesto_de(plano.nome_pdf), dados, novo=True)
    registrar("gravar_manifesto", "SUCESSO")
    return r
