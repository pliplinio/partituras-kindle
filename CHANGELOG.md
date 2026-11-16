# Changelog

Formato baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/);
versões seguem [SemVer](https://semver.org/lang/pt-BR/).

## [0.1.0] - 2026-11-15

### Adicionado

- Estrutura do pacote `partituras` com as cinco camadas: `dominio`, `html`, `pdf`, `adaptadores` e `casos_de_uso`.
- `REGRAS.md` com 144 regras numeradas, extraídas das instruções da versão ChatGPT, incluindo as mudanças de 15/11/2026: HTML com nome fixo, pastas separadas, conversor único e limpeza da biblioteca Kindle.
- Matriz `tests/matriz_regras.yaml` ligando cada regra à etapa e aos testes, verificada no CI.
- Teste que impede importações entre camadas fora do permitido.
- CI com lint, formatação e testes.
