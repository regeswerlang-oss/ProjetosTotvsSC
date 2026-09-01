# Evolução dos Movimentos — 01/09/2026

Par **Situação atual | Evolução** dentro das sub-abas de Movimentos, no mesmo
lugar e com o mesmo comportamento do que Cadastros já tinha — inclusive manter a
visão escolhida ao pular de Base Produção para Base de Testes.

## A pergunta é outra

Em Cadastros a evolução responde "quantos registros entraram". Aqui a pergunta
que decide go-live é **"a cobertura andou?"**, porque volume não é progresso:
entre 25/08 e 01/09 o Olim foi de **321 para 391 movimentos** com a cobertura
**parada em 7/11** e os mesmos 2 cenários faltantes. Nada nos números de volume
denuncia isso — só a coluna de cobertura.

Por isso a barra da série mede **cobertura**, não volume, e fica vermelha
enquanto houver faltante. O KPI diz "sem avanço vs anterior" em vez de repetir o
número, que é a informação que o coordenador precisa levar para a reunião.

## Rota

`GET /api/monitmov/<customer>/evolucao?ambiente=` devolve:

- `serie[]` — uma linha por medição: movimentos, documentos, combinações,
  análises, cobertos, faltantes, cenários e não previstos;
- `cenarios[]` — matriz cenário × medição, com `{qtde, status}` por data;
- `medicoes[]` — o eixo de datas.

**A cobertura é recalculada com `_cobertura()`, a MESMA função da "Situação
atual".** Reescrever a regra de casamento aqui (coringa `*`, normalização,
o que conta como não previsto) faria as duas visões divergirem no dia em que uma
delas mudasse — e o usuário veria 7/11 numa e 8/11 na outra sem explicação. Foi
conferido contra o banco: 391 movimentos, 118 combinações, 7/11 cobertos, batendo
com a tela da Situação atual.

Uma consulta só (`medicao_id = any(...)`) traz as dimensões de todas as
medições; o agrupamento é em Python. São poucas medições, mas centenas de
combinações cada — N+1 aqui custaria caro à toa.

## Tela

1. **KPIs** — cobertos (vermelho enquanto houver faltante), movimentos,
   combinações e quantidade de medições, todos com o delta contra a anterior.
2. **Evolução por medição** — série com barra de cobertura e Δ de cobertos e de
   movimentos lado a lado. É a comparação que revela volume subindo sem
   cobertura andar.
3. **Cenário por medição** — matriz agrupada por análise. **Análise com faltante
   já vem aberta**; a que está inteira coberta vem fechada, com o selo verde.
   Cenário sem movimento mostra `faltante`/`opcional` em vez de `0`, porque zero
   e "não era esperado" são coisas diferentes.

## Cuidado ao mexer

- `carregaMovimentos()` termina em `if (mov.visao === 'evolucao')` — sem isso a
  Situação atual repinta por cima da Evolução ao trocar de ambiente.
- A chave da matriz é o **id** do cenário, não a descrição: descrição repete
  entre análises.
- `mov.evoChave` é `cliente|ambiente`. Trocar de base tem que rebuscar; sem a
  chave, a Base de Testes mostraria os números da Produção.

## Como conferir

`/tmp/mov_evo_check.py`: botões presentes, KPI de cobertos sem avanço, série com
as duas datas, matriz com faltante aberta, volta para Situação atual sem quebrar
e visão preservada ao trocar de base. O stub reproduz os números reais do Olim
(321 → 391, 7/11 nas duas medições).
