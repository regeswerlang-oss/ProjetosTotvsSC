# Aba Tributos — Configurador de Tributos (FISA170), Produção × Teste

*30/10/2026. Piloto: DÍGITRO (`000348D0`), Base Produção (10207) e Base de Testes (10257).*

**Pedido.** Um painel só para o Configurador de Tributos, nas duas bases:
comparar os cadastros base a base, as quantidades das principais tabelas e as
regras incluídas, de forma visual, para mostrar ao cliente o que está em uma
base e na outra, e o que ainda falta incluir. Coleta pela REST, com botão de
coletar agora.

**Base técnica.** TDN *CFGTRIB – Configurador de Tributos* (tabelas, campos
da Regra de Cálculo, carga CBS/IBS com prefixos TR/TB/TA/TPP, carga só na
filial logada), *Cadastro de Perfis – Boas Práticas* e o artigo da Central
*FISA170 – Quais tabelas fazem parte do Configurador de Tributos*.

## As três perguntas (nesta ordem)

1. **O que está em Teste e ainda não subiu para a Produção?** E o contrário
   (regra criada direto na Produção).
2. **O que existe mas não funciona?** Regra apontando para tributo, perfil,
   base, alíquota ou escrituração que não existe (ou que só existe em outra
   filial); regra vigente com status de teste na Produção; vigência encerrada.
3. **O que falta para a Reforma (CBS/IBSEST/IBSMUN)?** Por **filial**: a carga
   padrão do FISA170 roda só na filial logada.

## Decisões que custam caro se desfeitas

1. **Aba própria, liberável ao cliente.** Integrações é interna; esta foi pedida
   para mostrar ao cliente. O cliente lê; a coleta é `require_interno`.
2. **Retrato guardado** (`cockpit.trib_coletas`), não leitura ao vivo como o
   Compara. O cliente precisa ver sem disparar nada, e a comparação junta duas
   coletas feitas em momentos diferentes — a barra mostra quando cada uma foi.
3. **Dicionário antes do conteúdo.** A fase 0 lê `USER_TAB_COLUMNS`
   (`INFORMATION_SCHEMA` no SQL Server/Postgres), SX2, SX3 (título e `X3_CBOX`),
   SIX ordem 1 e `SYS_COMPANY`. As consultas de conteúdo são montadas com as
   colunas que EXISTEM naquela base: campo novo de expedição contínua numa base
   só não derruba a leitura — vira "dicionário diferente" na tela.
4. **Coleta faseada.** A função da Vercel morre em 60 s e são ~45 tabelas por
   base. Cada chamada lê o que couber (~45 s) e devolve `pendentes`; o front
   repete até esvaziar, Produção e depois Teste. A 1ª fase grava a linha com
   `status='coletando'`; a última muda para `ok` (ou `parcial`, se alguma
   leitura falhou). A tela sempre mostra a última **concluída**.
5. **Chave de negócio, nunca o ID técnico.** `F2B_ID`, `F21_IDF20` etc. são
   FWUUID gerados em cada base: diferem sempre. A chave é `TRIB_CHAVE`
   (ex.: F2B = filial + regra + início de vigência); sem ela, o SIX ordem 1
   sem as colunas `_ID*`; se só sobrar ID, a tabela é comparada **pelo
   conteúdo** (multiconjunto de registros). Colunas `_ID*` ficam fora da
   comparação e a tela diz quais foram ignoradas.
6. **"Mesmo conteúdo, outro código".** Um registro só em Teste cujo conteúdo
   (fora a chave e os IDs) é igual a um só na Produção é marcado como par —
   é o caso de perfil/regra renumerado entre bases.
7. **Migração com dependências.** Para cada regra só em Teste (ou divergente),
   a tela lista os cadastros que ela usa e que a Produção ainda não tem
   (alíquota, base, perfil, escrituração, tributo). Subir só a F2B quebra.
8. **Filial casa como `xFilial`.** O cadastro referenciado vale se a filial dele
   é vazia (compartilhado) ou prefixo da filial da regra. "Existe em outra
   filial" é achado próprio — é o erro típico de cadastro exclusivo.
9. **Movimento só conta.** F2D, F2F, CJ3, CJL, CJM e a apuração (F2H–F2M) não
   são lidos registro a registro: mostram que o Configurador já está sendo
   usado (e onde).
10. **Memo pelas variantes de sempre** (`_integ_memo_exprs`: BLOB → CLOB → sem
    o campo), 1.000 bytes. É o caso das fórmulas (CIN).

11. **Versão anterior fora da comparação.** O FISA170 não sobrescreve: alterar
    base, alíquota ou regra grava a nova e deixa a antiga com `*_ALTERA = '1'`
    (F27 000004 e F28 000019 na Produção da Dígitro). Vale o dado, não o
    `X3_CBOX`: o da CIN diz "0=Foi alterado", mas na Dígitro as 398 fórmulas
    vigentes têm '0' e as 3 antigas têm '1'. A tela mostra "(n ant.)".
