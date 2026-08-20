# Aba "Por Etapa" — alinhamento das colunas — 20/08/2026

## O problema

O drill-down da etapa era uma **tabela aninhada** dentro de um `<td colspan="9">`.
Tabela aninhada tem grid próprio: as larguras das colunas de dentro são
calculadas pelo conteúdo dela, sem nenhuma relação com as da tabela de fora.
Resultado: o número da linha de módulo caía num lugar e o da linha de etapa em
outro, e ambos fora do rótulo do cabeçalho.

A tabela de fora também era `table-auto` — as colunas numéricas mudavam de
largura conforme o projeto aberto (`153` × `27` dão larguras diferentes), então
"Estimadas" e "% Exec" deslizavam sobre os números.

## O que mudou

1. **Uma tabela só.** As linhas de módulo e de atividade viraram `<tr>` irmãs no
   mesmo `<tbody>`, marcadas com `data-etapa-children="<etapa>"`. Mesmo grid ⇒
   alinhamento garantido pelo próprio layout de tabela, não por CSS igual dos
   dois lados.
2. **`table-fixed` + `<colgroup>`** com largura fixa nas oito colunas da direita.
   A coluna Etapa fica com a sobra. `min-w-[940px]` mantém a grade quando a tela
   encolhe — aí o container `overflow-x-auto` rola em vez de espremer.
3. **`tabular-nums`** em toda célula numérica: dígito com largura fixa, então a
   coluna de números fica com vírgula sob vírgula.
4. **Hierarquia por recuo**, não por tabela: módulo `padding-left: 1.75rem`,
   atividade `3.25rem`, aplicados na 1ª coluna via `style` (o recuo não pode ser
   classe utilitária porque muda por nível).

## Cuidado ao mexer

- **O toggle agora é `querySelectorAll`.** Antes existia UMA linha-filha (a que
  continha a tabela aninhada) e `querySelector` bastava. Agora são N linhas por
  etapa; usar `querySelector` esconderia só a primeira. O estado vem do chevron
  (`classList.toggle` devolve o novo estado) e é aplicado com
  `classList.toggle('hidden', !abre)` — assim as N linhas nunca dessincronizam.
- **Toda linha precisa ter as 9 `<td>`.** Sem tabela aninhada, um `colspan`
  errado desloca a linha inteira. A linha de atividade não tem barra de
  progresso, mas ainda assim emite a `<td>` vazia.
- A 1ª coluna é `truncate` com `title`: nome de etapa longo vira reticências em
  vez de empurrar as colunas numéricas.

## Como conferir

`/tmp/etapa_shot.py` compara o `getBoundingClientRect().right` de cada `<td>`
visível com o do `<th>` correspondente e falha se divergir mais de 1px. Saída
esperada: `DESALINHADOS: nenhum ✓` e `tabelas aninhadas: 0`.
