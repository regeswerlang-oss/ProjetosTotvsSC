# Transferência de cadastros entre bases (Produção ↔ Teste)

*04/11/2026. Piloto: Dígitro.*

## O problema

A aba Cadastros já lê as duas bases do cliente pela REST (TSCMONITREST): conta
o que existe em cada tabela e mostra a evolução. Quando falta um cadastro numa
das bases (cliente criado na produção que o protótipo da teste precisa, produto
homologado na teste que precisa subir), o caminho é exportar e importar à mão,
tabela a tabela. O pedido: **escolher uma tabela e transferir os registros de
uma base para a outra pela própria aba Cadastros**.

## A decisão: um fonte irmão, não afrouxar o que existe

O TSCMONITREST é só de leitura de propósito — a trava (só SELECT/WITH, palavra
proibida por palavra inteira) é o que permite ter uma REST que executa SQL na
base do cliente. Mexer nela para aceitar escrita misturaria as duas coisas.

Por isso a gravação mora num **fonte separado, `fontes/tlpp/TSCTRANSREST.tlpp`**,
publicado no mesmo `[HTTPURI]` (`…/rest/tsctrans`). A URL cadastrada no
⚙ Ambiente serve aos dois: o painel troca `/tscmonit` por `/tsctrans`.

| Rota | O que faz |
|---|---|
| `GET /tsctrans/ping` | identidade, versão, `token_ok`, `gravacao_liberada` |
| `POST /tsctrans/ler` | `{tabela, filtro?, apos_recno, limite}` → registros em JSON tipado pela `DbStruct`, paginados por `R_E_C_N_O_` (deletados fora) |
| `POST /tsctrans/gravar` | `{tabela, modo, simular, registros, filial_de?, filial_para?, campos_excluir?}` → incluídos, alterados, ignorados, erros por chave |

Ler pelo fonte novo (e não pelo `/tscmonit/query`) é necessário: o CSV do
TSCMONITREST troca `;` por espaço dentro do valor e não carrega memo — serve
para contar, não para copiar.

## Como grava

- Chave = **índice 1 da tabela na base destino** (`IndexKey(1)`), montada a
  partir dos valores recebidos; `DbSeek` decide inclusão × alteração.
- Modo **incluir** (padrão): o que já existe é ignorado. Modo
  **incluir_alterar**: sobrescreve só os campos recebidos.
- Só campos que existem nas duas bases; os que faltam no destino voltam em
  `campos_sem_destino`. Conversão pelo tipo/tamanho **do destino**.
- `filial_de`/`filial_para` troca o conteúdo de `<prefixo>_FILIAL` quando a
  máscara muda entre as bases (01 × 010101).
- Gravação direta (`RecLock`/`FieldPut`/`MsUnlock`), registro a registro: um
  erro não derruba o lote. **Não** roda ExecAuto/MVC — sem validações de tela,
  gatilhos ou pontos de entrada. É cópia de cadastro, não digitação.

## Proteções

1. Token `MV_TSCTOKN` (o mesmo do TSCMONITREST). Sem ele, fechado.
2. **`MV_TSCGRAV` (tipo L) = .T. na base DESTINO**. Sem o parâmetro, `/gravar`
   só simula (403). Produção nasce fechada: basta não criar o parâmetro lá.
3. Simulação é o padrão nas duas pontas (`simular` ausente = simula).
4. Painel: só interno, fora do "ver como"; origem ≠ destino; dicionário
   (SX\*, XX\*, SIX) recusado; tabela de movimento só com a caixa marcada;
   filtro com a mesma trava de palavras do TSCMONITREST.
5. Gravar em **Produção** exige admin **e** a frase `PRODUCAO <TABELA>`.

## Rotas do painel

| Rota | O que faz |
|---|---|
| `POST /api/protheus/<cli>/<amb>/transferir-ping` | ping do TSCTRANSREST daquela base |
| `POST /api/protheus/<cli>/transferir` | **um lote**: lê até N na origem e grava/simula no destino |

Cada lote cabe numa invocação da Vercel (leitura ≤ 22 s, gravação com o que
sobrar dos 50 s). O navegador repete com `ultimo_recno` até `fim`. Lote
gravado entra em `cockpit.protheus_coletas` com `tipo = 'transferencia'` no
ambiente destino (`docs/sql/2026-11-04-transferencia.sql`).

