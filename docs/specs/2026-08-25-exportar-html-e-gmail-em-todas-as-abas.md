# Exportar HTML / Rascunho no Gmail em todas as abas — 25/08/2026

Os dois botões viviam só na barra da sub-aba **Cadastros → Situação atual**.
Agora moram na barra de ações do detalhe do projeto (`#tab-acoes`, ao lado de
Expandir/Recolher) e valem para **toda** aba — Resumo, Cronograma, Por Módulo,
Por Etapa, Consumo, GAPs, Cadastros e Transição — inclusive as que vierem.

## Por que ficaram na barra global e não repetidos por aba

Repetir a dupla em cada painel seria oito cópias de markup para manter em
sincronia, e a aba nova de amanhã nasceria sem eles. Na barra global o botão é
um só e a aba nova é atendida sem tocar em HTML.

Consequência: `#tab-acoes` deixou de ser exclusiva das abas com árvore. Quem se
esconde por aba agora é o `#acoes-arvore` (Expandir/Recolher), que só faz
sentido em Cronograma, Por Módulo e Por Etapa.

## Duas formas de virar relatório

1. **Curado** — `relatorioCadastrosHTML()`, que Cadastros já tinha: HTML escrito
   à mão, números recalculados de `cad.dados`. Sai melhor e continua sendo usado
   na visão "Situação atual".
2. **Snapshot** — `snapshotAba(el)`: percorre o DOM do painel visível e troca as
   classes do Tailwind por `style` inline. Não conhece aba nenhuma, então atende
   todas, hoje e depois. É o que roda em Resumo, Cronograma, Por Módulo, Por
   Etapa, Consumo, GAPs, Transição — e em Cadastros na visão **Evolução**, onde
   o relatório curado não se aplica (ele retrata a última medição, não a série).

`RELATORIOS` diz, por aba, o título e qual container exportar.

## O que o snapshot resolve (e por quê)

Gmail ignora `<style>`, `class`, flex e grid. Sem tratar isso o e-mail chega sem
formatação nenhuma. O serializador então:

- **inline em tudo**, via `getComputedStyle`, emitindo só o que **difere do
  pai** nas propriedades herdadas. Sem esse diff cada `<td>` carregaria a fonte
  inteira e um GAPs de 645 linhas viraria um e-mail de vários MB;
- **fileira vira `<table>`**: `display:grid` de várias colunas ou `flex` em
  linha, com 2+ filhos, sai como uma linha de tabela. Sem isso a fileira de KPIs
  empilha em quatro cartões gigantes;
- **largura de célula em %**, nunca em px: o px foi medido na tela do usuário
  (1440, 1920…) e estouraria o cartão de 900 px do relatório. A proporção entre
  as colunas é o que interessa e sobrevive à conversão;
- **barra e quadradinho de legenda** (elemento colorido, sem filho, ≤24 px de
  altura) ganham `height`, `width` e **`display:inline-block`** — sem o
  inline-block um `<span>` com largura simplesmente não aparece;
- **campo de formulário vira o valor digitado** (`<b>4214</b>`, `☑`/`☐`, opção
  do select). Descartar o `<input>` deixava rótulo órfão ("Horas do projeto —")
  e escondia justamente o ajuste que o usuário fez antes de exportar;
- **descarta** `script`, `style`, `button`, `iframe` e o que está com
  `display:none` — inclusive as linhas de drill-down recolhidas;
- **SVG só no arquivo**: no e-mail sai (`opt.email`), porque o Gmail derruba.

## Isto exporta o que está NA TELA

Filtro de GAPs aplicado, etapa recolhida, sub-aba e ambiente escolhidos — tudo
entra como está. É a propriedade que torna o botão previsível, e também a que
exige atenção: exportar a aba GAPs com um filtro ligado gera um relatório
parcial que **não se anuncia como parcial**. Se isso virar problema, o lugar de
resolver é a moldura (`molduraRelatorio`), listando os filtros ativos.

## Cuidado ao mexer

- **A moldura é obrigatória.** Relatório sem cliente e sem data circula por
  e-mail e vira armadilha: ninguém sabe de quem é nem de quando.
- `abreModalEmail()` não chama mais `relatorioCadastrosHTML()` direto — recebe o
  relatório da aba ativa por `relatorioDaAba({email:true})`. O fluxo de
  credencial do Gmail (HTTP 428 → `abreModalCredGmail`) segue igual.
- Aba nova entra em `RELATORIOS` com título e seletor do container. Esquecer a
  entrada faz o botão avisar "não há nada nesta aba para exportar" em vez de
  quebrar.

## Como conferir

`/tmp/export_shot.py` abre cada aba, gera o relatório e checa que ele tem
conteúdo e **zero** `class=` e `<button>`. Depois `/tmp/ver_rel.py` renderiza o
HTML gerado para inspeção visual. Medido em 25/08/2026 (stub): Resumo 6 KB,
Cronograma 162 KB, Por Módulo 62 KB, Por Etapa 54 KB, Consumo 58 KB, GAPs 92 KB,
Cadastros 21 KB, Transição 3 KB.

## Correção do desalinhamento no rascunho (25/08/2026, mesmo dia)

O rascunho do Gmail da visão **Cadastros → Evolução** saiu com as listas
("Sem movimento", "Tabelas que diminuíram") desalinhadas: cada linha com a sua
própria largura de coluna.

**Causa.** Converter fileira em `<table>` estava certo, mas cada fileira virava
uma tabela **independente** — e tabela independente calcula coluna
independente. Dez linhas de uma lista, dez grades diferentes.

**Correção.** Fileiras **irmãs e de mesma forma** entram na MESMA tabela, uma
`<tr>` cada (`snapFilhos` agrupa, `snapLinhas` emite). A tabela vai com
`table-layout:fixed`, então a primeira linha dita as colunas e as demais
obedecem. A corrida quebra quando muda o número de colunas — aí é outra lista.

Três detalhes que essa mudança obrigou, cada um por um motivo concreto:

1. **Espaço em branco entre linhas não encerra a corrida.** As quebras do
   template literal viram nós de texto; tratá-los como conteúdo separava o
   cabeçalho da matriz das linhas de dados, cada um na sua tabela.
2. **Mas espaço também não se joga fora sem olhar.** Entre rótulo e valor ele é
   o espaço da frase. Fica retido e só é descartado se a corrida continuar.
3. **`padding-right:8px` nas células geradas, menos na última.** O `gap` do flex
   não existe em tabela; sem isso as colunas se encostam. Na última mexeria na
   borda direita da linha.

O valor de `<input>` também ganhou um espaço à esquerda: na tela quem separa o
rótulo do número é a borda do campo, que no export não existe.

**Como conferir:** `/tmp/evol_check.py` abre Cadastros → Evolução, exporta e
mede, dentro do HTML gerado, a borda direita de cada célula contra a primeira
linha de cada tabela — falha se divergir mais de 1px. Esperado:
`TODAS ALINHADAS: True`. Precisa de stub com 4 medições (`monitcad_evolucao()`),
senão a visão não tem ranking para desalinhar.
