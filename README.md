# Organizador de Partituras para Kindle (versão Claude)

Gera, a partir de um HTML canônico por fanfarra, o PDF navegável que vai para o
Kindle: set list, índice em três colunas e partituras com links de retorno.

Esta é a reescrita feita com o Claude. A versão ChatGPT continua no repositório
`pliplinio/org_partituras` e na pasta `Partituras_kindle`; as duas não
compartilham arquivos.

## Documentos

- [`REGRAS.md`](REGRAS.md): regras de negócio numeradas. É a referência de comportamento.
- [`CLAUDE.md`](CLAUDE.md): o que é específico de operar este projeto pelo Claude.
- [`tests/matriz_regras.yaml`](tests/matriz_regras.yaml): cada regra, a etapa em que precisa de teste e os testes que a cobrem.
- [`CHANGELOG.md`](CHANGELOG.md): mudanças por versão.

## Estrutura

```
src/partituras/
  dominio/       modelos, nomes, plano de sequência, versionamento (código puro)
  html/          leitura e edição do HTML canônico
  pdf/           conversão, materialização, links, gates, fingerprint
  adaptadores/   armazenamento, Kindle, relógio, histórico
  casos_de_uso/  um módulo por pedido do usuário
tests/
```

O teste `tests/test_projeto.py` impede que uma camada importe outra fora do
permitido.

## Desenvolvimento

```bash
python -m pip install -e ".[dev]"
ruff check . && ruff format --check .
pytest
```

## Etapas

| Etapa | Conteúdo | Situação |
| --- | --- | --- |
| 1 | Fundação: estrutura, CI, `REGRAS.md`, matriz regra → teste | em andamento |
| 2 | Domínio e HTML | — |
| 3 | PDF integral | — |
| 4 | Fingerprint e caminho rápido | — |
| 5 | Comandos `run`/`promote` e adaptadores | — |
| 6 | Piloto com as três fanfarras | — |
| 7 | Operação | — |

`etapa_atual` em `tests/matriz_regras.yaml` acompanha esta tabela: ao avançar,
todas as regras das etapas concluídas precisam ter teste.