## A tela

Aba Cadastros → rail de ações → **⇄ Transferir entre bases**. Mostra o ping das
duas bases (fonte publicado? gravação liberada?), pede tabela, modo, filtro,
de-para de filial, campos a não copiar e tamanho do lote. Simula por padrão;
desmarcar "Simulação" troca o botão para **Transferir**. Progresso por lote,
chave usada, campos sem destino e a lista de erros por chave. "Parar"
interrompe entre lotes.

## Para publicar numa base

1. Compilar `TSCTRANSREST.tlpp` no RPO do ambiente do REST e reiniciar o
   serviço REST (rotas anotadas só entram na subida).
2. Base que vai **receber**: criar `MV_TSCGRAV` (L) = `.T.`. Base que só
   fornece: não precisa.
3. No painel, o ping deve mostrar ✔ e "gravação liberada" no destino.

## Como foi testado

`docs/testes/transferencia-rotas.py` — Flask real, banco e as duas bases
fingidos (SA1 em memória, chave do índice 1, MV_TSCGRAV por base): simulação
sem gravar, 3 lotes de 3, de-para de filial, incluir × incluir_alterar, campo
excluído, guarda de produção (frase, admin, MV_TSCGRAV), recusas (movimento,
dicionário, filtro, modo, inativo), fonte não compilado (404) e log. Tela
aberta no Chrome com `/api/*` interceptado: ping das duas bases, 3 lotes
simulados, troca origem/destino e prompt de confirmação na produção.

## Aba Tributos (04/11/2026, tarde) — TSCTRANSREST 1.1

**Lateral:** a aba Tributos ganhou o grupo de ações com o mesmo
**⇄ Transferir entre bases**, listando só as tabelas de cadastro do
Configurador e com origem padrão = Base de Testes.

**Botão ⇄ por linha** (só interno, com as duas bases coletadas): em *O que
falta subir para a Produção* e em cada linha da *Comparação registro a
registro* que tenha chave estável — ↑ leva Teste → Produção (só em Teste,
conteúdo diferente), ↓ leva Produção → Teste (só na Produção); o modal permite
inverter. `POST /api/tributos/<cli>/transferir/plano` monta o **pacote** a
partir das últimas coletas (não toca nas bases):

1. o registro, filtrado e **localizado no destino pela chave de negócio**
   (`TRIB_CHAVE`/SIX sem ID) — nunca pelo índice 1, que no FISA170 pode usar o
   ID técnico. Por isso o fonte 1.1 aceita `chave` e busca por SQL nesses
   campos (havendo mais de um, o de maior R_E_C_N_O_);
2. na F2B, os cadastros referenciados (`TRIB_REFS`) que o destino não tem —
   perfil conferido com o `F20_TIPO` certo;
3. registro incluído com ID técnico leva os **itens filhos** ligados por
   `<FILHA>_ID<PAI>` (F21..F26 → F20), com o mesmo ID;
4. registro que já existe no destino é **atualizado sem as colunas `_ID*`** (o
   ID do destino e os filhos dele ficam) — sem o versionamento do FISA170, e a
   tela avisa;
5. versão anterior (`*_ALTERA = '1'`) fica fora da leitura.

Filtros portáveis (`RTRIM(col) = 'v'`; vazio = `RTRIM(col) = '' OR ... IS
NULL`, porque no Oracle `RTRIM('  ')` é NULL). O navegador roda passo a passo
pelo lote da aba Cadastros; Produção como destino pede a frase uma vez
(`PRODUCAO <TABELA>` da linha) e cada passo leva a sua. Depois de gravar, a
tela pede nova coleta para a comparação refletir.

> Fórmulas (CIN) ligadas por outro nome de campo que não `<CIN>_ID<PAI>` não
> entram no pacote automático — conferir na comparação após recoletar.

Teste: `docs/testes/transferencia-rotas.py` agora com 63 verificações (plano:
regra + alíquota + perfil do tipo certo + itens F21 pelo ID, atualização sem
ID, sem chave → 409, sentido invertido, `chave` repassada ao fonte).
