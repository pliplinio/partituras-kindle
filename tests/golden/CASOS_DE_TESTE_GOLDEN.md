# CASOS DE TESTE GOLDEN — FANFATESTE

## 1. Objetivo

Este documento define o cenário controlado de integração e regressão do projeto **Organizador de Partituras**, usando a fanfarra fictícia **Fanfateste** e partituras mock.

O objetivo é executar uma sequência curta e reproduzível de alterações de repertório, validar as saídas HTML/PDF e, depois de aprovadas, usar essas saídas como referência golden para comparar futuras otimizações de processamento.

Os testes devem seguir integralmente as regras vigentes em `INSTRUCOES_ORGANIZADOR_PARTITURAS.md` e usar a versão oficial atual de `organizador_partituras_kindle.py`.

## 2. Regra de envio ao Kindle

A execução dos casos de teste **deve gerar o PDF correspondente em todas as etapas**.

Por padrão, os testes **não devem enviar nenhum PDF ao Kindle nem disparar Gmail**.

Qualquer envio ao Kindle em ambiente de teste só pode ocorrer mediante solicitação explícita do usuário e não faz parte do fluxo normal do runner de testes.

## 3. Partituras mock

Arquivos atualmente presentes em `tests/golden_repertorio/input/`:

- `Jonia.png` — música **Jonia**, 1 parte;
- `Doria (1 de 2).png` — música **Doria**, parte 1 de 2;
- `Doria (2 de 2).png` — música **Doria**, parte 2 de 2;
- `Frigia (1 de 2).png` — música **Frigia**, parte 1 de 2;
- `Frigia (2 de 2).png` — música **Frigia**, parte 2 de 2;
- `Lidio.png` — música **Lidio**, 1 parte.

## 4. Regra de execução dos cenários

Os quatro casos são sequenciais.

- O caso 1 cria o repertório inicial da Fanfateste.
- Cada caso posterior parte do HTML canônico resultante e aprovado do caso anterior.
- Inclusão de música e alteração de set list são alterações de conteúdo e, portanto, não devem incrementar a versão do template HTML.
- Cada etapa deve gerar e validar um novo PDF conforme as regras oficiais de versionamento de PDF.
- Nenhuma etapa deve alterar repertórios reais como Xamego, Fanfarock ou Skaravana.
- As saídas de execução devem ser mantidas em `actual/` até a aprovação.
- Depois de aprovadas, as referências golden devem ser preservadas em `expected/` e não podem ser regeneradas automaticamente apenas para fazer um teste passar.

---

## 5. Caso 1 — Criação inicial com Jonia

### Prompt

> Crie um arquivo de partituras para a Fanfateste com a música Jonia. O set list será Jonia. (imagem anexada)

### Entrada

- `Jonia.png`

### Estado esperado do repertório

1. Jonia — 1 parte

### Set list esperado

1. Jonia

### Validações mínimas

- HTML canônico da Fanfateste criado a partir do template de teste;
- somente Jonia presente no repertório;
- índice contendo Jonia;
- set list contendo Jonia;
- link do set list apontando para Jonia;
- link do índice apontando para Jonia;
- título e `ABC` da página de Jonia retornando para a página 1;
- imagem incorporada íntegra e com SHA-256 correspondente à entrada;
- PDF gerado e íntegro;
- total esperado do PDF: **3 páginas** — set list, índice e Jonia;
- nenhum envio ao Kindle.

---

## 6. Caso 2 — Adição de Doria

### Prompt

> Adicione a música Doria ao arquivo de partituras da Fanfateste. O set list será Jonia, Doria. (2 imagens anexadas)

### Entradas novas

- `Doria (1 de 2).png`
- `Doria (2 de 2).png`

### Estado esperado do repertório

1. Jonia — 1 parte
2. Doria — 2 partes

### Set list esperado

1. Jonia
2. Doria

### Validações mínimas

