# Aba Integrações — grupo TOTVS Transmite

*16/10/2026. Piloto: RIO DESERTO (`TFDPHR00`), base de Produção.*

**Pedido.** Acompanhar no Dashboard de Projetos os erros do TOTVS Transmite da
Rio Deserto. A coleta lê pela mesma REST (`TSCMONITREST`) que já existe na aba
Integrações, e não por um painel separado.

**Base técnica.** São quatro fontes:
- o diagnóstico Transmite Rio Deserto (label Rio Deserto no Gmail, 12
  reclamações da Kelen entre maio e outubro);
- o plano de verificação montado depois da reunião interna com o Murilo
  (rotinas COMXCOL e IMPTRATOOL);
- o log `imptratoolupd.log`;
- o ticket 30316540.

## A pergunta que o grupo responde

A pergunta é a da Kelen: **"a nota que eu classifiquei vai ter a Confirmação
da Operação na SEFAZ a tempo?"** O caminho da nota tem cinco passos, e cada um
pode parar:

```
SEFAZ → Transmite → SCHEDIMPTRA/COMXCOL ──► CKOCOL + SDS (Importador XML)
                                              │  DS_STATUS B = revisão cadastral
                                              ▼
                                usuário classifica (SF1, F1_STATUS ≠ vazio)
                                              │
                              SCHEDUPDTRA grava CKO_STRAN = 4 e devolve
                              "Classificada" ao Transmite
                                              │
                         Transmite manifesta a Confirmação com F1_DTDIGIT/F1_HORA
```

A tela mostra só o lado Protheus. Saber se a ciência ou a confirmação saiu é
pergunta para o portal do Transmite. A conferência com o CSV exportado do
Transmite fica para a fase 2.

## Grupos por base

`cockpit.protheus_ambientes.integ_grupos text[]` recebe `rh`, `transmite` ou os
dois (migração `docs/sql/2026-10-16-integracoes-transmite.sql`).

- **Nulo = só RH.** Nenhuma base em produção muda até alguém ligar o grupo.
- **Base de RH** não paga as consultas de Compras.
- **Base de Compras** não mostra oito cartões cinza de Quírons e Ahgora.
- **Sem RH, sem healthcheck.** O healthcheck da Quírons só é chamado com `rh`
  ligado.
- **Grupos lidos ficam gravados.** A coleta salva os grupos que leu em
  `blocos._meta.grupos`, como já faz com o corte. Se os grupos da base forem
  trocados depois, a barra avisa "Grupos alterados", como faz com "Corte
  alterado".
- **Tela.** "Monitorar ☐ RH ☐ TOTVS Transmite" na barra da aba grava pelo
  `POST /api/integracoes/<customer>/grupos` `{"grupos": [...]}`. É preciso ao
  menos um grupo, e só grupos conhecidos são aceitos. A gravação não dispara
  coleta.

## Blocos (`_tra_scripts`)

As regras são as mesmas do RH:
- datas calculadas no Python, no fuso de Florianópolis, sem
  `SYSDATE`/`GETDATE`/`CURRENT_DATE`;
- sem `;` no fim;
- só `SELECT`;
- vazio robusto (`_integ_vazio`).

Para "preenchido" foi criado `_integ_preenchido` = `RTRIM(col) > ' '`, porque
`<> ''` nunca é verdadeiro no Oracle. A `CKOCOL` é tabela do TOTVS Colaboração e
**não leva sufixo**. As demais tabelas usam o sufixo do ⚙ Ambiente.

A janela é de **120 dias** de `F1_DTDIGIT`/`CKO_DT_IMP`/`DS_DATAIMP`, porque o
prazo do evento é de 90 dias. Se o corte da base for mais recente que isso, vale
o corte.

**Nota de terceiro**: `F1_CHVNFE` preenchida e `F1_FORMUL <> 'S'`.

