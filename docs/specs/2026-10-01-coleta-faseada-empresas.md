# Coleta faseada do script de Empresas

*01/10/2026 — a base recusou o script com 257 KB.*

## O problema

O gerador monta **um bloco por empresa × tabela**. Com 131 tabelas no escopo e
4 empresas, o script de Empresas chegou a **257 KB** e a REST recusou:

```
A base recusou a consulta: Consulta com 257 KB - o teto e 146 KB. Script desse
tamanho prende a licenca do REST ate o banco responder.
```

O teto (`LIM_SQL` no `TSCMONITREST`) não é capricho e **não deve ser subido**: um
script desse tamanho segura a licença do REST da base inteira até o banco
responder. Quem está errado é a chamada, que manda tudo de uma vez.

## A decisão: uma empresa por fase, laço no navegador

O corte já existia no gerador — `scriptEmpresas({ empresas: ['01'] })` filtra
pela SM0 e sai com os blocos de uma empresa só. Quatro empresas viram **quatro
scripts de ~60 KB**, folgados abaixo do teto.

O laço roda **no navegador**, não no backend. Cada fase é uma invocação própria
da Vercel, com seus próprios 60s: quatro leituras numa invocação só disputariam
o mesmo orçamento e a última morreria pela metade. De quebra, a tela mostra o
progresso e **retoma**: falhou a fase 3, o botão vira *"Tentar de novo (1)"* e
repete só ela — as que deram certo ficam guardadas no navegador.

```
painel                          backend                    base
──────                          ───────                    ────
gera N scripts (da SM0)
  POST /…/producao/fase  ──►  valida leitura  ──►  /tscmonit/query
  (um por empresa)        ◄──    CSV cru      ◄──    CSV
  … repete por empresa …
junta os CSVs
  POST /…/upload (text/csv) ──► _csv_empresas ──► monitemp_medicoes/_itens
```

A gravação é a **mesma** do "Subir medição": o CSV juntado entra pelo importador
de sempre. Nenhuma regra de painel ou de medição mudou.

## Detalhes que custaram decisão

**O dialeto vem do `⚙ Ambiente`, não de um select.** Era o campo que faltava no
payload do `/api/monitemp`. Sem banco informado a tela **para** em vez de gerar
Oracle por omissão: numa base SQL Server o script roda, volta errado, e ninguém
vê. Quem já cadastrou a REST já informou o banco — perguntar de novo é mais um
campo para errar.

**As fases saem da SM0, não do script salvo.** Está escrito na tela: edição
manual do script não entra na coleta faseada.

**Juntar é cabeçalho da primeira fase + corpo de todas.** Cabeçalho repetido no
meio do CSV vira linha de dado e estraga a medição inteira.

**A rota `/fase` repete a trava de leitura do `SqlSeguro`.** O SQL vem do
navegador; a base já recusaria escrita, mas uma segunda porta trancada custa
quinze linhas. Também barra fase acima de 140 KB — assim o erro aparece no
painel, com o número, em vez de ir prender a licença do REST para descobrir lá.

## Como foi testado

Backend: a trava aceita `SELECT`/`WITH`, cabeçalho de comentário, `DELETE` dentro
de literal e `;` no fim; barra DML, segundo comando, `INTO` e `DBMS_`. Fase de
156 KB recusada com o tamanho na mensagem. SQL de escrita **não chega na base**.

Tela, no Chromium com `/api/*` interceptado: sem banco no cadastro não abre; com
banco, três fases de ~59 KB (contra 250 KB inteiros); a fase 02 falha de
propósito, a lista marca `✕` com a mensagem da base, a barra fica em 67 % e o
botão vira *"Tentar de novo (1)"*; a retomada chama **só a 02** (sequência
`01,02,03,02`); o CSV enviado ao `/upload` tem **um** cabeçalho e as seis linhas.
