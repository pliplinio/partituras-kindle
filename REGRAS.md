# Regras do Organizador de Partituras (versão Claude)

Este arquivo contém as regras de negócio, sem histórico. Cada regra tem um
identificador estável no formato `[ÁREA-NN]`. A matriz
`tests/matriz_regras.yaml` liga cada identificador aos testes que o comprovam,
e o CI falha se uma regra deste arquivo não estiver na matriz.

Origem: `INSTRUCOES_ORGANIZADOR_PARTITURAS.md` da versão ChatGPT (25/10/2026),
mantendo o comportamento, com as mudanças decididas em 15/11/2026 marcadas como
**(novo)**. Decisões ainda abertas estão marcadas como **(pendente)** e usam o
padrão indicado até serem confirmadas.

Para mudar uma regra: altere este arquivo, a matriz e os testes no mesmo PR.

## ARQ — Fontes e pastas

- [ARQ-01] **(novo)** A pasta operacional é `G:\Meu Drive\Tuba\partituras_claude`, sincronizada com o Google Drive. A versão Claude nunca grava na pasta `Partituras_kindle` da versão ChatGPT.
- [ARQ-02] **(novo)** O código e as regras vivem só no repositório `pliplinio/partituras-kindle`. Não existe cópia do script no Drive.
- [ARQ-03] HTML é a fonte canônica do repertório; PDF é o produto final para o Kindle. PPTX e Google Slides são fontes legadas e não são usados quando houver HTML canônico.
- [ARQ-04] Diretórios locais são temporários. Todo resultado oficial é confirmado na pasta operacional.
- [ARQ-05] Relatórios, manifestos e o histórico de execuções ficam em `partituras_claude/automacao`.

## HTML — Arquivo canônico e versão de template

- [HTML-01] **(novo)** O HTML canônico tem nome fixo `<NOME>.html` (ex.: `Skaravana.html`), sem sufixo de versão, para que o link salvo nos favoritos não mude.
- [HTML-02] **(novo)** A versão de template fica dentro do arquivo, em `<meta name="partituras-template-version" content="NN">`, com pelo menos dois dígitos.
- [HTML-03] A versão de template muda somente em alteração deliberada de template: proporção ou tamanho da página, estrutura do cabeçalho, posição padrão de título/`ABC`, regra visual da área da partitura, CSS estrutural compartilhado, estrutura semântica dos blocos, template do índice ou do set list, esquema de atributos exigidos ou outra mudança estrutural global.
- [HTML-04] Alteração de conteúdo não muda a versão de template: incluir música, trocar imagens, mudar o número de partes, corrigir título ou metadados, alterar set list, regenerar índice, mudar a ordem canônica, atualizar links decorrentes do repertório, corrigir ausência ou duplicação.
- [HTML-05] Nova versão de template = versão vigente + 1.
- [HTML-06] **(novo)** Antes de gravar uma mudança de template, a versão vigente é copiada sem alteração para `old/<NOME>_vNN.html`; depois o conteúdo novo entra no mesmo arquivo `<NOME>.html`, preservando o ID no Drive.
- [HTML-07] Toda edição gera primeiro um HTML candidato separado; o canônico só é substituído depois que o candidato passa nas validações.
- [HTML-08] Em alteração de conteúdo, o canônico é substituído no mesmo arquivo, preservando nome e ID no Drive.
- [HTML-09] **(novo)** A edição preserva byte a byte tudo o que estiver fora da região alterada, inclusive quebras de linha (CRLF) e codificação.
- [HTML-10] Rejeitar edição que mude a versão de template em alteração de conteúdo, e mudança de template sem incremento de versão.

## EST — Estrutura semântica do HTML

- [EST-01] Cada página é um `section.slide` com `id` único.
- [EST-02] Página de partitura declara `data-role="score"`, `data-song` (título completo), `data-group` (identificador estável), `data-part` e `data-total-parts`.
- [EST-03] Página de partitura tem título visível, `ABC` visível e imagem incorporada válida.
- [EST-04] A estrutura do repertório é lida dos atributos, nunca inferida por OCR ou análise visual.
- [EST-05] O set list é `section#setlist[data-role="setlist"]`; o índice é `section[data-role="index"]`.
- [EST-06] Toda `section.slide` que não seja set list, índice nem partitura é página auxiliar canônica.