| id | tipo | o que lê |
|---|---|---|
| `tra_config` | resumo | SX6: `MV_NGINN`, `MV_NGLIDOS`, `MV_IMPXML`, `MV_DTINITR`, `MV_XMLDIAS`, `MV_COLEDI`, `MV_EXCEDI`, `MV_APITRAN`, `MV_DOCIMP`, `MV_COMCOL1..3`, `MV_HORARMT`, `MV_HORANFE`. **`MV_APITRAN` vem mascarado** (`(preenchido)` ou vazio), porque pode guardar chave de API. |
| `tra_fila` | resumo | CKOCOL por `CKO_CODEDI` × `CKO_STRAN`: quantidade, mais antigo, mais recente, parados há mais de 30 e de 60 dias |
| `tra_sem_retorno` | resumo | SF1 classificada (`F1_STATUS` preenchido) com XML na CKOCOL sem `CKO_STRAN = 4`, por filial, em faixas de idade da **emissão** (60–80, 80–90, mais de 90). Usa `EXISTS` e não `JOIN`, porque um XML reimportado deixa duas linhas na CKOCOL e dobraria a contagem. `CKO_STRAN` vazio conta como não classificado. |
| `tra_futuras` | resumo | SF1 com `F1_DTDIGIT > hoje`, ou hoje com `F1_HORA > agora + 10 min` (folga para o relógio do AppServer) |
| `tra_revisao` | resumo | SDS por `DS_STATUS`. Tem três variantes: por `DS_DATAIMP`, por `DS_EMISSA` e sem data. O nome do campo muda entre releases, e campo inexistente cai para a próxima variante. |
| `tra_sem_monitor` | resumo | SF1 classificada com chave e **sem SDS**, ou seja, digitada direto no Documento de Entrada, fora do Importador |
| `tra_sem_retorno_lista` | detalhe (300) | as notas do cartão 1: documento, fornecedor, emissão, digitação, `CKO_STRAN`, `CODEDI`, `DS_STATUS` e chave |
| `tra_futuras_lista` | detalhe (100) | as notas com data ou hora no futuro |
| `tra_fila_antigos` | detalhe (200) | XML há mais de 30 dias sem 4, com a situação na SF1 (não lançada, pré-nota ou classificada). É aqui que aparecem os 24 que o Transmite recusa por `DisponivelCancelamento`. |
| `tra_revisao_lista` | detalhe (200) | documentos em `DS_STATUS = 'B'`, em duas variantes |

Os resumos de todos os grupos rodam antes dos detalhes. Se o tempo acabar,
fica faltando a lista, e não o número.

## Indicadores (`_tra_indicadores`, grupo `transmite`)

| chave | valor | verde | amarelo | vermelho |
|---|---|---|---|---|
| `tra_sem_retorno` | notas classificadas sem 4 | 0 | digitadas hoje ou ontem | mais antiga digitada há 2 dias ou mais (o SCHEDUPDTRA roda todo dia) |
| `tra_prazo` | notas sem retorno com 60 dias ou mais de emissão | nenhuma | 60–80 dias | 80–90 dias, ou vencida (mais de 90) |
| `tra_hora_futura` | notas com data ou hora à frente | 0 | — | 1 ou mais (o evento sai com esse horário e a SEFAZ recusa). Com data adiantada, o texto aponta a data-base. Cita DMANMAT02-56222 e o PE A140IGRV. |
| `tra_revisao` | documentos em B | 0 | menos de 7 dias | 7 dias ou mais. O texto lista os demais status, crus. |
| `tra_fila` | XML há mais de 30 dias sem 4 | 0 | 30–60 dias | mais de 60 dias |
| `tra_entrada` | dias desde o último XML importado | até 2 | 3–4 | 5 ou mais, ou nenhum XML na janela |
| `tra_sem_monitor` | notas fora do Importador | 0 | 1 ou mais | — |
| `tra_params` | parâmetros encontrados `n/14` | `MV_IMPXML` .T. e `MV_DTINITR` com data | `MV_IMPXML = .F.`, ou `MV_DTINITR` vazio ou inválido | — |

