# Movimentos — filtro de período e apagar medição

*22/10/2026 — pedido do Reges, a partir da Digitro (base de testes).*

## Por quê

A Digitro passou a medir o fluxo de contratos (script D10) em 22/10. As medições
de 04/09 e 07/09 ficaram na mesma série — a de 07/09 só tinha SD2/SE5 de outra
janela e derrubava a cobertura para 0/41 no meio da evolução. Faltavam duas coisas
na sub-aba **Movimentos**: tirar uma medição que não presta e olhar só um período.

## O que mudou

### Filtro de período (data da coleta)

- Barra da sub-aba Movimentos: `Período [de] a [até]` + `✕ limpar`.
- O recorte vai como `?de=AAAA-MM-DD&ate=AAAA-MM-DD` para
  `GET /api/monitmov/<customer>` e `GET /api/monitmov/<customer>/evolucao`
  (helper `_periodo_req()`; aceita também AAAAMMDD). **O servidor recorta as
  medições** — KPIs, série, "Por análise", "Fora do combinado" e a matriz de
  cenários respeitam o mesmo período sem lógica duplicada no front.
- Situação atual = **última medição dentro do período**.
- O filtro vale para as duas bases (Produção/Testes) e para as duas visões; troca
  de projeto zera o filtro. Sem parâmetro, nada muda para quem já chamava
  (a aba Cobertura não passa filtro).

### Apagar medição de movimentos

- `DELETE /api/monitmov/<customer>/medicao?ambiente=&data=AAAA-MM-DD` — apaga
  `monitmov_dimensoes`, `monitmov_itens` e `monitmov_medicoes` daquela data/base.
- Mesma política do DELETE de cadastros: **só admin**, recusado em "ver como",
  sem desfazer.
- Tela: coluna 🗑 na tabela "Evolução por medição", só para admin real fora da
  área de clientes (`euSou.is_admin && acesso.modo !== 'cliente'`), com confirmação
  mostrando movimentos, combinações e cobertura da medição.
