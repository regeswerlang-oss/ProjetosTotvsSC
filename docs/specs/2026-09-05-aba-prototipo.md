# Aba Protótipo — roteiro MIT045, ciclos e aproveitamento (05/09/2026)

## A pergunta que esta tela responde

Não é **"qual o status do item"**, é **"o aproveitamento ANDOU do ciclo anterior
para este?"**. Todo o desenho sai daí:

- o resultado **não mora no item**, mora no par **(item × ciclo)** — o mesmo
  roteiro é executado de novo a cada ciclo e guardar o status no item apagaria a
  história;
- o **ciclo é a primeira escolha da barra**, não um filtro escondido;
- o KPI de aproveitamento vem com a **variação contra o ciclo anterior**, na
  ordem metodológica interno → isolado → integrado. Número solto de um ciclo não
  diz se o protótipo andou.

## Dois indicadores — confundi-los esconde problema

| indicador | fórmula | responde |
|---|---|---|
| **Aproveitamento** | % de `exito` sobre os **aplicáveis** | a execução andou? |
| **Maturação** | média das notas 0–10 | o usuário se sente seguro? |

`nao_aplicavel` **sai do denominador**: item que o cliente não usa reprovaria o
módulo inteiro sem nada de errado ter havido. Módulo 100% executado com maturação
4 é treinamento que não pegou — por isso os dois números convivem na tela.

## Modelo (schema `cockpit`)

| tabela | o que guarda |
|---|---|
| `proto_roteiros` | o MIT045: cliente, escopo (`modulo`/`processo`), título, link do Drive, URL do CSV publicado, data do protótipo |
| `proto_itens` | os itens como vieram da planilha (ordem, módulo, processo, subprocesso, descrição, consultor, usuário, data planejada) |
| `proto_ciclos` | `interno`/`isolado`/`integrado` × número, com `visivel_cliente` e `aberto` |
| `proto_resultados` | **(ciclo × item)**: status, nota 0–10, ocorrência, data de conclusão, quem respondeu |
| `proto_usuario_modulos` | quem edita qual módulo, **por cliente** (`*` = todos) |

`proto_usuario_modulos` é por **cliente**, não por roteiro: os módulos (SIGACTR,
SIGAFIN) são estáveis e o CP não deveria reliberar as mesmas pessoas a cada
roteiro novo.

## O ciclo INTERNO nasce fechado para o cliente

`visivel_cliente` default `false` para `interno`, `true` para os outros. O ciclo
interno é a consultoria ensaiando entre si — se vazar para a área de clientes, o
cliente lê ensaio como resultado. O `GET` filtra os ciclos antes de responder:
o cliente **nem recebe** o ciclo interno, não é só a tela que esconde.

## O LINK DO DRIVE NÃO É A FONTE DE DADOS

O backend na Vercel **não tem credencial Google**. Colar o link guarda a
referência rastreável (`fonte_url`, clicável), mas não traz item nenhum. Os itens
entram por um destes três, todos no mesmo parser:

1. **arquivo** `.xlsx`/`.csv` no corpo do POST (o caminho normal);
2. **`csv_url`** — a URL de *Arquivo > Compartilhar > Publicar na web > CSV*,
   gravada em `fonte_csv_url` para reimportar sem subir arquivo de novo;
3. **Cowork** — colar o link na conversa e importar por aqui (origem `cowork`).

`openpyxl` entrou no `requirements.txt` por causa do `.xlsx`. Sem ele a rota
responde uma mensagem que diz o que fazer ("exporte como CSV"), não um
`ImportError` na cara do usuário.

## O parser do MIT045

**ARMADILHA:** a planilha tem uma **coluna vazia à esquerda** e **três linhas de
cabeçalho** antes da tabela. O parser acha a linha de cabeçalho pelo **conteúdo**
(tem `DESCRIÇÃO` e `MÓDULO`/`PROCESSO`), não pela posição — é isso que faz ele
aguentar a planilha ganhar uma linha de logo amanhã. Os metadados (`Projeto`,
`Data Protótipo`) são lidos acima do cabeçalho, no formato rótulo | valor.

