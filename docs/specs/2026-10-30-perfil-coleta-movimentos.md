# Perfil de coleta de movimentos — a REST respeitando o que cada cliente mede

*30/10/2026. Gatilho: a Cobertura da Dígitro em 0/41 em produção, 18 "faltantes".*

## O problema

A coleta automática de movimentos (spec `2026-09-01-coleta-rest-protheus.md`)
era **um script por cliente**, o mesmo nas duas bases, rodado de uma vez pelo
`⚡ Coletar agora` da sub-aba Movimentos. Na Dígitro isso deu errado de três
jeitos, todos silenciosos:

1. **Script errado gravou produção sem reclamar.** Em 22/10 às 11:29 o script
   salvo como "movimentos" era um diagnóstico de dicionário (`GCT_CAMPO`,
   `GCT_TABELA`). A coleta de produção gravou 1.109 linhas disso. Depois o script
   foi trocado pelo D10 de contratos, mas só a base de **Testes** foi coletada de
   novo. Resultado: produção com 0/41, parecendo base parada.
2. **Cenário sem pergunta virava "faltante".** O D10 da Dígitro mede 14 análises
   de contratos e **nenhuma de SE5**. Os 11 cenários `SE5_BANCARIO` apareciam
   como *Faltante* ("não aconteceu"), quando a verdade é "ninguém perguntou à
   base". São ações diferentes: operar × ligar a medição.
3. **Cada cliente mede outra coisa.** A Dígitro mede o fluxo de contratos e a
   Olim mede fiscal, financeiro e compras. O TFDPHR00 roda em **Postgres**, e o
   gerador só sabia Oracle/SQL Server. Uma tabela de módulo não implantado
   (`ORA-00942`, caso da Açosul) derruba o script inteiro. E o teto de ~146 KB
   e 60 s vale para tudo junto.

Além disso, a aba **Cobertura**, que é onde se decide, não tinha botão de
coleta. Para atualizar, era preciso ir até a sub-aba e coletar cada base
separadamente. Foi assim que Teste e Produção ficaram fora de sincronia.

## A decisão

### 1. Perfil de coleta = script salvo + blocos

`cockpit.monitmov_perfil` (uma linha por cliente) e `cockpit.monitmov_blocos`.

- O **script salvo** (🗄 Script SQL) continua sendo o primeiro bloco e **não é
  copiado**: duas cópias divergiriam no primeiro "Salvar" do modal. No perfil
  só se liga e desliga.
- Os **blocos do catálogo** (`SD2_FISCAL`, `SE5_BANCARIO`) saem do gerador do
  D5 (`pecasMovD5`), agora com três dialetos: Oracle, SQL Server e
  **PostgreSQL**.
- Os **blocos próprios** são SQL colado no layout do D5.

Cada bloco declara as análises que mede, lidas do próprio SQL
(`'XXX_YYY' AS ANALISE`) ou informadas à mão. Isso vale também quando a resposta
volta vazia.

### 2. Particularidade por base: placeholders

`{{SUFIXO}}`, `{{EMPRESA}}`, `{{FILIAL}}` saem do ⚙ Ambiente **daquela base**;
`{{DT_INI}}`, `{{DT_FIM}}`, `{{PERIODO}}` saem da janela do perfil (dias; 0 =
base inteira, que vira `19000101–20991231`. Nunca `''`: no Oracle `''` é NULL e
o BETWEEN não traz nada). O mesmo bloco serve teste e produção mesmo com sufixo
ou filial diferentes. Script antigo, com `010` fixo, passa intacto.

Bloco em dialeto diferente do banco da base é **pulado** ("não se aplica"),
em vez de virar erro de sintaxe.

### 3. A coleta vira um LOTE, bloco a bloco

`cockpit.monitmov_lotes` guarda o plano, o resultado de cada bloco (com o CSV
enquanto o lote está aberto) e o resumo.

```
tela / cron                       backend                         base
───────────                       ───────                         ────
POST /lote?ambiente=     ──►  plano (blocos × análises)
POST /lote/<id>/bloco/<b> ─►  placeholders → /tscmonit/query ──►  CSV
  … um por bloco (60 s cada) …
POST /lote/<id>/fechar   ──►  junta CSVs → trava → _gravar_movimentos
```

- **Tabela inexistente** (`ORA-00942`, `Invalid object name`,
  `relation … does not exist`) = bloco *não se aplica*. Não trava o lote.
  **Coluna inexistente** (`ORA-00904`) **é erro**: o script está errado, e
  isso precisa aparecer.
- Bloco que falhou → o fechamento devolve 409 com a lista. A tela oferece
  *Tentar de novo (n)*, que roda só os blocos que falharam no mesmo lote, ou
  *Gravar só o que rodou*. Nesse caso as análises do bloco ficam como não
  medidas e a medição sai marcada como `parcial`.
- A gravação é a **de sempre** (`_gravar_movimentos`), uma medição por base e
  data, idempotente.

### 4. Trava de consistência

Antes de gravar: se o cliente **tem cenários** e a coleta **não mede nenhuma**
das análises com cenário, nada é gravado (409 `recusa`). Na tela aparece
*Gravar mesmo assim* (`forcar=1`), e a medição fica marcada como `forcado`, com
aviso na Cobertura. A mesma trava vale no `/coletar?tipo=movimentos` legado: o
caminho antigo não pode ser a porta por onde o script errado ainda grava.
Cliente sem cenário passa, porque ainda está montando a lista.