## MULTI — Músicas multipágina

- [MULTI-01] Todas as páginas de uma música formam um único grupo (`data-group`).
- [MULTI-02] As páginas do grupo ficam consecutivas e são movidas e duplicadas juntas.
- [MULTI-03] `data-part` forma a sequência `1..N` sem lacunas e todas as partes declaram o mesmo `data-total-parts=N`.
- [MULTI-04] Inconsistência de grupo, parte ou total reprova o processamento.

## MUS — Inclusão ou alteração de música

- [MUS-01] A entrada é: fanfarra, nome da música e uma ou mais imagens na ordem das partes.
- [MUS-02] A música é identificada pelo título normalizado e/ou `data-group`.
- [MUS-03] Alteração substitui o grupo completo da música; inclusão insere um grupo novo sem remover nenhum existente.
- [MUS-04] Somente o grupo selecionado pode mudar. Se as páginas do grupo não forem contíguas ou a identificação for ambígua, a alteração é bloqueada.
- [MUS-05] IDs existentes são preservados sempre que possível; IDs novos são únicos.
- [MUS-06] As imagens são incorporadas como `data:image/...;base64,...`.
- [MUS-07] O SHA-256 de cada imagem de entrada é idêntico ao da imagem incorporada na parte correspondente; qualquer divergência reprova.
- [MUS-08] O índice é regenerado automaticamente após inclusão ou alteração.

## LAY — Layout das páginas de partitura

- [LAY-01] Cabeçalho no topo, título centralizado, `ABC` à direita.
- [LAY-02] Nos templates com cabeçalho separado (raw-score), a imagem ocupa toda a área abaixo do cabeçalho (`width:100%; height:100%; object-fit:fill`).
- [LAY-03] Música de uma página exibe `Nome da Música`; multipágina exibe `Nome da Música (k de N)` e `ABC` em todas as páginas.
- [LAY-04] No template `score-overlay-header-v2`, a imagem ocupa a página inteira (880×650), sem corte, sem redução e sem `clip-path`, com cabeçalho HTML transparente sobreposto: título 17 px, `ABC` 14 px, caixa de 18 px de altura em `top: 17px`, largura ajustada ao texto.
- [LAY-05] Na limpeza de título/`ABC` antigos embutidos nos pixels, apagar só a região estritamente necessária, sem faixa branca no topo e sem atingir cifras, marcações, compassos ou outro conteúdo musical. A posição horizontal aprovada de cada título é preservada quando necessária para evitar sobreposição.
- [LAY-06] Ao editar uma música num HTML `score-overlay-header-v2`, o modo de cada grupo é preservado: overlay continua overlay e raw-score continua raw-score. Página overlay nova escolhe a posição horizontal de menor interferência visual.
- [LAY-07] Toda edição nesse template exige verificação visual de cinco itens antes da promoção: imagem sem corte ou redução indevida; título legível sem sobreposição; sem resíduo do cabeçalho antigo; `ABC` legível sem duplicação; nenhuma cifra ou marcação apagada. Falha em qualquer item reprova o candidato.

## IDX — Índice

- [IDX-01] Gerado automaticamente a partir das músicas do HTML, com uma entrada por música (multipágina aparece uma vez).
- [IDX-02] Ordem alfabética ignorando acentos e maiúsculas.
- [IDX-03] Texto exibido limitado a 22 caracteres; título completo preservado em `title`.
- [IDX-04] Três colunas reais (CSS Grid ou tabela), preenchidas coluna a coluna, com diferença máxima de 1 item entre colunas. Ex.: 29 músicas = 10/10/9.
- [IDX-05] Cada item aponta para a primeira ocorrência física da música no PDF; música fora do set list aponta para sua página preservada ao final.
- [IDX-06] No PDF, o índice é materializado em 3 colunas reais; conversão que linearize as colunas não pode ser promovida.
- [IDX-07] A validação reconstrói a leitura coluna 1, 2 e 3 de cima para baixo e compara exatamente com a lista alfabética esperada. Com menos de três músicas, colunas que devem estar vazias não reprovam.

## SET — Set list

