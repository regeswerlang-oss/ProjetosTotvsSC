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
