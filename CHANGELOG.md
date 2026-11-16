# Changelog

Formato baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/);
versões seguem [SemVer](https://semver.org/lang/pt-BR/).

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
