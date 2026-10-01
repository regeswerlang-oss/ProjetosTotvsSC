# Aba Estrutura — trilha de alterações, propostas e filtro de situação (01/10/2026)

Complementa `2026-09-29-aba-estrutura-empresas.md`. SQL:
`docs/sql/2026-10-01-estrutura-alteracoes-propostas.sql` (migration
`estrutura_alteracoes_propostas`, aplicada no Supabase `kpimalwnswxalwbidkog`).

## O problema

Dois consultores mexem na mesma definição de compartilhamento. Quem chega depois
troca `ECE` por `ECC` sem saber que outro já tinha decidido — e a decisão some sem
discussão. A tela precisava dizer **quem mudou** e dar um lugar para **discordar
sem sobrescrever**.

## O que entrou

### 1. Coluna **Alterada** (✓ + quem alterou)

- `cockpit.estrut_tabelas_hist`: uma linha por troca REAL de compartilhamento
  (`compart_antes` ≠ `compart_depois`), com `alterado_por`, `alterado_em` e
  `origem` (`edicao` · `proposta` · `manual` · `legado`).
- Semear do catálogo **não** grava trilha: semente é ponto de partida, não decisão.
  Salvar igual (reabrir o modal e gravar sem mudar) também não grava — senão o ✓
  acusaria quem só olhou.
- `legado`: na migração, tabela que já fugia da sugestão virou uma linha com quem
  gravou por último (`definido_por`). Na data da migração eram zero linhas.
- Na tela: ✓ verde (com o número de alterações se >1). **Passar o mouse** mostra as
  últimas 5 trocas (antes → depois, usuário, data/hora). O tooltip é preso ao
  `<body>` (`#est-tip`): dentro do `overflow-x-auto` da tabela ele seria cortado.
- **Aviso antes de sobrescrever**: trocar o select de uma tabela cuja última
  alteração foi de OUTRA pessoa (ou que tem proposta aberta) pede confirmação
  dizendo quem alterou. Cancelar devolve o valor e abre a discussão.

### 2. Coluna **Discussão** (propostas)

- `cockpit.estrut_propostas`: `compart` proposto, `compart_na_hora` (o que estava
  definido quando foi proposta), `motivo` (obrigatório), `autor`, `status`
  (`aberta` · `aplicada` · `descartada`), `resolvido_por/em`, `resolucao`.
- `POST /api/estrutura/<customer>/proposta`
  - `{tabela_id, compart, motivo}` → abre (recusa proposta igual à definição atual);
  - `{id, acao: 'aplicar'}` → troca a definição e grava trilha com origem `proposta`;
  - `{id, acao: 'descartar', resolucao}` → exige o porquê (vai para a ata).
- Modal "Discussão · <tabela>": definição de hoje, quem alterou, todas as
  propostas (abertas com Aplicar/Descartar; resolvidas com quem e por quê) e o
  formulário de nova proposta (3 posições respeitando o leiaute + motivo).
- `GET /api/estrutura/<customer>` passou a devolver `historico` e `propostas`
  dentro de cada tabela (duas queries para o cliente inteiro).

### 3. Filtro de **Situação** (barra acima da lista)

`Todas · Não definidas · Com conflito · Em discussão · Alteradas`, com contagem.

- **Não definidas**: `compart` vazio.
- **Com conflito**: tabela envolvida numa regra da TDN violada (o mesmo erro da
  Conferência — os alertas de regra agora trazem `tabelas: [tab_a, tab_b]`) **ou**
  com proposta aberta pedindo outro compartilhamento.
- **Em discussão**: proposta aberta. **Alteradas**: tem trilha.
- Qualquer situação ≠ Todas olha **todos os módulos** (o select de módulo fica
  desabilitado): "o que falta definir" e "o que está em conflito" não respeitam
  módulo. Linha em conflito ganha fundo rosa; não definida, âmbar.

## Acesso

Igual ao resto da aba: interna (`cliente: False`), gravação em
`require_interno()` + `deny_aba(customer, "estrutura")`.

## Testes

- `docs/testes/testestrutura-trilha.mjs` (stub HTTP + Chromium): contagem das
  situações, filtros conflito/não definidas, tooltip com autor, confirmação ao
  sobrescrever e cancelamento sem POST, registrar proposta e aplicar proposta.
- `docs/testes/teststub.mjs` e `testestrutura.py` continuam passando.

## Pendências

- Notificar por e-mail o autor da última alteração quando alguém abre proposta.
- Relatório de ata só com as propostas (o Exportar HTML já leva as colunas novas, por ser snapshot do DOM).
