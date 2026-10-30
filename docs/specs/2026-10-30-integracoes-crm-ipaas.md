# Aba Integrações — grupo CRM × iPaaS × Painel de Projetos

*30/10/2026. Piloto: DÍGITRO (`000348D0`), Base Produção e Base de Testes.*

**Pedido.** Fazer na aba Integrações a coleta de dados da integração da
Dígitro, nos dois sentidos:

- **Protheus → iPaaS → CRM:** produtos e tabelas de preço.
- **CRM → iPaaS → Protheus:** propostas, itens e valores.

E o que o Painel de Projetos (Alison) mostra: propostas recebidas, propostas
tratadas, contratos gerados e medições geradas. A coleta sempre roda nas duas
bases, Produção e Teste.

**Base técnica.**

- *Painel de Projetos – Especificação Técnica* (Alison, 01/10/2026): §9.3,
  §10, §12, §13.4 (ZA3), §13.1 (ZA0/ZA1), ZA9 e §13.10.
- Fluxo Sistêmico CRM × iPaaS × Painel × Contratos v2 (27/10), pontos P1 a P15.
- Reunião interna Felipe/Alison/Reges de 27/10/2026.

## A pergunta que o grupo responde

**"A proposta que o comercial ganhou no CRM virou projeto, contrato e medição?
E o que parou no caminho?"**

```
CRM ─iPaaS─► POST /api/v1/CRMIntegracao ─► ZA3  STG1 R→P→L | E   (Etapa 1, na hora)
                                            │   STG2 A→P→S | E   (Etapa 2, job U_CRMPROJT / Sincronizar)
                                            ▼
                     ZA0 (1 projeto por OV) + CTD + CN9 (1 contrato por oportunidade, 1 planilha por projeto)
                                            │   transação única: erro = nada gravado
                                            ▼
                     CND (medição — NÃO é gerada pela integração)      ZA3_STIPA (retorno ao CRM — não implementado)
```

## Decisões que custam caro se desfeitas

1. **A chave da cadeia é o contrato da ZA3 (`ZA3_CONTRA`).** O número da
   proposta não serve:
   - na ZA3 ele só existe dentro do JSON;
   - o `CN9_XOPORT` tem 6 posições, contra 50 do `ZA0_PROPOS` (P10).

   Uma junção por proposta quebraria sem dar erro. Por isso:
   - projetos entram por `RTRIM(ZA0_CONTRA) IN (contratos da ZA3 com STG2 = S)`;
   - CN9 e CND entram pelo mesmo conjunto;
   - todas as junções usam `RTRIM`, porque `ZA3_CONTRA` é C20 e `ZA0_CONTRA` é C17.
2. **Erro de proposta reprocessada não conta como aberto.** Uma proposta que
   errou e depois teve sucesso (outro registro com o mesmo `ZA3_IDCRM` em
   STG2 = S) aparece na lista como "já com sucesso depois". Ela não entra no
   cartão nem no resumo de causas.
3. **Nada de subconsulta dentro de agregação.** Não se usa
   `SUM(CASE WHEN EXISTS …)`, porque o SQL Server recusa. As contagens condicionais usam
   `LEFT JOIN` numa derivada (preço vigente, pedido da medição, proposta que já
   teve sucesso). O teste do back trava esse padrão.
4. **Fila e erro vêm por dia** (`ZA3_DTINC` + `MIN(ZA3_HRINC)`). O par data e
   hora dá a idade exata sem concatenar campo, que se escreve `||` no Oracle e
   `+` no SQL Server. A idade é calculada no Python com o relógio de
   Florianópolis.
5. **O retorno ao CRM (`ZA3_STIPA`) não pesa enquanto não existir.** Na reunião
   de 27/10 ficou registrado que a integração termina ao gerar projetos e
   contrato. O cartão fica cinza e explica o P11. Ele só vira vermelho se
   aparecer STIPA = E, ou seja, quando o retorno for implementado e falhar.
6. **O lado Protheus → CRM é medido pela prontidão e pelo efeito, não pela
   fila.** O gatilho, a API e a tabela de controle do envio ainda não foram
   definidos (P1); Felipe e Cássio estão definindo o filtro e o de-para. O
   painel mostra duas coisas:
   - **Prontidão:** produto ativo (fora os `PRJ*` criados pela própria
     integração) com preço maior que zero numa tabela DA0 ativa e dentro da
     vigência.
   - **Efeito:** a proposta barrada por cadastro, pela causa do `ZA3_ERRO`. A
     integração é tudo ou nada, então um código sem preço barra a proposta
     inteira.

   Quando a fila de envio existir, ela entra como mais um bloco.
