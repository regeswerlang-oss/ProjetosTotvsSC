# Aba Integrações — grupo EAI Protheus × Schedule

*30/10/2026. Piloto: DÍGITRO (`000348D0`), Base Produção e Base de Testes.*

**Pedido.** Levar para a aba Integrações, com o botão **⚡ Coletar agora**, os
indicadores do desenho técnico *EAI × Schedule × iPaaS × CRM* (Consultoria
TOTVS SC, 30/10). O grupo cobre o sentido **Protheus → iPaaS → CRM** dos
cadastros. O sentido **CRM → iPaaS → Protheus** (propostas, ZA3) é o grupo
`crm` (PR #5), que entra depois.

**Base técnica.**

- Leitura da Produção da Dígitro em 30/10/2026, das 10:05 às 10:20, pelo `/tscmonit/query`.
- Reunião interna Reges/Felipe/Cassio/Fábio (TOTVS CRM) de 30/10.
- TDN: *A camada do EAI Protheus* (XX3, XX4, XXF), *Status das mensagens no
  EAI Protheus* (4 tentativas, FWEAICLEAR), *Cadastro de Produtos – Item*
  (XXF gravada no retorno), *ER ajuste dos campos data Schedule/EAI*
  (XX0, XX1, XX2, XX3, SCHDTSK).

## A pergunta que o grupo responde

**"O cadastro que o Protheus mandou pela Mensagem Única chegou ao destino e
voltou com o ID dele?"**

```
evento no cadastro ─► adapter XX4 ─► fila XX3 (status 0) ─► envio pelo canal do adapter
                                                              3 = PAD.APP (iPaaS) · 1 = ESB
                                    XX3 status 7 "Entregue" ◄─┘
destino devolve a ResponseMessage ─► entra na XX3 ─► FWEAIRECE (Schedule) processa
                                    ─► XXF (de-para ID externo × código Protheus) + status 2 "Finalizada"
FWEAICLEAR (diário) ─► apaga FISICAMENTE as finalizadas
```

## Decisões que custam caro se desfeitas

1. **Não se mede "% finalizadas".** O FWEAICLEAR apaga as finalizadas: uma
   base saudável fica com quase nada na XX3. O painel mede o que ficou
   **aberto** (idade da entregue sem retorno, falhas, parada antes do envio)
   e o **de-para gravado** (XXF), que é a prova durável do retorno.
2. **"Cadastro sem envio" olha a XX3 e a XXF.** Mensagem já limpa pelo
   FWEAICLEAR deixa o de-para. Só falta quando o cadastro tem registros, o
   adapter envia, e não há mensagem nem de-para. É o caso da tabela de preço
   da Dígitro, carregada por fora do evento.
3. **Código do status sempre ao lado do rótulo.** A TDN lista as 8 legendas
   sem o código. A ordem dela (0 a 7) casa com os dados da Dígitro: o 7, com
   URL e sem tentativa, é Entregue; o 5, com 4 tentativas, é Não entregue.
   Se uma base mostrar outra coisa, o código cru aparece e a leitura não
   engana.
4. **Nunca se lê `XX3_URL` nem `XX3_TRANS`.** A URL do iPaaS leva a api-key em
   texto claro, e o TRANS é a mensagem inteira. Vem só `COM_DESTINO` (S/N). O
   teste do back e a REST fingida das rotas travam isso. O `MV_EAIPASS` vem
   como `(preenchido)`.
5. **Sufixo só nas tabelas da empresa.** XX3, XX4 e XXE levam o sufixo
   (`XX3010`). XX0, XX1, XX2, XXD, XXF e SCHDTSK são do framework e ficam sem
   sufixo, como na Dígitro.
6. **CLOB não é memo do DBAccess.** `XX3_RETURN` e `XX1_RECORR` são CLOB no
   Oracle, então a 1ª variante é `DBMS_LOB.SUBSTR`, não `UTL_RAW`
   (`_eai_texto_exprs`). A última variante é sempre sem o campo.
7. **O job da Etapa 2 do CRM (`U_CRMPROJT`) não é cobrado.** Alison, em
   30/10: ele fica desligado de propósito até o de-para e os campos fecharem.
   O fluxo é o **Sincronizar** do Painel de Projetos. O grupo EAI só cobra
   FWEAIRECE, FWEAISEND e FWEAICLEAR, e qualquer agendamento que nunca rodou.

## Blocos (`_eai_scripts`)

| id | tipo | o que lê |
|---|---|---|
| `eai_config` | resumo | SX6 `MV_EAI*` (`MV_EAIPASS` mascarado) |
| `eai_adapters` | resumo | XX4: rotina, mensagem, envia/recebe, método, canal, versão, condição de envio |
| `eai_status` | resumo | XX3 por mensagem × status × canal × sentido: qtd, 4+ tentativas, com destino, 1ª e última data (sem janela, só o corte) |
| `eai_abertas` | resumo | XX3 ≠ finalizada por mensagem × status × dia, com a menor hora (30 dias) |
| `eai_depara` | resumo | XXF por alias × referência × mensagem |
| `eai_empresa` | resumo | XXD (de-para de empresa/filial) |
| `eai_cadastros` | resumo | contagem de SA1, SA2, SB1, SA3, SE4, SAH, SA4, SBM, DA0, DA1 |
| `eai_agendamentos` | resumo | XX1: rotina, ambiente, início, última execução, recorrência (CLOB), marca EAI |
| `eai_agend_empfil` | resumo | XX2 (empresa/filial de cada agendamento) |
| `eai_tarefas` | resumo | SCHDTSK por agendamento × status |
| `eai_agents` | resumo | XX0 |
| `eai_pendentes_lista` | detalhe (200) | XX3 abertas das mais antigas: status, canal, tentativas, evento, web service, `COM_DESTINO`, retorno (CLOB) |

## Indicadores (`_eai_indicadores`, grupo `eai`)

| chave | valor | verde | amarelo | vermelho |
|---|---|---|---|---|
| `eai_sem_retorno` | entregues (7) | nenhuma, ou < 30 min | 30 min ou mais (`EAI_RET_MIN`) | 24 h ou mais (`EAI_RET_HORAS`) |
| `eai_falhas` | falhou/não entregue/recusada | 0 | só de hoje e com menos de 4 tentativas | de 1 dia ou mais, ou com 4 tentativas |
| `eai_aguardando` | status 0/1 | nada, ou < 15 min | 15 min ou mais | 2 h ou mais |
| `eai_canal` | abertas em canal ≠ adapter | 0 | alguma | — |
| `eai_depara` | registros na XXF | todo alias enviado tem de-para | algum alias sem | XXF vazia com envio |
| `eai_cobertura` | adapters sem nenhum envio | 0 | — | cadastro com registros, adapter envia, sem mensagem nem de-para |
| `eai_jobs` | `n/2` (RECE e SEND em dia) | rodando há < 15 min; CLEAR em 2 dias | algum há 15 min ou mais; CLEAR ausente ou atrasado | RECE/SEND ausente (com adapter assíncrono), nunca executou, ou parado há 2 h |
| `eai_agendamentos` | agendamentos nunca executados | 0 | — | algum com início no passado e sem execução |
| `eai_params` | `n/13` | coerentes | `MV_EAIPORT` sem adapter no canal ESB | adapter no ESB com `MV_EAIURL` vazio |

Cinza = bloco não lido, tabela ausente ou sem dado para comparar (não piora a situação geral).

## Retrato da Produção da Dígitro (30/10, 10:05)

Todos os indicadores em vermelho, menos `eai_aguardando` (verde), e `eai_canal` e `eai_params` (amarelos):

- 969 entregues sem retorno, a mais antiga de 28/10.
- 12 não entregues com 4 tentativas.
- 6 SELLER no canal ESB (`MV_EAIPORT = WS_ERPProtheusToGFE`, `MV_EAIURL` vazio).
- XXF vazia.
- `PRICELISTHEADERITEM` sem nenhuma mensagem, com 7 tabelas e 322 itens.
- FWEAIRECE e FWEAISEND criados em 21/10 como "sempre ativo" no Smart Schedule e nunca executados.

O teste `docs/testes/integracoes-eai-back.py` usa esses números.

## Tela

- Barra: **Monitorar ☐ RH ☐ TOTVS Transmite ☐ CRM × iPaaS ☐ EAI × Schedule**.
  O **⚡ Produção + Teste** aparece com CRM ou EAI ligado. Ele liga na outra
  base os grupos de comparação que faltarem lá e mantém os que ela já tem.
- Nove cartões do grupo.
- Caixa "o cadastro saiu e voltou?":
  - **caminho:** fila → aguardando → com falha → entregues sem retorno → finalizadas → de-para, com "! atenção" em texto;
  - **Produção × Teste** lado a lado;
  - fila por mensagem/status/canal;
  - abertas com idade;
  - adapters;
  - XXF;
  - cadastros;
  - **Schedule:** agendamentos com última execução, "✕ nunca executou", recorrência e tarefas; agents.
  - parâmetros e XXD.

## Testes

- `python3 docs/testes/integracoes-eai-back.py`: 299 asserções. Cobre o SQL
  (sem `;`, sem relógio, sem `||`, sem URL/TRANS, sufixo só onde cabe,
  variantes CLOB, SQL Server, corte), o retrato real da Produção, o cenário
  saudável, a mensagem limpa pelo FWEAICLEAR com de-para, as tabelas ausentes
  e a coleta sem relógio.
- `python3 docs/testes/integracoes-rotas.py`: inclui a coleta só-EAI com a REST
  fingida (12 consultas, nenhuma de outro grupo, sem segredo no payload,
  recorrência lida), os scripts do grupo e a rota `/grupos` aceitando `eai`.
- `node docs/testes/integracoes-eai-front.js`: 30 asserções (checkbox, botão,
  cartões, caminho, status com código, nunca executou, escape, duas bases
  ligando o EAI na outra, zero erro de JS).

## Para ligar na Dígitro

1. Publicar e rodar `docs/sql/2026-10-30-integracoes-eai.sql` no Supabase.
   Ele aceita `crm` e `eai` e liga o EAI nas duas bases. Rodar **depois** do
   deploy: o código antigo trata grupo desconhecido como "só RH".
2. Na aba Integrações, clicar em **⚡ Coletar agora**, ou em **⚡ Produção + Teste**.

## Fora deste patch

- **Conferência com o monitor do iPaaS** (execuções e erros do lado do iPaaS).
  Depende da leitura pelo Chrome e de uma API do iPaaS.
- **Coleta automática pelo pg_cron** (`/api/cron/integracoes`).
