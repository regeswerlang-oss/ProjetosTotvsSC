# Aba Compara — dicionário (SX2/SX3/SX6) entre as empresas da mesma base

*01/10/2026 — pedido do Reges a partir da aba Estrutura.*

## O problema

A aba **Estrutura** diz como o compartilhamento **deveria** ser: é a definição
que o consultor monta com o cliente. O que ela não responde é a pergunta que
aparece na implantação com mais de uma empresa: **as empresas desta base foram
montadas iguais?**

No Protheus o dicionário é por **grupo de empresas**. `SX2010`, `SX2020` e
`SX2030` são dicionários **diferentes**, com campos, tamanhos e parâmetros
próprios. Ninguém vê a divergência até o cliente ligar dizendo que o campo
existe numa empresa e não na outra — normalmente no meio de um teste integrado,
que é o pior momento possível.

## A decisão

Uma aba **Compara**, lendo o dicionário **ao vivo** pela REST que já existe
(`TSCMONITREST`, rota `/tscmonit/query`, só leitura), sem guardar nada.

Não guardar é decisão, não falta: dicionário muda a cada compilação e a cada
pacote aplicado. Um retrato de ontem apresentado como "a situação" engana mais
do que ajuda. A aba também **não roda sozinha** ao abrir — quem dispara é o
consultor, depois de escolher a base. Rodar na base errada é o erro caro deste
processo, igual ao da coleta de cadastros.

## Onde a agregação roda — e por quê

| Dicionário | Volta | Agregação |
|---|---|---|
| **SX2** | tudo | no painel |
| **SX3** | só o que diverge | **no banco** |
| **SX6** | só o que diverge | **no banco** |

O SX2 vem inteiro porque *"a tabela existe só na empresa 1 e 2"* é uma pergunta
sobre **ausência**: sem a lista completa não dá para saber quem falta. São ~600
linhas por empresa — cabe.

O SX3 não cabe: três empresas são ~90 mil linhas, acima do `limite_linhas` e do
tempo da função da Vercel (morre em 60s). Então o `GROUP BY` roda no Oracle e
volta só `(arquivo, campo)` que falta em alguma empresa **ou** que muda de
tipo/tamanho/decimal entre elas. Mesma lógica no SX6.

## O que cada bloco responde

1. **SX2 — tabelas por empresa.** Uma coluna por empresa; a célula traz o
   compartilhamento (`X2_MODOEMP` + `X2_MODOUN` + `X2_MODO`) e `—` quando a
   tabela não existe ali. A coluna *Situação* resume: `só em 01, 02`,
   `compartilhamento diferente` ou `igual`.
2. **SX3 — campos divergentes por tabela.** Agrupado por arquivo, a célula traz
   `tipo/tamanho,decimal`; `—` é campo que não existe naquela empresa. É o
   "campo a mais" e o "tamanho diferente" na mesma leitura.
3. **SX6 — parâmetros divergentes**, nos três sabores que o pedido separa, nesta
   ordem: **não existe** na empresa; existe com **compartilhamento** diferente
   (o chip é o `X6_FIL` — "todas" = parâmetro global, código = só naquela
   filial); existe com **conteúdo** diferente.

## Descoberta das empresas

Ninguém digita sufixo: uma consulta em `ALL_TABLES` acha os `SX[236]\d{3}` e só
entram os sufixos que têm os **três** dicionários.

A **empresa 99 fica de fora, sempre**. É a empresa de exemplo que vem no pacote
do Protheus: existe em toda base, não é do cliente, e comparar contra ela só
produz ruído — "a tabela falta na 99" aparecia em quase tudo e inflava a
contagem. O corte acontece **antes da consulta**, não na tela: assim a 99 nem
entra no `UNION` e as três leituras ficam menores. Um `SX3` sem o `SX2` do mesmo
grupo é sobra de migração, não empresa — esses aparecem num aviso à parte, para
não virarem conclusão errada. O nome da empresa vem do SM0 que a aba Estrutura
já leu; o dicionário só conhece o sufixo, e `010 × 020` não diz nada a ninguém.

## Recolher: o bloco fechado nem gera DOM

Na primeira base real a aba voltou com **5.529 campos divergentes** e 238
parâmetros. Despejar isso de uma vez não é leitura, é rolagem — e o navegador
sente. Os três blocos recolhem, e o corpo da tabela é uma **função**: fechado,
a tabela não chega a ser montada.

O **SX2 abre por padrão**; SX3 e SX6 nascem recolhidos. O SX2 é o menor e o mais
lido — "a tabela existe nesta empresa?" é a primeira pergunta; o detalhe de
campo e de parâmetro vem depois, sob demanda. O contador fica no cabeçalho para
o bloco fechado ainda informar (`5.529 campos em 1.240 tabelas`).

## Limites que valem lembrar

- **Só Oracle** por enquanto. O ambiente cadastrado como `mssql`/`postgres`
  recebe recusa explícita em vez de um SQL que não roda.
- São **quatro** chamadas ao `/query` (sufixos + SX2 + SX3 + SX6), com prazo
  compartilhado: o `timeout_s` do ambiente, limitado a 50s. Estourou, a resposta
  diz em qual leitura parou.
- `truncado: true` em qualquer uma vira erro, não resultado parcial —
  comparação truncada é comparação errada.
- **Não depende do patch v1.1** do `TSCMONITREST`: o SQL gerado começa
  direto em `WITH`/`SELECT`, sem cabeçalho de comentário, que era o que o
  `SqlSeguro` 1.0 recusava.

## Como foi testado

Stub da REST devolvendo CSV de três empresas (`010/020/030`) com divergências
plantadas: `XX1` só em duas empresas, `SB1` com compartilhamento diferente,
`A1_XZZZ` só numa, `A1_NOME` com 40/40/60, `MV_AAA` ausente, `MV_BBB` com
`X6_FIL` diferente e `MV_CCC` com conteúdo diferente. O teste inclui um **porte
do `SqlSeguro` v1.1** e passa os quatro SELECTs por ele — a regra que recusa o
script mora na base, não aqui, e descobrir isso depois do deploy sai caro.

A tela foi aberta no Chromium com `/api/*` interceptado, conferindo a matriz, o
filtro "só o que diverge", a busca e o sumiço do cabeçalho de tabela do SX3
quando nenhum campo seu sobra visível.