- [SET-01] Com set list: página 1 = set list, página 2 = índice, partituras depois.
- [SET-02] O set list é HTML nativo com texto real; nada de imagem ou hotspots como interface.
- [SET-03] Cada item declara `data-setlist-pos`; item com partitura tem o texto dentro de `<a href="#...">` e declara `data-setlist-group`.
- [SET-04] No HTML canônico, o link aponta para a primeira página canônica do grupo; no PDF, para a primeira página da própria ocorrência.
- [SET-05] Música repetida no set list gera ocorrências físicas distintas, e cada item aponta para a sua.
- [SET-06] A ordem visual e semântica segue exatamente a ordem do set list.
- [SET-07] A entrada textual aceita listas numeradas, marcadores, travessões, uma música por linha, blocos e bis; ignora apenas cabeçalhos, datas, locais, horários, seções, observações e resíduos de layout inequívocos.
- [SET-08] Sem set list: página 1 = índice, repertório na ordem canônica do HTML, sem inventar set list.
- [SET-09] Música do set list sem partitura fica visível como texto, sem link, sem página criada e sem substituição por outra música; é registrada como ausente e não é erro estrutural.

## PRES — Preservação

- [PRES-01] Nenhuma música ou página canônica pode ser excluída silenciosamente; todas aparecem pelo menos uma vez no PDF.
- [PRES-02] Músicas fora do set list vão ao final, uma vez, na ordem canônica.
- [PRES-03] Páginas auxiliares são preservadas uma vez, após as partituras, na ordem declarada, e não recebem links de título/`ABC`.
- [PRES-04] A preservação é verificada comparando a sequência final com todas as páginas canônicas de origem, nunca só com a sequência construída.

## NOM — Correspondência de nomes

- [NOM-01] Preferir igualdade normalizada exata; aceitar diferenças inequívocas de capitalização, acentuação, pontuação, espaços, abreviações e pequenos erros.
- [NOM-02] Em correspondência aproximada, registrar título procurado, melhor e segundo candidato com scores e a diferença.
- [NOM-03] É ambíguo quando houver mais de uma opção plausível ou a diferença entre os dois melhores scores for menor que 0,08. **(novo)** Também é ambíguo quando a melhor aproximação ficar entre 0,68 e 0,80: não está claro se é aquela música ou uma música sem partitura (ex.: "Mixolidio" × "Lidio", 0,714).
- [NOM-04] Nenhuma ambiguidade é resolvida silenciosamente.
- [NOM-05] Caso obrigatório de regressão: `Ska Paralamas` × `Skaravan`. Nunca escolher pela posição visual; priorizar a similaridade lexical e validar o destino individual.

## PDF — Geração e versionamento

- [PDF-01] Nome final `<NOME>_vNN.pdf`, com underscore e pelo menos dois dígitos.
- [PDF-02] Próxima versão = max(versão de template, versões de PDF existentes, versão mínima configurada) + 1. Em colisão, usar a próxima versão livre.
- [PDF-03] **(pendente)** A versão mínima configurada continua a numeração da versão ChatGPT (ex.: próximo Skaravana = v15), para não reutilizar números já enviados ao Kindle.
- [PDF-04] Nenhum PDF existente é sobrescrito.
- [PDF-05] Fluxo integral: HTML canônico → PDF cru na ordem canônica → materialização do set list → PDF candidato.
- [PDF-06] **(novo)** Conversor oficial único: Chromium headless em versão fixa, respeitando o tamanho de página do template (hoje 880×650 px). Cada `section.slide` gera exatamente uma página no PDF cru; diferença de contagem reprova.
- [PDF-07] O PDF cru nunca é promovido nem enviado.
- [PDF-08] A materialização mantém set list e índice no início, materializa cada ocorrência na ordem do set list, anexa ao final os grupos não usados e as páginas auxiliares, reconstrói o índice em 3 colunas e recria todos os links.
- [PDF-09] Geração e validação usam o mesmo plano semântico.
- [PDF-10] O candidato é gravado como `.candidate.pdf`, reaberto e validado; se a validação falhar, é descartado e nenhum nome final é criado.
- [PDF-11] Substituição simples de música com a mesma quantidade de partes, sem mudar template, set list nem índice, usa preferencialmente patch incremental sobre o PDF anterior aprovado (SHA-256 conferido), trocando só a imagem das páginas alvo em todas as ocorrências.
- [PDF-12] Se a quantidade de partes mudar, houver inclusão ou remoção de páginas, mudança de template ou falha do patch, usar a geração integral. O relatório indica `incremental_pdf_patch` ou o motivo do fallback.

