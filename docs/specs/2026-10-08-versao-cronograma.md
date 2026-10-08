# Cronograma lido na versão vigente (08/10/2026)

## Sintoma
Aba **Por Etapa** (e Por Módulo / Cronograma / Consumo) divergia do portal
TOTVS. Ex.: Digitro 000348D025 — Protótipo Integrado 459h no dashboard × 378h
no portal; total 5.215h × 5.210,5h; executadas 2.599,9h × 3.213,6h.

## Causa
- `cockpit.projetos.versao_projeto` é nulo nos 1.160 projetos (a lista PCI não
  traz o campo), então o front montava `/api/projeto/.../01/...`.
- `/PCITConectaProjetos/mapa` ignora a versão pedida e devolve a **vigente**
  (`IB7_VERSAO`) — por isso o cabeçalho mostrava "versão 11".
- `/PCITConectaProjetos/cronograma` **respeita** `VERSAO`: devolvia a v01
  (plano original), com outra distribuição de horas e apontamentos.

## Correção
`abrirDetalhe()` em `web/index.html`: o cronograma é buscado com a versão
devolvida pelo `/mapa` (`IB7_VERSAO`); só cai no `ver`/'01' se o mapa não
trouxer versão.

## Conferência
Com v11 a soma das atividades nível 3 por sub-etapa bate com o portal
(Levantamento 294 / 339,27; Prot. Integrado 378 / 0; Específicos 2.346,5 /
1.282,42; Gestão 1.000 / 1.063,45).

# Aba Consumo — coluna "Sem agenda" (08/10/2026)

## Sintoma
A linha não fechava: Protótipo Integrado 378 estimadas, 0 realizadas, 280,4 a
realizar — faltavam 97,6h que não apareciam em lugar nenhum.

## Causa
"A realizar" (`aRealizar()`) soma só agendas não apontadas (status ≠ ZA/ZV).
O estimado que ainda **não tem agenda** não tinha coluna. É o mesmo que o portal
mostra como Cobertura (280,4 / 378 = 74%).

## Correção
Coluna **Sem agenda** = Estimadas − Realizadas − A realizar, na linha e no
total. Valor negativo vira "+X estouro" em vermelho (realizado + agendado passou
do estimado: Levantamento +45,3; Capacitação +88).
Fechamento Digitro v11: 4.208,5 = 2.150,2 + 754,4 + 1.303,9.
