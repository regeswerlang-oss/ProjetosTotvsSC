# Protótipo v2 — papéis, atribuição e o OK do consultor (07/09/2026)

## Dois eixos de resposta — a decisão que carrega tudo

Antes o item tinha **um** status. Agora tem dois, e eles são de gente diferente:

| eixo | quem preenche | valores |
|---|---|---|
| `status` | **o cliente** | Não iniciado · Executado · Com dúvida · Com erro · Não aplicável (+ nota 0–10 + ocorrência) |
| `validacao` | **o consultor TOTVS** | Aguardando · OK · Reprovado (+ parecer) |

**"Executei" não é "está certo".** O APROVEITAMENTO conta somente `validacao='ok'`.
Sem essa separação o cliente marca 40 itens como executados e o protótipo fecha
em 100% sem ninguém da TOTVS ter olhado.

Consequência que vale ouro: **responder de novo devolve a validação para
`pendente`** e limpa `validado_por`. Mudou a resposta, o OK anterior era sobre
outra coisa.

### Três indicadores, três perguntas

- **Execução** = % `executado` sobre os aplicáveis → *o cliente andou?*
- **Aproveitamento** = % `ok` sobre os aplicáveis → *o trabalho presta?*
- **Aguardando validação** = feito (`executado`/`duvida`) e ainda `pendente`

A distância entre execução e aproveitamento **é a fila de validação** — é ela que
denuncia consultor parado, não a contagem de executados. Na tela isso vira duas
barras por ciclo: a clara é o que o cliente executou, a escura é o que a TOTVS
validou, e o vão entre elas se lê de longe.

`erro` **não** entra em "aguardando validação": erro é problema a resolver, não
fila de conferência. Ele aparece no KPI de Maturação.

## Papéis — o segundo eixo de permissão

`usuarios_login.perfil` diz o que a pessoa é **no sistema**.
`usuario_clientes.papel` (novo) diz o que ela é **naquele projeto**:

| papel | pode |
|---|---|
| `cp_totvs` | coordena: importa/cria roteiro, cria ciclo, monta a equipe, atribui, valida tudo |
| `consultor` | valida os itens dos **módulos dele** |
| `cp_cliente` | distribui responsáveis e responde tudo do cliente — **não valida** |
| `usuario_chave` | responde o que lhe foi atribuído |

Confundir os dois eixos abre acesso: a mesma consultora é `cp_totvs` na Dígitro e
`consultor` no Olim. Por isso o papel é **por cliente**, nunca global.

**`require_cp(customer)`** é o portão da coordenação. Admin sempre passa — senão
marcar o primeiro CP seria impossível (bootstrap). Papel da TOTVS (`cp_totvs`,
`consultor`) **não se concede a login de cliente**: a rota recusa.

**O CP do Cliente NÃO libera acesso.** Ele distribui trabalho entre quem a TOTVS
já liberou. Quem entra no sistema continua sendo decisão da tela **Acessos** —
foi decisão explícita, e é o que impede o cliente de abrir porta para fora sem
você saber. Atribuir a um e-mail sem acesso ao cliente é recusado com a
mensagem certa: criaria **responsável fantasma**, linha com dono e ninguém
consegue responder.

Na tela, os botões de coordenação usam `.pro-cp` / `.pro-cps`, **não**
`data-interno`: consultor comum **é** interno e mesmo assim não coordena.

## Quem executa o quê — precedência da atribuição

`proto_atribuicoes (roteiro_id, ciclo_id, escopo, alvo, email)`.
`ciclo_id` NULL = **padrão do roteiro**; preenchido = **exceção daquele ciclo**.

Precedência, do mais específico para o mais geral:

1. exceção do **ciclo**: item > processo > módulo
2. padrão do **roteiro**: item > processo > módulo
3. a coluna `Usuário` que veio da planilha

Isso é o que permite **definir uma vez e sobrescrever só onde precisa** — sem
redistribuir 40 linhas a cada ciclo. Inverter a ordem faria a atribuição do
módulo apagar a da linha.

O `unique nulls not distinct (roteiro_id, ciclo_id, escopo, alvo)` é obrigatório:
sem ele duas linhas com `ciclo_id NULL` e mesmo alvo não colidiriam e o padrão do
roteiro viraria duplicata silenciosa. (PG 15+; o banco está em 17.)

