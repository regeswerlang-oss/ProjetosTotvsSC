# Layout unificado tsc-ui (07/11/2026)

O Gestor de Projetos usa o mesmo layout dos demais dashboards TOTVS SC
(hub DashboardIndex, Cockpit Único e SDHub):

- `web/assets/tsc/tsc-ui.css` — design system escuro (tokens `--tsc-*`, classes `.tsc-*`).
- `web/assets/tsc/tsc-pages.css` — acertos por página; aqui valem os blocos
  `html.tsc-tw` (Tailwind CDN) e `html[data-tsc-page^="projetos"]`.
- `web/assets/tsc/tsc-shell.js` — trilho lateral com a navegação entre os 4 apps.
  Só é carregado para perfis **internos** (`/api/me` → `interno: true`); a área de
  clientes não vê a navegação interna.

Como o tema escuro foi aplicado no `web/index.html` (sem mudar lógica):

1. `tailwind.config` da página remapeia `white` (superfície `#10131c`) e a escala
   `slate` (invertida: 50 = escuro, 900 = texto claro).
2. Cores fixas claras do `<style>` e de estilos inline foram convertidas para a
   paleta escura.
3. KPIs do resumo usam `.tsc-kpi` (card escuro, valor colorido).

Fonte canônica dos 3 arquivos: pasta `ui/` do repo DashboardIndex — ao mudar,
altere lá e copie para `web/assets/tsc/`.
