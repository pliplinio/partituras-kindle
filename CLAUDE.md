# CLAUDE.md

Instruções para o Claude ao trabalhar neste repositório.

## Antes de qualquer alteração

1. Ler `REGRAS.md` inteiro. Ele define o comportamento; o código o implementa.
2. Toda mudança de regra altera, no mesmo PR, `REGRAS.md`, `tests/matriz_regras.yaml` e os testes.
3. Rodar `ruff check .`, `ruff format --check .` e `pytest` antes de abrir PR.

## Pastas e arquivos

- Pasta operacional no computador do usuário: `G:\Meu Drive\Tuba\partituras_claude` (sincronizada com o Google Drive). Acessá-la pelas ferramentas do dispositivo conectado.
- HTMLs canônicos com nome fixo: `Xamego.html`, `Skaravana.html`, `Fanfarock.html`. A origem de cada um está em `ORIGEM_DA_COPIA.json`.
- Entradas dos testes: `partituras_claude/testes/golden_repertorio/`.
- Nunca gravar na pasta `G:\Meu Drive\Tuba\Partituras_kindle` nem no repositório `pliplinio/org_partituras`: pertencem à versão ChatGPT.

## Limites do ambiente que já causaram problemas

- **Gmail conectado:** cada chamada aceita no máximo 4,2 MB (cerca de 3,1 MB de anexo). Os PDFs têm de 4 a 5 MB. Envio direto e rascunho falham pelo mesmo limite. O caminho que funciona é o Gmail no navegador do app, botão "Inserir arquivos do Drive", opção **anexo** (nunca link). Testado em 15/11/2026.
- **Download do Drive pelo conector** devolve o arquivo em base64 no contexto: inviável para HTMLs de 5 a 7 MB. Ler e gravar pela pasta sincronizada.
- **Quebras de linha CRLF:** os HTMLs canônicos usam CRLF. Ler e gravar em bytes; `read_text`/`write_text` convertem as quebras e alteram o arquivo inteiro.
- **Conversão HTML → PDF:** WeasyPrint gerou 106 páginas em vez de 28 no Skaravana. Usar só Chromium headless com o tamanho de página do template.
- **Biblioteca Kindle:** a Amazon não sobrescreve documentos de mesmo nome. A limpeza de versões antigas é feita em `amazon.com.br`, página "Gerencie seu conteúdo e dispositivos", no navegador do app, com a lista confirmada pelo usuário antes de excluir.

## Convenções

- Código, nomes de módulos e mensagens em português.
- Uma branch por etapa ou mudança; PR com CI verde antes do merge em `main`.
- Não versionar PDFs, renders nem HTMLs de repertório real; eles ficam no Drive.