Avisos que não bloqueiam: análise devolvida que nenhum bloco declara, análises
que não se aplicam e análises que ficaram sem medir.

### 5. NÃO MEDIDO

A medição grava no payload `analises_medidas`. `_cobertura(…, medidas)`:

| Status | Regra |
|---|---|
| `COBERTO` | casou com observado e `QTDE > 0` |
| `NAO_MEDIDO` | `QTDE = 0` e a análise **não foi perguntada** nesta medição |
| `FALTANTE` / `OPCIONAL` | perguntada e sem movimento |

Uma medição antiga ou subida à mão não tem `analises_medidas`. Nesse caso
**vale o que veio no arquivo**: análise ausente do arquivo não foi medida.

Na aba Cobertura (testes × produção), o cenário é *Não medido* só quando
**nenhuma** das duas bases perguntou. Se uma delas perguntou e não achou nada,
ele é *Faltante*. O KPI novo "Não medidos" aponta para o 🧩 Perfil, e
"Faltantes" passou a dizer "medido e sem movimento". A evolução ganhou
`nao_medidos` na série e o status na matriz.

### 6. Coleta agendada (cron)

`GET /api/cron/coleta-movimentos` (Bearer `CRON_SECRET`), pelo pg_cron do
Supabase:

- pega **uma base por vez**: primeiro um lote do cron que ficou aberto, depois a
  base agendada há mais tempo sem coleta gravada;
- respeita a agenda do perfil (`diaria` = 20 h desde a última gravada,
  `semanal` = 6,5 dias) e as bases da agenda (`*`/`producao`/`teste`);
- orçamento de 48 s por chamada. Bloco novo só começa com 12 s de folga, e o
  lote que não terminou fica aberto para a próxima chamada **retomar**;
- lote do cron que falhou ou foi recusado não é refeito antes de 6 h. O log fica
  em `protheus_coletas` com `disparado_por = 'cron'`;
- `?customer=&ambiente=` força uma base (teste manual), ignorando agenda e
  espera.

Agenda padrão: **desligada**. Ninguém passa a ser coletado sem que o consultor
ligue no perfil.

Job sugerido (madrugada, 02:00–03:50 em Brasília, de 10 em 10 min; o comando
copia o Bearer do job 7, então o segredo não aparece no SQL):

```sql
select cron.schedule('projetos-coleta-movimentos', '*/10 5-6 * * *',
  replace((select command from cron.job where jobid = 7),
          '/api/cron/sync', '/api/cron/coleta-movimentos'));
```

## A tela

- **Cobertura**: os botões **⚡ Atualizar pela REST**, que roda testes e
  produção em sequência, e **🧩 Perfil de coleta** entram no rail. A mesma
  sub-aba Movimentos ganha o 🧩 Perfil, e o seu **⚡ Coletar agora** passa pelo
  lote, só na base aberta.
- **⚡ Atualizar pela REST**: um quadro por base, com o selo, o environment, o
  banco e o sufixo, e uma linha por bloco: ✓ / ✕ / – (não se aplica) / ⏳,
  linhas, segundos e erro. No fim, a medição gravada e os avisos, ou os botões
  de retomada e recusa.
- **🧩 Perfil**: as bases, as análises com cenário (com *medida por bloco
  ativo* ou *⚠ Não medido* e o botão **+ do catálogo**), os blocos (ativar,
  editar, remover), a janela, a agenda e as últimas coletas.

## Limites e cuidados

- Bloco acima de 140 KB é recusado com o tamanho na mensagem. Divida em dois.
- Salvar bloco aplica a trava de escrita do `/fase`, **menos** `DBMS_`: a
  contagem blindada (`DBMS_XMLGEN`) é leitura e a base aceita, e o script da
  Olim roda assim desde setembro.
- O CSV do lote é apagado ao gravar. Fica só o resumo por bloco.
- Lote aberto antigo da mesma base é marcado `abandonado` quando outro abre.

## Como foi testado

`docs/testes/movimentos-perfil-lab.py`: Postgres local
(`movimentos-perfil-lab-schema.sql` + a migração) e um stub HTTP do
TSCMONITREST. 63 checagens pelas rotas Flask:

- coletar legado (grava, registra `analises_medidas`, recusa o script GCT sem
  apagar a medição boa);
- `NAO_MEDIDO` × `FALTANTE`;
- blocos: salvar, recusar escrita, aceitar `DBMS_XMLGEN`;
- sufixo diferente por base (`SE5010` × `SE5020`), período trocado e banner
  cortado;
- tabela inexistente = não se aplica, bloco Postgres pulado numa base Oracle;
- falha de coluna → 409 → parcial;
- trava → lote continua aberto → forçar grava;
- cron: sem Bearer = 401, sem agenda não faz nada, respeita a coleta recente,
  coleta as duas bases, janela de 30 dias, chamada forçada, log
  `disparado_por=cron`, orçamento que estoura deixa o lote aberto e a chamada
  seguinte retoma o mesmo lote.

A tela foi testada no Chromium contra o mesmo laboratório, com a situação real
da Dígitro (produção GCT e teste D10):

- a Cobertura antes mostra 2 *Não medidos* (SE5);
- 🧩 → *+ do catálogo* liga o SE5;
- ⚡ grava as duas bases e o painel volta com SE5 medido;
- bloco quebrado → *Gravar só o que rodou* → recusa → *Gravar mesmo assim*
  (preservando o parcial).

O gerador foi conferido nos três dialetos. A migração rodou num Postgres 16
limpo.
