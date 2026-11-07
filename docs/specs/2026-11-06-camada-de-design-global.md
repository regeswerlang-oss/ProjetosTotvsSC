# Camada de design global — todas as abas (2026-11-06)

Bloco de CSS no `<style>` do `web/index.html` (comentário "CAMADA DE DESIGN")
que moderniza o app inteiro sem tocar no JS nem no HTML de cada aba. Regras
prefixadas com `body` para vencer as utilities do Tailwind CDN.

| Área | O que muda |
|------|------------|
| Tipografia | Inter carregada de `rsms.me` (antes só referenciada), `tnum` para números alinhados, fundo `#F3F6F8`. |
| Header | filete em gradiente Blue → Purple na base; botões com raio 9 px e press. |
| Cards | `.rounded-lg` → 14 px, `.rounded-md` → 9 px, borda `#e3eaf0`, sombra suave em `.bg-white.border`. Cabeçalho do projeto com filete azul à esquerda. |
| Abas | `#tabs-bar` fixa sob o header (sticky, 73 px); `.tab-btn` com indicador em gradiente animado (scaleX) e hover; painéis `#tab-*` entram com fade (`gp-fade`), inclusive sub-abas `.pl-sub/.sub-tab/.emp-tab`. |
| Rail de ações | raio 9 px, hover desliza 2 px, CTA em gradiente com sombra. |
| Botões/campos | transições e press em `main button`; inputs/selects/textarea com raio 10 px e foco TOTVS Blue (anel 3 px); checkbox/radio com `accent-color`. |
| Tabelas | `thead th` em cinza-azulado 600; hover de linha `#f6fbfd`. |
| Dobráveis | `summary` com raio e transição; chevron menor; fase do cronograma em gradiente claro. |
| Barras/selos | `.bar-track` 0,55 rem; `.fill-exec` em gradiente; KPIs da lista (`#resumo`) com gradiente e número maior. |
| Acessibilidade | `prefers-reduced-motion` desliga animações. |

Para uma aba fugir da regra, use uma classe própria mais específica — não
remova o bloco.
