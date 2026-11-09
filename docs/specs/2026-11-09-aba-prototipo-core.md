# Aba Protótipo Core — trilha ao vivo da proposta (09/11/2026)

*Piloto: DÍGITRO (`000348D0`), protótipo integrado de 09 e 10/11/2026.*

## A pergunta que a tela responde

**"A proposta que a Aline acabou de digitar no CRM chegou? Gravou na ZA3?
Virou projeto? Virou contrato? E os valores batem com o que a regra diz?"**

Durante o protótipo integrado a sala inteira quer essa resposta em segundos,
para cada proposta digitada — e quer registrar a divergência antes que ela se
perca. A aba Integrações (grupo CRM × iPaaS) responde em agregados ("quantas
pararam"). Esta aba responde **por mensagem**, com os campos reais.

```
Proposta no CRM → iPaaS/Etapa 1 (ZA3) → Etapa 2 (Sincronizar) → Painel de Projetos (ZA0/ZA1/SB1 PRJ/CTD/ZA4) → Contratos (CN9/CNA/CNB) → Retorno (STIPA)
```

## Tela

- **Esquerda — a fila da ZA3.** Uma linha por mensagem (`messageId`), com os
  três semáforos (STG1 · STG2 · STIPA), nº da proposta e cliente (lidos do
  começo do JSON), data/hora, contrato, nº de projetos encontrados. KPIs:
  recebidas, com contrato, na fila, em erro. Busca e "só problemas".
- **Direita — a trilha** da mensagem escolhida:
  - **Seis cards de estágio** em fluxo com setas coloridas. Cada card tem
    nível (OK / Atenção / Divergente / Info / Sem dado), KPIs e resumo.
    **Toque = expande** o detalhe abaixo: campos reais da tabela com o título
    do dicionário, ordens de venda com itens, JSON completo, ZA0 por projeto
    (itens, PRJ no SB1, CTD, NS), CN9 com CNA e CNB.
  - **Conceitos** do catálogo C01–C25: cards com código, esperado × observado
    e nível; toque expande regra, nota e o botão **⚑ Registrar ocorrência no
    Radar** (grava em `radar_itens` com a evidência pronta).
- Barra: base (Produção/Teste), **⚡ Atualizar agora** e **atualizar a cada 30 s**.
- Exporta HTML / rascunho no Gmail como as outras abas (`RELATORIOS.core`).

## Decisões que custam caro se desfeitas

1. **Os campos vêm do dicionário (SX3), não de uma lista fixa.** A proposta
   tem "variações e campos possíveis"; o que existe na ZA3/ZA0/CN9 da base é
   o que a tela mostra. Campos virtuais (`X3_CONTEXT = 'V'`) ficam fora.
   Se o SX3 não puder ser lido, vale `CORE_CAMPOS_MINIMOS`. Cache de 10 min.
2. **Memo em HEXADECIMAL, em pedaços.** O CSV da REST separa por `;` e o JSON
   é cheio de `;`, aspas e quebras de linha. Em hex só há `[0-9A-F]`:
   Oracle `RAWTOHEX(DBMS_LOB.SUBSTR(col, 1900, off))` (BLOB) ou
   `RAWTOHEX(UTL_RAW.CAST_TO_RAW(DBMS_LOB.SUBSTR(...)))` (CLOB); SQL Server
   `CONVERT(VARCHAR(MAX), SUBSTRING(CONVERT(VARBINARY(MAX), col), off, 1900), 2)`.
   1900 bytes → 3800 caracteres, abaixo dos 4000 do VARCHAR2. A lista lê 1
   pedaço (basta o nº da proposta); a trilha lê até 24 (≈ 45 KB por memo).
   O Python junta, decodifica UTF-8 → cp1252 e faz `json.loads` tolerante.
3. **Chave da cadeia = contrato da ZA3 e código do projeto.** `ZA3_CONTRA` →
   `ZA0_CONTRA` / `CN9_NUMERO`; `ZA0_CODIGO` = `ZA1_CODIGO` = `CTD_ITEM` =
   `CNB_ITEMCTA` (comparação sem espaço, porque o código é "NNNNNN AAAA").
   Nomes diferentes no dicionário são resolvidos por `_core_chave()`.
4. **Só a revisão vigente** do contrato entra em CNA/CNB.
5. **Leitura é operação (licença no REST): `require_interno`.** A aba é
   liberável ao cliente para ver o que for exportado/publicado; a leitura na
   base continua só com a equipe TOTVS, como toda coleta.
6. **Os conceitos são avaliados no servidor** (`_core_conceitos`), a tela só
   desenha. Cada um devolve `nivel`, `esperado`, `observado`, `regra`, `dica`
   e `estagio`. Cobertos: C01 memorial, C02 IT, C03 tipo de venda, C04
   modalidade, C05 UN, C06 plataforma, C07 físico/virtual (PRJ, NS), C10
   garantia/monitoramento, C12 condição → vigência, C13 tabela, C14 três
   clientes, C16 vendedor, C17 participação, C18 valor zero, C19 venda ×
   locação (PRJ na CNB), C23 nº proposta (XOPORT 6 × PROPOS 50), cardinalidade
   (1 projeto/OV, 1 contrato, 1 planilha/projeto), CTD, valor do PRJ, valor do
   contrato, P11 retorno.
7. **A leitura do JSON é por nome de chave, em qualquer profundidade e sem
   acento/caixa** (`_core_busca`): o consolidado da ZA3 pode mudar de forma
   entre versões do iPaaS sem a tela quebrar. Se o consolidado não trouxer as
   ordens, os três blocos (OPORT, ITOPOR, ORDVEN) são juntados.

## Rotas

| Rota | O que faz |
|---|---|
| `GET /api/core/<customer>/propostas?ambiente=&limite=` | SX3 (cache) + ZA3 (últimas N, memo 1 pedaço) + ZA0/CN9 dos contratos |
| `GET /api/core/<customer>/trilha?ambiente=&msgid=` (ou `idcrm=` / `recno=`) | ZA3 completa + irmãs, ZA0/ZA1/SB1/CTD/ZA4, CN9/CNA/CNB, estágios e conceitos |

Ocorrência → `POST /api/radar/<customer>/item` (rota existente), processo
sugerido pelo nome (integra → painel/projeto → crm).

## Testes

- `python3 docs/testes/core-back.py` — 84 asserções: SQL por dialeto (hex,
  TOP/ROWNUM, sem `;`, palavras proibidas), hex → texto, JSON tolerante,
  leitura da proposta, conceitos e estágios em 5 cenários.
- `node docs/testes/core-front.mjs` — stub + Chromium: fila, trilha, os seis
  detalhes, filtro e expansão dos conceitos, modal de ocorrência gravando no
  stub do Radar, troca de base, busca, erro na Etapa 1, exportação.

## Fora deste patch

- Comparar com o lado CRM/iPaaS (monitor do iPaaS, P3).
- Histórico das leituras (hoje é retrato ao vivo; `protheus_coletas` só loga).
- Disparar o Sincronizar a partir da tela (a REST é só leitura, de propósito).