**ARMADILHA de tela:** "não tem módulo liberado" **não** é "não tem o que fazer".
Quem recebeu uma linha atribuída edita sem módulo nenhum — é exatamente para isso
que a atribuição por linha existe. A faixa de leitura só aparece quando
`!itens.some(proPodeResponder)`, nunca olhando só a lista de módulos.

## Módulos: quem EXECUTA e quem VALIDA

`proto_usuario_modulos` ganhou `papel` (`executa` | `valida`) e `processo`
(NULL = o módulo inteiro). Misturar os dois na mesma lista confundiria o
usuário-chave que preenche com o consultor que dá o OK — e o OK é justamente o
que fecha o item. `modulo = '*'` libera o cliente inteiro.

## Roteiro manual

Três caminhos, todos em `POST /api/proto/<c>/roteiro/manual`:

1. **do zero** — itens colados em bloco, formato `Módulo | Processo | Subprocesso | Descrição`
   (só a descrição é obrigatória);
2. **copiando outro roteiro** (`?copiar_de=<rid>`) — copia a **estrutura**, nunca
   os resultados: resultado é do projeto onde foi executado. `GET /api/proto/modelos`
   lista os candidatos, recortados por `allowed_customers()`;
3. vazio, e depois `POST .../itens` linha a linha.

Apagar item **inativa** (`ativo=false`): o item pode ter resultado de ciclo anterior.

## Exportar de volta no formato MIT045

`GET /api/proto/<c>/roteiro/<rid>/export?ciclo=<cid>` gera o `.xlsx` mantendo a
coluna vazia à esquerda e as linhas de cabeçalho — é assim que o arquivo original
é, e é assim que **o nosso próprio parser reconhece na volta**. Acrescenta três
colunas: Validação, Parecer do consultor e Nota.

## Portões

```
GET  /api/proto/<c>                              auth + deny_aba(prototipo)
GET  /api/proto/<c>/roteiro/<rid>                auth + deny_aba
GET  /api/proto/<c>/indicadores/<rid>            auth + deny_aba
GET  /api/proto/<c>/roteiro/<rid>/export         auth + deny_aba
POST /api/proto/<c>/ciclo/<cid>/resultado        auth + deny_aba + proto_pode_responder
POST /api/proto/<c>/ciclo/<cid>/validar          auth + deny_aba + proto_pode_validar
POST /api/proto/<c>/roteiro | /manual | /itens   require_cp
POST /api/proto/<c>/roteiro/<rid>/ciclo          require_cp
PATCH|DELETE /api/proto/<c>/ciclo/<cid>          require_cp
GET|POST|DELETE /api/proto/<c>/equipe            require_cp
POST|DELETE .../atribuicoes                      auth + deny_aba + (cp_totvs OU cp_cliente)
GET  /api/proto/modelos                          auth + eh_interno
```

## Conferido

`/tmp/v/testregras.py` — precedência da atribuição nos 5 casos (sem regra →
planilha; módulo; processo vence módulo; linha vence processo; **exceção do ciclo
vence a linha do roteiro**) e a aritmética dos indicadores: `aplicáveis = total −
n/a`, `aproveitamento < execução` quando há executado sem OK, `aguardando = 2`
com `erro` fora.

`/tmp/v/testpapeis.mjs` — Playwright nos quatro papéis:

| cenário | ciclos | responde | valida | botões de coordenação |
|---|---|---|---|---|
| CP TOTVS | 2 (vê o interno) | todos | todos | 6 |
| Consultor SIGACTR | 2 | todos (é interno) | só SIGACTR | 0 |
| CP do Cliente | 1 (interno não chega) | todos | nenhum | só Atribuir |
| Usuário-chave com **só a linha 5** | 1 | **só a linha 5** | nenhum | 0 |

A última linha é a prova do conceito: sem módulo liberado nenhum, a atribuição
por linha sozinha já dá acesso de escrita àquele item e a nenhum outro.

## Pendências

1. **Importar o MIT045 real da Dígitro pela tela** — o parser roda contra uma
   reconstrução fiel, não contra os bytes originais.
2. Marcar Viviani e Cassio como `cp_totvs` nos clientes deles (hoje só admin
   coordena, por bootstrap).
3. Liberar a aba `prototipo` em Acessos para os usuários-chave.
4. Re-sync automático pela `fonte_csv_url` (a coluna existe, a rota não).
