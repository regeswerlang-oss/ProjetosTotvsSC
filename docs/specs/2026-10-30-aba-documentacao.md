# Aba Documentação — casa única da documentação por processo (30/10/2026)

*Piloto: DIGITRO (`000348D0`). SQL: `docs/sql/2026-10-30-documentacao.sql`.*

**Pedido:** uma aba no Dashboard de Projetos para publicar a documentação por
processo/fluxo/módulo, para a consultoria e para o cliente, com uma **matriz** do
que sempre gerar e de quem vê. Clicar num HTML abre a página; num JPEG, a imagem.

**Decisão (brainstorm 30/10):** UNIFICAR. A aba substitui a Página Indexada
(`DigitroConsultoriaindex`, que só tinha exemplos) e absorve o Portal de Processos
do Cliente (`digitroindex`, 1 processo — Comissão — vira o tipo *Explicação ao
cliente*). Navegação pelos **Processos Principais** do Radar
(`cockpit.radar_processos`), não pelos 24 módulos / 200 processos do escopo.

## Modelo

| Tabela | Papel |
|---|---|
| `doc_tipos` | **A matriz** (global): tipo, obrigatório em todo processo, `nivel_max` (até onde pode chegar), formatos |
| `doc_series` | O documento lógico (ex.: *Fluxo do Painel de Projetos*), por cliente |
| `doc_serie_processos` | Liga a série a N processos **e ligações** (um fluxo de integração aparece em 4 processos, cadastrado uma vez) |
| `doc_versoes` | Cada arquivo: formato, versão, data, **vigente**, visibilidade. Uma vigente por (série, formato) — o HTML novo não tira a imagem do ar |
| `doc_arquivos` | Conteúdo em `bytea`, deduplicado por sha256 (mesmo HTML em duas pastas = um arquivo) |
| `doc_dispensas` | "Este processo não precisa deste tipo" + motivo (ex.: sem customização → sem MIT044) |

### Matriz v1

| Tipo | Obrigatório | Quem vê |
|---|---|---|
| Fluxo sistêmico | ✅ | consultoria + cliente (após liberar) |
| Explicação ao cliente | — | consultoria + cliente |
| Processo consolidado | ✅ | consultoria + cliente |
| Especificação da customização (MIT044) | ✅ | consultoria + cliente |
| Termo de validação (MIT010) | ✅ | consultoria + cliente |
| Estimativa / necessidade | — | consultoria + cliente |
| Apresentação / status report | — | consultoria + cliente |
| Material de apoio (vídeo, link, pasta) | — | consultoria + cliente |
| Desenho / especificação técnica | — | **só consultoria (trava)** |
| Parecer / diagnóstico interno | — | **só consultoria (trava)** |
| Registro de reunião interno | — | **só consultoria (trava)** |

## Três travas (todas no servidor)

1. **Tipo** — `nivel_max='consultoria'` nunca vai ao cliente, nem por admin.
2. **Quem libera** — só admin põe uma versão em `cliente` (e recolhe).
3. **Recorte** — `/api/docs` devolve ao cliente só versão vigente + liberada, sem
   `publicado_por`, `origem`, `nota`, histórico, cobertura ou dispensas. A rota do
   arquivo confere tudo de novo (link copiado não fura).

Tudo entra como **Consultoria**; rascunho é visível só para quem publicou.

## Visualizador

- **HTML** → iframe com `sandbox` **sem** `allow-same-origin` + `Content-Security-Policy: sandbox`
  na resposta: a página roda em origem opaca e não lê a sessão do dashboard (vale
  também para "Nova aba"). SVG idem.
- **JPEG/PNG/SVG** → imagem ajustada à tela, clique alterna para tamanho real.
- **PDF** → leitor do navegador. **MD/TXT** → leitura renderizada (texto escapado).
- **Link** → abre em nova aba.

## Limites

Teto de **3,5 MB por arquivo** (a função da Vercel não devolve corpo acima de
4,5 MB). PDF maior: comprimir as imagens a 150 dpi (a MIT044 do Painel foi de
7,9 MB para 2,3 MB, legível) ou publicar como link. Pacote `.zip` até 4,4 MB.

## Rotas

| Rota | Portão |
|---|---|
| `GET /api/docs/<c>` | `require_auth` + `deny_aba(c, "documentos")` (recorte do cliente) |
| `GET /api/docs/<c>/arquivo/<vid>[?baixar=1]` | idem + reconferência da versão |
| `POST /api/docs/<c>/publicar` (multipart: `arquivo` ou `url`) | `require_interno` + `deny_customer` |
| `POST /api/docs/<c>/serie/<sid>` | idem (título, descrição, tipo, processos, arquivar) |
| `POST /api/docs/<c>/versao/<vid>` | idem (visibilidade, tornar vigente, excluir = admin) |
| `POST /api/docs/<c>/dispensa` | idem |
| `POST /api/docs/<c>/processo` | idem (cliente sem taxonomia: cria o Processo Principal — aparece no Radar) |
| `POST /api/docs/<c>/pacote` (`.zip` com `manifest.json`) | idem — idempotente |

### `manifest.json` do pacote

```json
{ "series": [ {
  "serie": "fluxo-painel-gestao-projetos", "tipo": "fluxo",
  "titulo": "Fluxo sistêmico do Painel de Gestão de Projetos",
  "descricao": "…", "processos": ["PNL", "iPaaS → Painel de Projetos"],
  "versoes": [ { "arquivo": "fluxo.html", "versao": "v1", "data": "2026-10-30",
                 "vigente": true, "nome": "nome original.html", "origem": "pasta/arquivo", "nota": "…" } ] } ] }
```

Processo por id, prefixo ou nome. Versões em ordem (antiga → nova).

## Carga inicial Dígitro (12 documentos, 17 versões)

Das pastas *Fluxo Sistemico Digitro*, *Painel de Contratos* e *FLuxo Sistemico
Integracao CRM Protheus*. Achados ao montar:

- *Fluxo Painel de Projetos Dígitro.html* e *Digitro_Fluxo_Sistemico_Painel_Gestao_Projetos.html* são **o mesmo arquivo** → 1 documento.
- O fluxo de **Integrações** existe em duas versões (27/10 e 30/10, esta com a situação dos testes) → v2 vigente, v1 no histórico.
- O fluxo **Comercial** tem 2 HTMLs (27/10 e 30/10) → v2 vigente; a imagem escura virou documento próprio.
- O *Processo* (.md) foi convertido para HTML; traz horas contratadas e nomes da equipe — **revisar antes de liberar**.
- *Claude.pdf* ficou de fora (não é entregável).

Cobertura resultante: **Painel de Projetos 4/4**; CRM, iPaaS, Contratos, Fiscal e Cadastros só com o fluxo.

## Testes

- `python3 docs/testes/doc-back.py` — formatos, travas, cobertura, recorte do cliente, manifesto, portões das 8 rotas.
- `node docs/testes/doc-front.mjs` — visão interna (processo, matriz, dispensa, liberação, visualizador) e do cliente.
- `DATABASE_URL=<postgres de TESTE> python3 docs/testes/doc-integracao.py` — rotas reais contra Postgres local (pacote, publicar, versões, travas, recorte).