## LNK — Links

- [LNK-01] Título e `ABC` de toda página de partitura apontam para a página 1 (set list, ou índice quando não houver set list), em todas as partes e ocorrências.
- [LNK-02] No PDF final, depois do conteúdo gráfico, os links de título e `ABC` são removidos e recriados como anotações internas `GoTo`, com área clicável moderadamente ampliada que não alcança a margem superior da página.
- [LNK-03] No `score-overlay-header-v2`, a área de fallback acompanha a caixa visual (17–35 px em 880×650, expansão vertical de cerca de 2 px). Havendo texto extraível, segue o retângulo real do título/`ABC`.
- [LNK-04] Páginas de partitura não são puladas mesmo sem texto extraível; páginas auxiliares não recebem esses links.
- [LNK-05] Sem links externos, salvo pedido expresso.
- [LNK-06] Nenhum link aponta para página inexistente, música errada ou ocorrência errada.
- [LNK-07] Quando aplicável, a área clicável cobre todo o texto ou pelo menos 90% dele.
- [LNK-08] A validação confere destino, ocorrência e cobertura; contagem de links não basta.

## VAL — Validação automática

- [VAL-01] Antes de qualquer inspeção visual, o gate estrutural deriva de novo o plano a partir do HTML e reprova o PDF em qualquer divergência.
- [VAL-02] O gate estrutural verifica: páginas reais × esperadas, preservação, sequência do set list, repetições, multipáginas, links do set list, do índice e de retorno, correspondência individual item → ocorrência, índice em 3 colunas, título/parte de cada página, ausência de links externos e de destinos inválidos, e integridade do arquivo.
- [VAL-03] O validador associa cada rótulo físico do índice ao destino por correspondência exata ou inequívoca, independente do algoritmo que criou os links.
- [VAL-04] Gate de escopo do HTML em substituição simples: grupos não alvo inalterados e na mesma ordem; CSS e template iguais; set list com mesmas posições, títulos e grupos; índice com o mesmo conjunto; grupo alvo presente; nenhuma inserção, remoção ou reordenação de grupos não relacionados.
- [VAL-05] Gate nominal da música alterada, antes da inspeção: título, todas as partes `1..N`, páginas encontradas e SHA-256 do candidato.
- [VAL-06] Validações da edição de HTML: IDs únicos, título e grupo corretos, partes consistentes, imagens incorporadas, área da imagem conforme o template, grupo consecutivo, índice regenerado, versão de template mantida.
- [VAL-07] Modo estrito sempre: reprovar estrutura não interpretada, índice ausente, ambiguidade, exclusão indevida, multipágina inconsistente, ordem errada, repetição não duplicada, link incorreto ou externo, total divergente, tentativa de sobrescrita, erro de versão de template, falha de renderização, inspeção obrigatória não feita ou saída corrompida.
- [VAL-08] Pré-validação visual sinaliza página vazia, proporção inesperada, pouco conteúdo, imagem ausente ou não carregada, overflow e elemento fora da área útil. Alertas priorizam a inspeção, não a substituem.

## INS — Fingerprint e inspeção visual

- [INS-01] Fingerprint de 100% das páginas a 110 DPI, uma vez por candidato definitivo, com dimensões, SHA-256 dos pixels, SHA-256 do texto normalizado e fingerprint dos links.
- [INS-02] Uma página só herda inspeção de um PDF anterior aprovado (SHA-256 registrado e conferido) quando dimensões, pixels e texto coincidem exatamente, independente da posição.
- [INS-03] Mudança só de links não invalida o reuso, mas é registrada.
- [INS-04] Inspeção integral obrigatória em: mudança de template ou CSS estrutural, de tamanho de página ou do mecanismo de renderização; ausência de PDF anterior aprovado verificável; manifesto incompatível; falha da comparação; grande mudança estrutural; pedido do usuário.
- [INS-05] Renderizar para inspeção apenas as páginas sem correspondência, salvo fallback integral; as páginas da música alterada são sempre inspecionadas quando seus pixels mudam. Contact sheets com até 6 páginas; página suspeita é aberta sozinha.
- [INS-06] A inspeção verifica página em branco, cortes, conteúdo fora da página, deformações, baixa resolução, ilegibilidade, orientação, duplicações e páginas ausentes.
- [INS-07] Nenhuma inspeção é declarada sem ter sido feita de verdade.
- [INS-09] Usar primeiro o manifesto do PDF anterior; renderizar o PDF anterior só como fallback. Não reduzir cobertura nem DPI para ganhar tempo.
- [INS-08] Cada PDF aprovado tem manifesto por página (JSON) com SHA-256 do PDF, DPI, total de páginas, fingerprints e links por página, páginas inspecionadas e páginas reutilizadas com a origem.