7. **Os tokens são mascarados no SQL** (`MV_ZCRMTOK`, `MV_ZLICTOK`,
   `MV_ZLICCLI`, `MV_ZLICSEC`). O valor vem como `(preenchido)` ou vazio e
   nunca chega ao Supabase.

## Blocos (`_crm_scripts`)

| id | tipo | o que lê |
|---|---|---|
| `crm_config` | resumo | SX6: `MV_ZCRMMOD`, `MV_ZCRMURL`, `MV_ZCRMLOG`, `MV_ZMAILPP`, `MV_ZOPEMAI`, `MV_ZLIC*`, `MV_ZGRPLIC` (tokens mascarados) |
| `crm_totais` | resumo (1 linha) | ZA3: mensagens, propostas distintas, liberadas, tratadas (STG2 = S), contratos na ZA3, retornadas, 1ª e última entrada |
| `crm_situacao` | resumo | ZA3 por STG1 × STG2 × STIPA |
| `crm_fila` | resumo | ZA3 parada (STG1 R/P, ou L com STG2 A/P), por dia, com a menor hora |
| `crm_erros` | resumo | ZA3 em erro (STG1 ou STG2 = E), por dia, com `SEM_SUCESSO` |
| `crm_projetos` | resumo | ZA0 dos contratos gerados, por tipo (físico/virtual) × situação |
| `crm_contratos` | resumo | CN9 dos contratos gerados, por `CN9_SITUAC` (10 = revisão antiga, fora da conta) |
| `crm_medicoes` | resumo | CND dos contratos gerados, por `CND_SITUAC`, com pedido de venda (`C5_MDCONTR`/`C5_MDNUMED`). Uma variante sem a SC5 |
| `crm_cad_produtos` | resumo | SB1 ativo por tipo: total, com preço vigente e com `B1_ZFATURA`. Uma variante sem `B1_ZFATURA` |
| `crm_cad_tabelas` | resumo | DA0 com vigência, itens e itens com preço |
| `crm_pendentes_lista` | detalhe (200) | ZA3 com erro ou parada, com o `ZA3_ERRO` (memo: BLOB → CLOB → sem texto) e `JA_OK` |
| `crm_rastreio_lista` | detalhe (200) | ZA3 com sucesso → proposta (ZA0_PROPOS), nº de projetos, contrato e situação na CN9, nº de medições, retorno |
| `crm_sem_preco_lista` | detalhe (200) | produtos ativos sem preço vigente |

O corte "A partir de" da base vale para `ZA3_DTINC`, inclusive no conjunto de
contratos. Os cadastros não têm corte.

**Causa do erro** (`_crm_causa` → coluna `CAUSA` em cada linha da lista e
`causas` no bloco). A regra é aplicada sobre o texto sem acento, nesta ordem:
duplicidade → tabela de preço → cliente → vendedor → produto → condição →
tipo de contrato → mensagem (JSON) → ambiente → outros. A tabela de preço vem
antes de produto: "produto sem preço na tabela" é problema da DA1, e não da
SB1.

## Indicadores (`_crm_indicadores`, grupo `crm`)

| chave | valor | verde | amarelo | vermelho | cinza |
|---|---|---|---|---|---|
| `crm_recebidas` | propostas distintas | houve recebimento | — | — | nenhuma no período |
| `crm_erros` | propostas em erro sem sucesso depois | 0 | erro de hoje | erro de 1 dia ou mais (`CRM_ERRO_DIAS`) | — |
| `crm_fila` | registros parados | vazia ou menos de 60 min | 60 min ou mais (`CRM_PARADA_MIN`) | 24 h ou mais (`CRM_PARADA_HORAS`) | — |
| `crm_contratos` | contratos achados na CN9 | todos os da ZA3 existem | — | sucesso sem contrato | nenhum gerado |
| `crm_medicoes` | `medidos/total` | há contrato | — | — | sem contrato |
| `crm_retorno` | retornados | S sem pendência | S com A | algum E | não implementado (P11) |
| `crm_cad_produtos` | % com preço vigente | 90% ou mais | 60% ou mais | abaixo de 60%, ou nenhum produto ativo | — |
| `crm_cad_tabelas` | tabelas vigentes | com itens com preço | vigente sem preço | nenhuma | — |
| `crm_params` | `n/13` | `MV_ZCRMMOD` = 2 e `MV_ZMAILPP` preenchido | modo ≠ 2 ou sem e-mail | — | — |