Bloco não lido vira **cinza com o motivo**. Tabela ausente é informação, e não
erro, igual ao grupo de RH.

Os limites estão em constantes no topo do bloco (`TRA_PRAZO`,
`TRA_PRAZO_AMARELO`/`VERMELHO`, `TRA_FILA_*`, `TRA_JANELA` e `TRA_FOLGA_MIN`).
O prazo de 90 dias é o adotado no diagnóstico de 16/10 (3 meses). Se a regra
fiscal confirmada for outra, basta trocar a constante. O front repete os três
números do prazo (`INT_TRA_*`) para pintar a coluna "Prazo do evento" da lista.

Só o código `4 = Classificada` de `CKO_STRAN` e o `B = revisão cadastral` de
`DS_STATUS` estão documentados nos tickets. Os demais códigos aparecem crus na
tela ("2 · não classificada"), sem inventar significado.

## Tela

- **Caixa "TOTVS Transmite — classificação e evento na SEFAZ".** Mostra as
  listas acima. A coluna **Prazo do evento** traz texto e ícone
  ("! 73 d · faltam 17", "✕ 107 d · vencido"), nunca só cor.
- **Caixas de RH.** As de Quírons, Ahgora, eSocial e Configuração só aparecem
  se a coleta leu o grupo RH.
- **Histórico.** Mostra só as colunas de indicadores que existem na série.
- **Confirmação e barra "Coletando".** Dizem o que vai ser lido conforme os
  grupos ligados.

## Testes

- `python3 docs/testes/integracoes-back.py`: SQL de cada bloco (sem `;`, sem
  relógio do banco, sem `<> ''`, CKOCOL sem sufixo, faixas de data, máscara,
  variantes, corte) e as regras de nível de cada cartão.
- `python3 docs/testes/integracoes-rotas.py`: coleta só-Transmite sem nenhuma
  consulta de RH e sem healthcheck, variante da SDS, grupos gravados na coleta,
  rota `/grupos` e scripts.
- `node docs/testes/integracoes-front.js`: cartões e caixas por grupo, prazo em
  texto, escape da chave, checkboxes e aviso de "Grupos alterados".

## Para ligar na Rio Deserto

1. Rodar `docs/sql/2026-10-16-integracoes-transmite.sql` no Supabase.
2. Cadastrar o ⚙ Ambiente de `TFDPHR00` produção:
   - URL `…/rest/tscmonit`;
   - token = `MV_TSCTOKN` da base;
   - banco;
   - sufixo `010`.

   Hoje não há linha para a Rio Deserto em `protheus_ambientes`.
3. Marcar ☑ TOTVS Transmite (e desmarcar RH) na barra da aba.
4. Clicar em ⚡ Coletar agora. Conferir o nome da tabela `CKOCOL` e os campos
   da SDS pelo **🗄 Scripts SQL** no console TCloud, se algum bloco vier cinza.

## Fase 2 (fora deste patch)

- **Conferência com o Transmite.** Upload do CSV "classificados sem ciência"
  exportado do portal Transmite e cruzamento por chave com a SF1/CKOCOL. Isso
  fecha a pergunta "o evento saiu?".
- **Coleta diária automática.** Feita por pg_cron, como as outras coletas.

## Por que o Importador parou: CKO_CODERR (30/10/2026)

**Pedido.** Deixar fixo na aba o quadro "motivo de cada erro do Importador". Na
Rio Deserto ele mostrou que o problema não estava nas transferências entre
filiais: era cadastro de fornecedor, notas que o Importador não trata e XML
cancelado ou sem destino no grupo.

**Blocos novos**