## PRO — Promoção

- [PRO-01] Promover exatamente os bytes inspecionados, sem reconstruir.
- [PRO-02] Recalcular o SHA-256 imediatamente antes de qualquer gravação final ou envio; divergência do SHA-256 inspecionado bloqueia.
- [PRO-03] Ordem: guardar bytes e SHA-256 originais do HTML; gravar o HTML; confirmar SHA-256; gravar o PDF como arquivo novo; confirmar nome, versão, pasta, ID e SHA-256; só então enviar ao Kindle.
- [PRO-04] Se a gravação do PDF falhar depois da do HTML, restaurar o HTML com os bytes originais e confirmar o SHA-256 restaurado.
- [PRO-06] Antes do processamento pesado, confirmar que existem as ações necessárias: gravar o HTML no mesmo arquivo, criar o PDF novo, ler e confirmar o que foi gravado e enviar ao Kindle (dispensado só em processamento sem envio).
- [PRO-05] Não declarar o armazenamento ou o envio bloqueados sem ausência real da ação ou erro efetivo; registrar a operação e a mensagem de erro; não criar arquivos de teste no Drive.

## KIN — Kindle

- [KIN-01] Todo PDF final aprovado e confirmado no Drive é enviado automaticamente na mesma execução para `plinio.plinio_GuQd3r@kindle.com`, salvo pedido explícito de processamento sem envio.
- [KIN-02] Nunca usar SMTP, senha ou credenciais manuais.
- [KIN-03] **(pendente)** Usar o Gmail conectado quando o PDF couber no limite do conector; quando não couber (limite de 4,2 MB por chamada, cerca de 3,1 MB de anexo), usar o Gmail no navegador do app, inserindo o PDF do Drive como anexo, nunca como link.
- [KIN-04] Antes de declarar bloqueio, tentar envio direto, depois rascunho e envio do rascunho, depois o caminho alternativo de KIN-03. Erro transitório de conector permite uma nova tentativa pelo mesmo caminho.
- [KIN-05] Nunca trocar o anexo por link do Drive. Registrar cada tentativa, método e resultado.
- [KIN-06] **(novo)** A Amazon não sobrescreve documentos de mesmo nome. Depois de um envio com sucesso, as versões antigas da mesma fanfarra podem ser apagadas em lote na página "Gerencie seu conteúdo e dispositivos", sempre com confirmação prévia da lista pelo usuário.

## FLX — Fluxo e eficiência

- [FLX-01] Uma única listagem inicial da pasta operacional gera um plano congelado (HTML, PDFs existentes, manifesto anterior, próxima versão). Nova descoberta exige reiniciar a execução com novo plano.
- [FLX-02] Os bytes baixados no início são reutilizados durante toda a execução, sem novas buscas para dados que não mudaram.
- [FLX-03] Em substituição simples: uma edição de HTML, um PDF candidato e um fingerprint; o delta reutiliza o manifesto do candidato já calculado.
- [FLX-04] Se o candidato precisar ser reconstruído, fingerprints e renders anteriores são descartados e recalculados só para o novo candidato.
- [FLX-05] Mudança só de nome de arquivo com o mesmo SHA-256 não repete renderização nem inspeção.
- [FLX-06] O processamento só é interrompido por ambiguidade, inconsistência ou bloqueio real.

## TMP — Medição de tempo