## Produção × Teste

- **Leitura.** O `GET /api/integracoes/<customer>` passa a devolver `outra`: a
  última coleta da outra base (indicadores, quando e grupos), lida só do
  Supabase.
- **Comparação.** A caixa do CRM mostra os indicadores do grupo lado a lado nas
  duas bases.
- **Coleta.** O botão **⚡ Produção + Teste** (na barra, só com o grupo ligado,
  e repetido dentro da caixa) coleta as duas bases, uma depois da outra.
- **Grupo desligado na outra base.** O botão liga o grupo lá antes de coletar
  (pede confirmação e mantém os grupos que a base já monitora).
- **Outra base sem cadastro.** O botão coleta só a base atual e avisa.

Pela decisão de 27/10, a integração roda plugada na produção do CRM e do
Protheus. A Base de Testes mostra o que foi exercitado nos protótipos; a
Produção mostra a prontidão dos cadastros e o fluxo real.

## Tela

- Barra: **Monitorar ☐ RH ☐ TOTVS Transmite ☐ CRM × iPaaS** e **⚡ Produção + Teste**.
- Nove cartões do grupo, com o status sempre em ícone e rótulo.
- **Funil.** Recebidas → Liberadas → Tratadas → Projetos → Contratos → Medidos → Retorno.
  - A queda só é marcada onde a cardinalidade é a mesma: liberadas contra recebidas, tratadas contra liberadas e contratos contra tratadas. Projeto é um por OV; contrato é um por proposta.
  - "Medidos" aparece como "de N", sem alerta, porque a medição vem depois, pelo cronograma.
- **Listas.**
  - Pendentes: causa com quem resolve, e "já com sucesso depois?".
  - Rastreio: "✕ não está na CN9" em texto.
  - ZA3 por etapa, projetos, contratos e medições.
  - Seção **Protheus → CRM**: produtos por tipo com o % com preço, tabelas com vigência, produtos sem preço e parâmetros.

## Testes

- `python3 docs/testes/integracoes-crm-back.py`: 319 asserções. Cobre o SQL de
  cada bloco e variante (sem `;`, sem relógio do banco, sem `<> ''`, sem
  subconsulta em agregação, máscara de token, corte, SQL Server), a causa do
  erro, a idade na fila e os níveis de cada cartão nos cenários saudável, com
  problema, produção vazia e ZA3 ausente.
- `python3 docs/testes/integracoes-rotas.py`: a coleta só-CRM com a REST
  fingida (14 consultas, memo pela variante CLOB, causa anotada, `outra` no
  payload, sem healthcheck) e a rota `/grupos` aceitando `crm`.
- `node docs/testes/integracoes-crm-front.js`: 35 asserções (checkbox, botão,
  cartões, funil, comparação das bases, causa, rastreio, cadastros, coleta nas
  duas bases ligando o grupo na outra e zero erro de JS).

## Para ligar na Dígitro

1. Rodar `docs/sql/2026-10-30-integracoes-crm.sql` no Supabase. Ele aceita o
   grupo `crm` e liga o grupo nas duas bases da Dígitro. O ⚙ Ambiente das duas
   bases já existe: Produção na 10207 e Testes na 10257, environment
   desenvolvimento.
2. Na aba Integrações, clicar em **⚡ Produção + Teste**.
3. Se algum bloco vier cinza por campo inexistente, conferir o dicionário pelo
   **🗄 Scripts SQL** no console TCloud. Os candidatos são `CN9_DTINIC`,
   `CND_SITUAC` e `B1_ZFATURA` (este tem variante).

## Fora deste patch

- **Fila do envio Protheus → CRM.** Entra quando o P1 definir o gatilho e a
  tabela de controle.
- **Conferência com o lado CRM e iPaaS.** Seria a contagem de oportunidades
  contratadas no CRM, ou o monitor do iPaaS, cruzada com a ZA3, e é o que
  fecha a pergunta "alguma proposta se perdeu no transporte?". Depende de
  acesso ao monitor do iPaaS (P3).
- **Coleta automática pelo pg_cron.** Uma rota `/api/cron/integracoes`, no
  molde das outras coletas.
