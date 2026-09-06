# Rail de ações à esquerda + cabeçalho compacto do projeto

**Data:** 05/09/2026 · **Arquivo:** `web/index.html`

## Por quê

O detalhe do projeto gastava ~235px de altura no card de cabeçalho e espalhava
as ações por três lugares diferentes: a barra do topo (`Exportar HTML`,
`Rascunho no Gmail`, `Expandir/Recolher`) e a régua interna de cada aba
(`Script SQL`, `Ambiente`, `Coletar agora`, `Subir medição`, `Cenários`,
`Importar…`, `Publicar painel`). Quem trocava de aba tinha que procurar o botão
de novo.

## O que mudou

### 1. Cabeçalho do projeto: ~235px → ~90px

Título em `text-base`, status e contrato na mesma linha do título, e uma linha
única com `código | Coord. | Aux. | Vigência | Tipo` no lugar do grid de quatro
colunas.

> **Armadilha:** o JS reescreve o `className` do `#d-status` ao montar o
> detalhe. Mudar o tamanho do badge exige mexer **no HTML e no script**.

### 2. Rail de ações (coluna à esquerda)

`<aside id="tab-acoes">`, 178px, sticky abaixo do header, ao lado do card das
abas. Em telas < 768px ela vira uma faixa horizontal acima do card.

O id `#tab-acoes` foi **mantido de propósito**: `setTab()` e `aplicaAbas()` já
sabiam mostrar/esconder esse id — o rail herdou a regra sem duplicar lógica.

Grupos por `data-rail`, um só visível por vez:

| `data-rail` | aparece em | conteúdo |
|---|---|---|
| `arvore` | Cronograma, Por Módulo, Por Etapa | Expandir / Recolher tudo |
| `cad` | Cadastros › sub-aba Cadastros | Script SQL, Ambiente, Coletar agora, Subir medição |
| `mov` | Cadastros › sub-aba Movimentos | idem + Cenários, Importar movimentos |
| `cob` | Cobertura | Cenários, Importar análise |
| `pro` | Protótipo | Módulos por usuário, Novo ciclo, Importar roteiro |
| `tr` | Transição | Publicar painel |
| — (sem `data-rail`) | **todas** | Exportar HTML, Rascunho no Gmail |

`RAIL_ABA` mapeia aba → grupo; **Cadastros é a exceção**, porque lá o grupo
depende da SUB-aba — quem decide é o `setSub()`, que roda depois do `setTab()`
e sobrepõe.

### 3. Faixa de abas

Perdeu 178px de largura para o rail e cortava "Transição": `px-4 py-2` → `px-3`
nos botões (**no HTML e na string que o `setTab()` reescreve**), `gap-1` →
`gap-0.5`, `whitespace-nowrap` e `overflow-x-auto` na faixa — aba nova rola,
não some.

### 4. O que NÃO mudou

- **Filtros e contexto** (cliente, selo do ambiente, Situação atual/Evolução,
  `↻ Atualizar`, seletor de ciclo/painel) seguem na régua acima da tabela.
- **Portões de acesso**: os botões continuam com `data-interno`, agora dentro do
  rail. Quem barra de verdade segue sendo `require_interno()` / `deny_aba()` no
  servidor. Nada foi mexido em `api/index.py`.

## Efeito colateral bom: export mais limpo

`RELATORIOS` aponta para `#tab-*`. Com as ações fora dos painéis, o
`snapshotAba()` não passa mais por nenhum botão de operação — antes eles eram
descartados no meio do caminho.

## Conferido (Playwright + stub, sem Supabase)

- rail = 178px; grupo `cad` visível e `mov`/`cob`/`pro`/`tr` escondidos;
- `railGrupo('mov')` troca o grupo e esconde o de Cadastros;
- **modo cliente**: só `⬇ Exportar HTML` visível, zero `[data-interno]` no rail;
- as 11 abas cabem numa linha em 1440px.