- [TMP-01] O cronômetro começa e é persistido antes da primeira leitura do Drive e nunca é reiniciado ao chamar o código.
- [TMP-02] Registrar `request_received_at_utc` quando disponível (sem inferir), `workflow_started_at_utc`, `first_drive_read_at_utc` e `workflow_finished_at_utc`, com timezone.
- [TMP-03] O fim é capturado logo antes da resposta final, depois da entrega e do relatório; a latência de exibição é declarada como excluída.
- [TMP-04] Total = fim − início por relógio, nunca a soma de etapas nem o tempo do núcleo.
- [TMP-05] Cada etapa registra início, fim, duração, resultado e tentativas; etapa não executada é `NAO_EXECUTADA` com duração nula.
- [TMP-06] Contadores: descobertas no Drive, downloads, edições de HTML, PDFs candidatos, fingerprints, páginas renderizadas, páginas reutilizadas, repetições. Meta em substituição simples: 1 descoberta, 1 edição, 1 candidato.
- [TMP-07] Sem total confiável, `STATUS FINAL: FALHA` com motivo `MEDICAO_DE_TEMPO_INCOMPLETA`, mantendo separados os resultados do PDF e do Kindle; nunca reconstruir ou reenviar só para medir.

## HIS — Histórico de execuções

- [HIS-01] **(novo)** O histórico `partituras_claude/automacao/historico_execucoes.jsonl` é próprio da versão Claude e só recebe acréscimos; registros anteriores nunca são alterados.
- [HIS-02] Cada execução registra, inclusive em falha: timestamps, durações, comando, status, erro, versão e SHA-256 do código, operação, música, versão de template, PDF e SHA-256, referência anterior, etapas, contadores, páginas inspecionadas e reutilizadas, resultado do gate de escopo e os três estados finais.
- [HIS-03] O registro é gravado mesmo em exceção e nunca contém senhas, tokens ou segredos.

## REL — Relatório final

- [REL-06] Antes de gerar, apresentar o relatório pré-geração quando aplicável: HTML e versão de template, tipo de alteração, músicas e páginas canônicas, tabela ordem/música/páginas do set list, correspondências com scores, ambiguidades, repetições, multipáginas, ausências, músicas fora do set list, sequência completa e total esperado.
- [REL-01] Toda execução termina com relatório final explícito na resposta, inclusive em falha ou bloqueio, também salvo em `automacao`.
- [REL-02] O relatório começa pelo tempo e segue o formato: tempo percebido pelo usuário, tempo do atendimento, início/fim, tempo do núcleo, fanfarra/música, HTML, PDF, SHA-256, imagens, páginas/preservação/sequência, set list/índice/retornos, fingerprint/inspeção, Drive/Kindle, tempos por etapa, pendências.
- [REL-03] Sem timestamp do pedido, a primeira linha diz que o tempo é medido desde o início do atendimento.
- [REL-04] O relatório termina exatamente com `PROCESSAMENTO DO PDF: SUCESSO|FALHA`, `ENVIO AO KINDLE: SUCESSO|FALHA|BLOQUEADO` e `STATUS FINAL: SUCESSO|FALHA`.
- [REL-05] `STATUS FINAL: SUCESSO` somente quando todas as etapas obrigatórias, inclusive o gate de tempo, foram concluídas.

## TST — Testes de regressão

- [TST-01] O laboratório usa a Fanfateste, isolado dos repertórios reais, sem Drive, Gmail ou Kindle, e executa o código produtivo.
- [TST-02] Doze cenários: 01 Jonia (criação, 3 p.), 02 Doria (multipágina, 5 p.), 03 Frigia (multipágina, 7 p.), 04 Lidio (1 página, 8 p.), 05 substituição rápida de 1 página, 06 substituição rápida multipágina, 07 set list reordenado, 08 repetição multipágina, 09 set list reduzido, 10 música sem partitura, 11 link externo (deve ser rejeitado), 12 destino interno errado (deve ser rejeitado).
- [TST-03] `PASS` significa gates positivos aprovados e negativos rejeitados; `regression_validated_against_golden=true` só quando todos os cenários positivos tiverem golden aprovado e idêntico.
- [TST-04] A referência golden só é promovida com aprovação visual explícita; a execução normal nunca a altera, nem para mascarar regressão.
- [TST-05] Toda regra deste arquivo tem pelo menos um teste na matriz antes do fim da etapa indicada para ela.

## VER — Versão do código

- [VER-01] O código usa versão semântica `MAJOR.MINOR.PATCH`, declarada em `src/partituras/version.py` e exibida por `partituras --version`.
- [VER-02] Cada release tem entrada no `CHANGELOG.md` e tag Git imutável `vMAJOR.MINOR.PATCH`.
- [VER-03] A versão do código é independente das versões de template, PDF e testes.