| id | tipo | o que lê |
|---|---|---|
| `tra_erros` | resumo | CKOCOL sem `CKO_STRAN = 4` na janela, agrupada por `CKO_CODERR` × `CKO_STRAN` × tipo do documento. O tipo é NFS-e quando a chave não tem 44 posições, CT-e quando o modelo é 57, e NF-e nos demais casos. |
| `tra_erros_msg` | detalhe | o texto gravado pelo Importador (`CKO_MSGERR`), um XML por código |
| `tra_erros_lista` | detalhe (300) | os XML com código, um a um, com o destinatário (`CKO_CNPJIM`) |

**Regras que o SQL tem que seguir**

- **Funções por banco.** `_tra_sql_fns` usa `SUBSTR`/`LENGTH` no Oracle,
  `SUBSTRING`/`LEN` no SQL Server e `SUBSTRING`/`LENGTH` no Postgres.
- **Classificação em subconsulta, sem concatenação.** O DBAccess do Postgres
  reescreve `||` com `CASE` dentro e quebra o SQL. Foi visto em 30/10, com o
  erro "syntax error at or near )".
- **Agrupamento.** Usa as colunas da subconsulta, porque o Oracle não aceita
  `GROUP BY` por apelido nem por posição.

**Leitura da mensagem (memo)**

- **Postgres.** O DBAccess grava o memo em BYTEA.
  `SUBSTRING(CAST(CKO_MSGERR AS VARCHAR), 1, n)` devolve o hexa (`\x434f4d…`),
  e o `_tra_msg` decodifica em latin-1 e tira o prefixo "COM052 - ".
- **Oracle e SQL Server.** Usam as mesmas variantes do memo do RH. A última
  variante vem sempre sem mensagem.
- **Sem texto lido.** Se nenhuma variante devolver texto, vale o texto de
  `TRA_CODERR`.

**Quem resolve** (`TRA_CODERR`, com os textos lidos na base da Rio Deserto)

| Código | Motivo | Quem resolve |
|---|---|---|
| COM007 | Fornecedor inexistente na base | Cadastro |
| COM020 | CT-e cita documento de entrada inexistente | Cadastro |
| COM003 | Devolução/complemento de ICMS-IPI não é tratado pelo Importador | Fiscal (lançar à mão e manifestar no Transmite) |
| COM004 | NF-e de ajuste não é tratada pelo Importador | Fiscal |
| COM005 | Chave já registrada em outra nota de entrada | Duplicidade |
| COM044 | Documento de entrada já existe no Monitor | Duplicidade |
| COM036 / COM040 | CT-e / NF-e cancelada | Sem ação |
| COM052 | XML não pertence a nenhuma empresa/filial | Sem ação |
| outro | — | Não mapeado (ver a mensagem no Monitor) |

> O COM040/COM036 confirma a leitura do `DisponivelCancelamento` do Transmite:
> as chaves recusadas em 16/10 aparecem na base como "NF-e cancelada" e "CT-e
> cancelado".

**Cartão `tra_erros`**

- **Valor:** XML que pedem ação (cadastro, fiscal, duplicidade e não mapeado).
- **Níveis:** 0 = verde; o mais antigo com 7 dias ou mais = vermelho; abaixo
  disso = amarelo. Os "sem ação" aparecem só no texto.
- **Resumo gravado.** A coleta grava o resumo em
  `blocos.tra_erros.resumo` (`_tra_erros_resumo`, função pura), e o histórico
  ganha a coluna "Erros Importador".

**Ajustes na lista "sem retorno"**

- **Coluna Importador.** Separa "sem SDS" de "(vazio) · sem status" usando
  `TEM_SDS`. Antes, as duas situações apareciam como "sem SDS".
- **Coluna Tipo NF.** Mostra o tipo da nota (normal, complemento de ICMS,
  complemento de preço/frete…).
- **Legenda do `CKO_STRAN`.** Agora vai completa: 0 não processado,
  1 pendente, 2 Exportada, 3 Integrada, 4 Classificada.
