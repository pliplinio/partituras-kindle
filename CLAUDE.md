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

## Como atender um pedido (operação)

O código exige Python 3.13 e roda neste ambiente (contêiner). A pasta `G:` não monta no
shell do dispositivo; ela é lida e gravada pelas ferramentas de arquivo do dispositivo.

1. `partituras iniciar --trabalho T [--pedido <horário do pedido>] [--sem-envio]`, antes de
   qualquer leitura da pasta (TMP-01).
2. Trazer da pasta, com `device_stage_files`, o HTML da fanfarra, os PDFs dela e
   `automacao/manifestos/<último PDF>.manifest.json`, e montar o espelho em disco local
   (`/home/claude/espelho/partituras_claude`) com esses mesmos nomes. Uma listagem só (FLX-01).
   Não usar `/mnt/user-data/outputs` como espelho: é rclone, troca o ID do arquivo a cada
   gravação e o `promover` bloqueia por HTML-08. Os arquivos a gravar com `device_commit_files`
   são copiados para `/mnt/user-data/outputs/entrega`.
3. `partituras preparar --trabalho T --pasta <espelho> --fanfarra <Nome>`.
4. Set list novo ou geração integral: `partituras gerar --trabalho T [--setlist arquivo.txt]`.
   Troca de música com set list novo: `partituras gerar --trabalho T --setlist arquivo.txt
   --musica "<Nome>" --imagens <png...>` (um só candidato, PDF-12).
   Troca de música: `partituras substituir --trabalho T --pasta <espelho> --musica "<Nome>"
   --imagens <png...>`.
5. Inspecionar de verdade as páginas em `T/renders` (folhas de até 6 páginas; página com
   alerta aberta sozinha). No template overlay, conferir também os cinco itens de LAY-07.
   Registrar com `partituras aprovar --trabalho T --inspecionadas <páginas>
   [--achado N:descrição]`. Achado reprova; corrigir e gerar de novo.
6. `partituras promover --trabalho T --pasta <espelho>`. Depois, gravar na pasta real na
   ordem de PRO-03 com `device_commit_files`: HTML (se mudou, com `expectedMtimeMs`) →
   PDF novo → reler com `device_stage_files` e conferir o SHA-256 com o inspecionado →
   manifesto.
7. Kindle (KIN-03): PDF acima de ~3,1 MB vai pelo Gmail no navegador do app, "Inserir arquivos
   do Drive", como anexo. Registrar cada tentativa com `partituras kindle`. Depois do sucesso,
   propor a lista de KIN-06 (todos os outros documentos versionados da fanfarra) e só apagar
   com confirmação.
8. `partituras finalizar --trabalho T --pasta <espelho>` e gravar na pasta real o relatório e
   o `historico_execucoes.jsonl` do espelho. Responder com o relatório.

Estado após o piloto de 16/11/2026: `Xamego_v01.pdf`, `Skaravana_v01.pdf` e
`Fanfarock_v01.pdf` aprovados na pasta, com manifesto; os HTMLs já declaram a versão de
template (22, 06 e 10). A primeira troca de música em cada fanfarra já reaproveita a inspeção.

## Convenções

- Código, nomes de módulos e mensagens em português.
- Uma branch por etapa ou mudança; PR com CI verde antes do merge em `main`.
- Não versionar PDFs, renders nem HTMLs de repertório real; eles ficam no Drive.
