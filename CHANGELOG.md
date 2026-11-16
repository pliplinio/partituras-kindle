# Changelog

Formato baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/);
versões seguem [SemVer](https://semver.org/lang/pt-BR/).

## [0.6.0] - 2026-11-16

Decisões do usuário antes do piloto.

### Alterado

- PDF-02 e PDF-03: numeração própria da versão Claude, recomeçando em `v01`; a próxima versão
  é o maior PDF existente + 1, e a versão de template não entra na conta. Sai o parâmetro
  `--versao-minima`.
- KIN-06: a limpeza lista todos os outros documentos versionados da fanfarra, porque os da
  versão ChatGPT podem ter número maior que o novo.
- KIN-03 e REL-04 aprovados como estavam propostos.

## [0.5.0] - 2026-11-16

Etapa 5: execução completa, promoção, Kindle, histórico e relatório.

### Adicionado

- `dominio/tempo.py`: cronômetro iniciado antes da primeira leitura do Drive, persistido entre
  passos, total por relógio, etapas e contadores (TMP-01 a TMP-07).
- `dominio/execucao.py`: plano congelado a partir de uma única listagem, com o PDF aprovado
  anterior e o seu manifesto; barra a pasta da versão ChatGPT e HTML sem versão de template.
- `casos_de_uso/promover.py`: grava HTML, PDF e manifesto na ordem de PRO-03, conferindo o
  SHA-256 a cada passo e restaurando o HTML se o PDF falhar (PRO-04).
- `dominio/kindle.py`: caminho de envio pelo tamanho do PDF, registro das tentativas, bloqueio
  só depois de tentar todos os caminhos e lista de versões antigas para limpeza (KIN-01 a KIN-06).
- `adaptadores/pasta_local.py` e `adaptadores/historico.py`: pasta operacional em bytes e
  histórico JSONL só com acréscimos, sem segredos.
- `dominio/relatorio.py`: relatório na ordem de REL-02 e três estados finais.
- `casos_de_uso/executar.py` e CLI com os passos `iniciar`, `preparar`, `gerar`, `substituir`,
  `aprovar`, `promover`, `kindle` e `finalizar`.

### Alterado

- REL-04 (pendente de aprovação): `ENVIO AO KINDLE: NAO_SOLICITADO` no processamento sem envio
  pedido explicitamente.

## [0.4.0] - 2026-11-15

Etapa 4: reaproveitamento de inspeção e troca rápida de música.

### Adicionado


- `pdf/fingerprint.py`: manifesto por página a 110 DPI (pixels, texto e links), compatível com o
  formato `partituras-pdf-page-manifest-v1` da versão anterior. O manifesto do Skaravana v14
  recalculado aqui é idêntico ao gravado pela versão ChatGPT.
- Delta independente da posição da página; inspeção integral obrigatória em mudança de template,
  de renderizador, de tamanho de página, sem PDF anterior verificável ou a pedido (INS-04).
- Links do índice inseridos linha a linha da tabela, como na versão anterior: o candidato do
  Skaravana reaproveita a inspeção das 28 páginas do v14 sem diferença de links.
- `pdf/patch.py`: patch incremental que troca só a imagem da música em todas as ocorrências,
  sobre o PDF anterior com SHA-256 aprovado; qualquer incompatibilidade cai para a geração
  integral com o motivo registrado (PDF-11, PDF-12).
- `html/escopo.py`: gate de escopo da substituição simples (VAL-04).
- `pdf/inspecao.py`: gate nominal (VAL-05), pré-validação visual (VAL-08), renderização seletiva,
  folhas de contato de até 6 páginas e registro de inspeção que recusa páginas não vistas.
- `casos_de_uso/substituir_musica.py`: caminho rápido completo. Trocar uma música do Skaravana
  leva cerca de 2 s e pede inspeção só das páginas dela.
- Cenários golden 05 e 06; `tests/golden/laboratorio.py` com comparação e promoção de golden
  só com aprovação visual explícita (TST-03, TST-04).

## [0.3.0] - 2026-11-15

### Adicionado

- Plano de distribuição das páginas (set list, repetições, preservação, auxiliares, índice) e relatório pré-geração.
- Conversão com o Chromium fixado pelo Playwright 1.63 (Chrome 153.0.8010.12), papel fixo de 880 px × 487,92 pt, uma página por slide.
- Materialização: índice desenhado em 3 colunas, links do set list por ocorrência, do índice pela primeira ocorrência e retornos GoTo de título e `ABC`.
- Gate estrutural independente, com cobertura mínima de 90% dos links sobre o texto.
- Laboratório da Fanfateste (cenários 1 a 4 e 7 a 12) e testes negativos de corrupção.
- Chromium instalado no CI.

### Verificado com repertórios reais

- Skaravana: PDF idêntico ao v14 aprovado em pixels (110 DPI), texto e links nas 28 páginas.
- Xamego e Fanfarock: gate aprovado. O Xamego v38 aprovado tem página de 880×650 pt (outro conversor); o primeiro PDF do Xamego pela versão Claude exige inspeção integral (INS-04).

### Mudado em relação à versão ChatGPT

- NOM-01: inclusão de nome só conta por palavras inteiras ("Lidio" não abrevia "Mixolidio").
- NOM-03: aproximação entre 0,68 e 0,80 é ambiguidade e pede confirmação, em vez de criar o link.

## [0.2.0] - 2026-11-15

### Adicionado

- Domínio: correspondência de nomes (mesma fórmula de score da versão ChatGPT, uma candidata por música), estrutura do repertório, índice, leitura do set list em texto e versões de template e de PDF.
- HTML: leitura que preserva os bytes (CRLF incluído), gravação da versão de template no arquivo, regeneração de índice e set list, inclusão e troca de música com as validações da edição.
- Testes com os HTMLs reais (opcionais, via `PARTITURAS_HTML_REAIS`): regenerar índice e set list dos três repertórios não altera nenhum byte.

### Mudado em relação à versão ChatGPT

- Item do set list que já declara `data-setlist-group` mantém a ligação, sem recalcular pelo nome.
- Títulos que só diferem por parênteses ("Coração Partido" e "Coração Partido (graus)") são desempatados pela grafia completa; antes, a primeira página vencia sem aviso.
- Bloco de música gerado segue a quebra de linha do arquivo.

## [0.1.0] - 2026-11-15

### Adicionado

- Estrutura do pacote `partituras` com as cinco camadas: `dominio`, `html`, `pdf`, `adaptadores` e `casos_de_uso`.
- `REGRAS.md` com 144 regras numeradas, extraídas das instruções da versão ChatGPT, incluindo as mudanças de 15/11/2026: HTML com nome fixo, pastas separadas, conversor único e limpeza da biblioteca Kindle.
- Matriz `tests/matriz_regras.yaml` ligando cada regra à etapa e aos testes, verificada no CI.
- Teste que impede importações entre camadas fora do permitido.
- CI com lint, formatação e testes.