**ARMADILHA que custou um teste:** a célula de data já chega ao `_proto_data`
como **texto** (`"2026-05-01 00:00:00"`), porque quem lê a planilha normaliza
tudo para string antes. Sem cortar a hora, `_data_iso` não casa e a Data do
Protótipo entra **nula** — o roteiro importa 40 itens certinhos, sem data, e
ninguém percebe. Hoje `_proto_data` aceita `1/5/2026`, `2026-05-01`,
`2026-05-01 00:00:00`, ISO com `T`, `20260501` e o `datetime` do openpyxl.

Linha sem descrição (rodapé, nota) **não é item**. Ordem repetida é
desempatada antes do insert, senão o `unique (roteiro_id, ordem)` estoura no meio.

`semear=1` cria o **Interno 1** já com o Status que veio preenchido na planilha —
senão o CP redigita 40 linhas. O de-para (`PROTO_STATUS_DE`) converte
"Executado com êxito" → `exito`, "Erro / Necessário ajuste" → `erro` etc.

## Quem edita o quê — três portas, todas no servidor

`_proto_pode_editar()` exige as três: o **ciclo aceita resposta** (`aberto`), o
**ciclo é visível** para quem responde, e o **módulo está liberado** para ele.
A tela do cliente só desenha campo nos módulos dele, mas é o servidor que barra o
item de outro módulo mandado na mão. Esconder não é proteger.

## Portões

```
/api/proto/<customer>                        GET     require_auth + deny_aba(prototipo)
/api/proto/<customer>/roteiro/<rid>          GET     require_auth + deny_aba
/api/proto/<customer>/indicadores/<rid>      GET     require_auth + deny_aba
/api/proto/<customer>/ciclo/<cid>/resultado  POST    require_auth + deny_aba + _proto_pode_editar
/api/proto/<customer>/roteiro                POST    require_interno   (importar)
/api/proto/<customer>/roteiro/<rid>          DELETE  require_interno   (inativa, não apaga)
/api/proto/<customer>/roteiro/<rid>/ciclo    POST    require_interno
/api/proto/<customer>/ciclo/<cid>            PATCH   require_interno   (abrir/fechar/publicar)
/api/proto/<customer>/ciclo/<cid>            DELETE  require_interno   (exige confirmar=1 se já respondido)
/api/proto/<customer>/modulos                GET/POST/DELETE require_interno
```

Apagar roteiro **inativa**, não apaga: os resultados dos ciclos são histórico do
projeto. Apagar ciclo com item respondido exige `confirmar=1`.

A aba `prototipo` entrou no catálogo `ABAS` como liberável ao cliente — mas
`ABAS_PADRAO_CLIENTE` continua `['cadastros']`, então **o CP tem que liberar a
aba** em 👥 Acessos antes de o cliente ver qualquer coisa.

## Conferido

`/tmp/v/testparse.py` — o MIT045 reconstruído célula a célula a partir do texto
do arquivo real da Dígitro, nas duas variantes de data (texto e `datetime`):
40 itens, 6 módulos, rodapé ignorado, ordens únicas, e o **CSV exportado dá
exatamente o mesmo resultado do XLSX**. Mais o agregador: `aplicáveis = total −
não aplicáveis` e `aproveitamento = êxito / aplicáveis` em todos os módulos.

`/tmp/v/testproto.mjs` — Playwright nos **três cenários que importam**:

| cenário | ciclos | edita |
|---|---|---|
| interno | 3 (interno com selo "só interno") | todos |
| cliente com SIGACTR liberado | 2 (o interno **nem chega**) | só os 2 itens de SIGACTR |
| cliente sem módulo | 2 | nenhum, com a faixa explicando |

**ARMADILHA de tela:** `.bar-track` só funciona em `<div>`. Num `<span>`
(display inline) o `height` é ignorado e a barra some — o resto do arquivo já
usava `<div>` por isso. E cor de barra por classe Tailwind gerada em runtime
pode não existir na folha: aqui vai **cor inline**, como o `.fill-exec` faz.

## Pendências

1. **Importar o MIT045 real da Dígitro pela tela** — é o primeiro teste de
   verdade do parser contra o arquivo original (o teste roda contra uma
   reconstrução fiel, não contra os bytes).
2. Liberar a aba `prototipo` para os usuários-chave em 👥 Acessos, e os módulos
   em 👥 Módulos por usuário.
3. Re-sync automático pela `fonte_csv_url` (a coluna existe, a rota de resync
   ainda não).
4. Exportar o ciclo preenchido de volta para o formato MIT045.