12. **Perfil com tipo.** A F20 guarda os quatro perfis com `F20_TIPO` (01
    origem/destino, 02 participante, 03 operação, 04 produto) e o mesmo código
    existe em tipos diferentes (TPP001 é participante e produto). A referência
    da regra é conferida com o tipo certo; código que só existe em outro tipo é
    "existe, mas com outro tipo de perfil".
13. **`X3_CBOX` vem com espaço no lugar do `;`** pelo CSV da REST
    ("1=Em Teste 2=Aprovada"). O corte é pelo `<código>=`.
14. **Coerência (amarelo, para conferir):** descrição que fala de um tributo e
    regra que calcula outro; percentual na descrição diferente da alíquota
    amarrada; código fora do tamanho dos demais. E regra vigente que termina
    em até 90 dias (a CBS/IBS da Dígitro vai até 31/12/2026).

## Primeira leitura real — Produção da Dígitro, 30/10/2026 14:15

Coleta completa em 9 s (22 tabelas lidas, memo da CIN pela 1ª variante).
43 regras de cálculo, todas aprovadas e vigentes; nenhuma referência quebrada.
Achados: A00101 (CBSFED) e A00102 (IBSEST) terminam em 31/12/2026 e usam base
000003 e alíquota 000003 (zero, cClass 410999); as alíquotas TA001 (0,9%) e
TA0002 (0,1%) existem e nenhuma regra usa. E00302 e S00104 dizem 1% e usam a
alíquota 000016 (1,5%); E00307 diz "INSS 11%" e calcula ISS a 2,5%. A Base de
Testes (10257) recusou o TLS (`unexpected eof`) — REST fora do ar no dia.

## Tela

- Barra: cliente, **⚡ Coletar Produção + Teste** (só interno), **↻ Atualizar**;
  quando e de que environment veio cada base, e se ficou parcial.
- Cartões: regras só em Teste, mesmo código com conteúdo diferente, só na
  Produção, referências quebradas (por base), regras "em teste" vigentes na
  Produção, CBS/IBS na Produção.
- **O que falta subir para a Produção** (F2B): situação, filial, regra,
  tributo, descrição, início, campos diferentes e "também falta na Produção".
- **Reforma — CBS/IBS por filial**: tributo × filial, `P n · T n`, verde
  (Produção calcula), amarelo (só Teste), vermelho (nenhuma).
- **Saúde das regras**: por base — vigência, status (decodificado pelo
  `X3_CBOX`), referências quebradas, status de teste, cadastros sem uso.
- **Quantidades por tabela**, por grupo do Configurador, com Δ = Teste −
  Produção, compartilhamento (`X2_MODOEMP+MODOUN+MODO`) e o detalhe por filial.
- **Comparação registro a registro**: uma caixa por tabela com os contadores,
  filtro (só diferenças, só em Teste, só na Produção, diferentes, iguais,
  todos), busca e, nas diferentes, `campo: Produção → Teste`.

## Rotas

| rota | quem | o que faz |
|---|---|---|
| `GET /api/tributos/<customer>` | quem tem a aba | comparação das últimas coletas concluídas (Supabase) |
| `POST /api/tributos/<customer>/coletar?ambiente=` `{coleta_id?}` | interno | uma fase da coleta |
| `GET /api/tributos/<customer>/scripts?ambiente=` | interno | SQL da fase 0, para conferir no console TCloud |

## Testes

- `python3 docs/testes/tributos-back.py` — 107: SQL (só SELECT, sem `;`,
  sufixo, deletados fora), memo em variantes, chave/SIX/ID, comparação por
  chave e por conteúdo, par de mesmo conteúdo, referências (inclusive outra
  filial), vigência, status, CBS/IBS por filial, migração com dependências,
  coleta faseada com REST fingida. `FIXTURE=1` regrava o retrato do front.
- `python3 docs/testes/tributos-rotas.py` — 21: Flask de verdade com banco e
  REST fingidos; fases, histórico, guardas, tabela ausente no Supabase.
- `node docs/testes/tributos-front.js` — 31: aba, cartões, migração, matriz,
  saúde, quantidades, comparação com filtro, coleta faseada nas duas bases,
  cliente sem o botão de coleta, zero erro de JS.

## Para ligar

1. Rodar `docs/sql/2026-10-30-tributos.sql` no Supabase (tabela nova; pode ser
   antes ou depois do deploy — sem ela a aba avisa com 503).
2. Merge; a Vercel publica.
3. Aba **Tributos** → **⚡ Coletar Produção + Teste**.
4. Para mostrar ao cliente: **Acessos** → marcar a aba *Configurador de Tributos*.

## Fora deste patch

- **Cobertura pelo movimento** — CFOP/produto/UF/participante que aparecem em
  notas reais (SD1/SD2/SFT) sem nenhuma regra que os enquadre. É o "faltante"
  mais forte, mas lê movimento: entra como fase opcional, com corte por data.
- Checagem do **tipo** do perfil (`F20_TIPO`) contra o campo da regra que o usa.
- Coleta automática pelo pg_cron.