- Jonia preservada sem alteração indevida;
- Doria incluída como um único grupo multipágina;
- Doria com partes `1 de 2` e `2 de 2` consecutivas;
- `data-part` e `data-total-parts` coerentes;
- índice contendo uma única entrada para Doria e uma para Jonia;
- set list atualizado para Jonia, Doria;
- links do set list e índice apontando para a primeira página correta de cada música;
- imagens de Doria incorporadas com SHA-256 correspondente às entradas;
- versão do template HTML mantida;
- novo PDF gerado e íntegro;
- total esperado do PDF: **5 páginas** — set list, índice, Jonia e duas páginas de Doria;
- nenhum envio ao Kindle.

---

## 7. Caso 3 — Adição de Frigia

### Prompt

> Adicione a música Frigia ao arquivo de partituras da Fanfateste. O set list será Jonia, Doria, Frigia. (2 imagens anexadas)

### Entradas novas

- `Frigia (1 de 2).png`
- `Frigia (2 de 2).png`

### Estado esperado do repertório

1. Jonia — 1 parte
2. Doria — 2 partes
3. Frigia — 2 partes

### Set list esperado

1. Jonia
2. Doria
3. Frigia

### Validações mínimas

- Jonia e Doria preservadas;
- Frigia incluída como um único grupo multipágina;
- Frigia com partes `1 de 2` e `2 de 2` consecutivas;
- índice contendo uma única entrada para cada música;
- set list atualizado para Jonia, Doria, Frigia;
- links internos corretos;
- imagens incorporadas com SHA-256 correspondente às entradas;
- versão do template HTML mantida;
- novo PDF gerado e íntegro;
- total esperado do PDF: **7 páginas** — set list, índice, Jonia, duas páginas de Doria e duas páginas de Frigia;
- nenhum envio ao Kindle.

---

## 8. Caso 4 — Adição de Lidio

### Prompt

> Adicione a música Lidio ao arquivo de partituras da Fanfateste. O set list será Jonia, Doria, Frigia, Lidio. (imagem anexada)

### Entrada nova

- `Lidio.png`

### Estado esperado do repertório

1. Jonia — 1 parte
2. Doria — 2 partes
3. Frigia — 2 partes
4. Lidio — 1 parte

### Set list esperado

1. Jonia
2. Doria
3. Frigia
4. Lidio

### Validações mínimas

- Jonia, Doria e Frigia preservadas;
- Lidio incluída como música de uma página;
- índice contendo exatamente uma entrada para cada uma das quatro músicas;
- índice em ordem alfabética segundo as regras oficiais;
- set list atualizado para Jonia, Doria, Frigia, Lidio;
- links internos corretos;
- imagem de Lidio incorporada com SHA-256 correspondente à entrada;
- versão do template HTML mantida;
- novo PDF gerado e íntegro;
- total esperado do PDF: **8 páginas** — set list, índice, Jonia, duas páginas de Doria, duas páginas de Frigia e Lidio;
- nenhum envio ao Kindle.

---

## 9. Casos adicionais de cobertura produtiva — revisão 1.3

Os casos 5–12 partem do estado controlado do caso 4. Eles não alteram repertórios reais.

### Caso 5 — `05_replace_fast_1p`

Substituir `Lidio` por uma nova imagem de uma parte usando **o próprio `replace-song-fast`**. O teste exige:

- `converter.mode = incremental_pdf_patch`;
- gate estrutural aprovado;
- gate nominal aprovado;
- `candidate_manifest_reused_for_delta = true`;
- 8 páginas;
- demais músicas preservadas.

### Caso 6 — `06_replace_fast_multipage`

Substituir as duas imagens de `Doria` usando `replace-song-fast`. Exigir patch incremental multipágina, gate estrutural e reuso do manifesto candidato.

### Caso 7 — `07_setlist_reorder`

Set list: `Lidio, Doria, Jonia`. `Frigia` não está no set list e deve ser preservada ao final. O PDF materializado deve ter 8 páginas e ordem física correspondente ao plano semântico.

