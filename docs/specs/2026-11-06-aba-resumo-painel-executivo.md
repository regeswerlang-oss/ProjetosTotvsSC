# Aba Resumo — painel executivo do projeto (2026-11-06)

## O que mudou

A aba **Resumo** do detalhe do projeto deixou de ser "4 cards + lista de horas"
e virou um painel executivo, montado em `renderResumoProjeto()` a partir do que
o app já carrega — nada novo no backend.

| Bloco | Fonte | Conteúdo |
|-------|-------|----------|
| Hero (4 cards com anel) | `/mapa` | Horas previstas (anel = % de saldo; saldo em h e o item "Saldo Projeto" do PCI), Horas realizadas (anel = % do previsto; projeção do PCI), Medição (realizada/prevista, % medido), Período atual (% do período). |
| Execução (8 mini-KPIs) | `/cronograma` + `/mapa` | Atividades concluídas/total, Em implantação (+ abertas), Bloqueadas, Atrasadas (fim previsto < hoje e não concluída), Horas agendadas (`aRealizar`), Saldo livre (previsto − realizado − agendado), Etapas estouradas (nível 1 com realizado > previsto, com pílulas das 6 piores), Prazo decorrido (vigência `IB7_DTVALI → IBL_DTFIM`, dias restantes/vencidos e **ritmo** = % horas ÷ % prazo). Sem vigência, o prazo mostra "—". |
| Avanço por fase | `/cronograma` (nível 0) | barra realizado ÷ previsto por fase; cor azul / amarelo ≥ 90 % / vermelho > 100 %. |
| Apontamentos por tipo | `/mapa.horaItems` | barras hh:mm + participação sobre as horas apontadas (Saldo e Projeção ficam fora da participação). |
| Atividades atrasadas | `/cronograma` (nível 3) | 6 mais atrasadas, com etapa, data fim e dias de atraso. |
| Próximas atividades | `/cronograma` (nível 3) | 6 próximas por `data_inicio ≥ hoje`, com "em N d". |

## Mecânica

- `preencheMapa()` guarda `state.mapa` e chama `renderResumoProjeto()`; a parte
  que depende do cronograma mostra "Carregando cronograma…" até `abrirDetalhe`
  receber o `/cronograma`, quando a função roda de novo.
- `abrirDetalhe()` zera `state.cronograma` ao abrir outro projeto, para o Resumo
  não mostrar o cronograma do projeto anterior.
- Helpers novos: `hhmmParaHoras`, `isoHoje`, `diasEntre`, `rsAnel` (SVG),
  `rsHero`, `rsKpi`, `rsBarra`, `corPorConsumo`. CSS com prefixo `.rs-*`.
- Exportar HTML / Rascunho no Gmail continuam pelo snapshot de `#tab-resumo`
  (`RELATORIOS.resumo`); os anéis SVG saem no HTML e são omitidos no e-mail, mas
  os percentuais também estão em texto nos subtítulos.