### Caso 8 — `08_setlist_repeat`

Set list: `Doria, Jonia, Doria`. O grupo completo de Doria deve aparecer duas vezes, com destinos físicos distintos. `Frigia` e `Lidio` permanecem ao final. Total: 10 páginas.

### Caso 9 — `09_non_setlist_preserved`

Set list: apenas `Doria`. `Jonia`, `Frigia` e `Lidio` devem ser preservadas ao final, uma vez cada, na ordem canônica relativa. Total: 8 páginas.

### Caso 10 — `10_missing_score`

Set list: `Jonia, Inexistente, Doria`. `Inexistente` permanece visível, sem link e sem página inventada. `Frigia` e `Lidio` permanecem ao final. Total: 8 páginas.

### Caso 11 — `11_bad_external_link`

Partir de PDF válido e inserir deliberadamente um link externo sobre item do set list. **PASS do caso = `validate_pdf_against_html` rejeitar o PDF.**

### Caso 12 — `12_wrong_internal_target`

Partir de PDF válido e alterar deliberadamente um link do set list para uma página interna existente, porém errada. **PASS do caso = gate estrutural rejeitar o destino divergente.**

## 10. Critérios para aprovação golden

Uma etapa positiva somente pode ser promovida para `expected/` depois de passar pelas validações automáticas e pela inspeção visual exigida. Preservar HTML, PDF, manifesto, relatório, snapshot, hashes e métricas.

A comparação de regressão prioriza equivalência estrutural/semântica, fingerprints visual/textual por página, dimensões, links e integridade das imagens, não apenas SHA-256 bruto do PDF.

Os casos negativos não são promovidos como referência visual; seu contrato é a rejeição determinística da corrupção.

## 11. Execução, reuso visual e promoção

Execução normal:

```bash
python tests/golden_repertorio/run_golden_tests.py
```

A execução normal grava em `actual/` e nunca altera `expected/`.

Para cenário positivo sem golden aprovado, renderizar todas as páginas para inspeção visual inicial. Quando `expected/<cenario>/snapshot.json` existir e a comparação for `OK`, a execução deve registrar todas as páginas como `reused_pages`, não regenerar PNGs por conveniência e indicar explicitamente a origem do reuso.

`summary.json` contém `regression_validated_against_golden=true` somente quando todos os 10 cenários positivos compararam `OK`; `PASS` com `SEM_GOLDEN` não é prova de regressão contra referência aprovada.

Promoção deliberada:

```bash
python tests/golden_repertorio/run_golden_tests.py \
  --promote-golden \
  --visual-approval-file aprovacao_visual.json
```

O arquivo de aprovação deve conter `approved=true` e a lista completa dos 10 cenários positivos. Sem esse arquivo, a promoção deve falhar.

## 12. Versionamento do processo e histórico de performance

A revisão atual é **1.3** (`template v01`, revisão de processo 3). Ela adiciona:

- materialização produtiva da sequência do set list;
- cobertura direta de `replace-song-fast`;
- repetição/reordenação/preservação/ausência;
- testes negativos de links;
- reuso auditável de inspeção visual;
- bloqueio de promoção sem aprovação visual;
- `elapsed_seconds_core` separado de `elapsed_seconds_wall`;
- gráfico baseado preferencialmente no tempo `core`.

O `historico_testes_golden.jsonl` é append-only. Execuções `FAIL` continuam registradas; o gráfico usa a execução `PASS` mais recente de cada versão `a.b`.

## 13. Sincronização

Quando executado pelo ChatGPT/orquestrador com acesso ao Drive oficial, após `PASS` sincronizar para `actual/` os artefatos gerados dos cenários positivos, `report.json` dos negativos, `summary.json`, `historico_testes_golden.jsonl` e `evolucao_tempo_testes.png`. A execução standalone não contém credenciais nem lógica própria de Drive/Gmail.
