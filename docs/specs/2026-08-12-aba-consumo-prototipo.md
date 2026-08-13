# Aba Consumo — PROTÓTIPO (12/08/2026)

Resumo do projeto **por etapa**, com o realizado, comparado contra a base de
horas do projeto menos as personalizações. Sai do `state.cronograma` que já
alimenta a aba "Por Etapa" — sem chamada nova à API.

**Status: protótipo aguardando validação.** A regra de base ainda tem uma
inconsistência aberta (ver abaixo).

## O que já faz

- **Fora do cálculo e da tela**: qualquer fase/etapa/sub-etapa cujo nome contenha
  `monitoramento e controle` ou `encerramento` (comparação sem acento, então
  "Monitoramento" com ou sem acento cai igual). São esforço de gestão, não de
  entrega — somá-los distorceria o consumo por etapa.
- **Base editável**: `Horas do projeto` (default = HORAS_PREVISTAS do mapa) menos
  `Personalizações` (default 1006) = base de comparação. Os dois campos são
  editáveis para simular.
- **Específicos com seleção**: cada atividade tem caixa para entrar ou não no
  cálculo. Desmarcar recalcula a etapa, o total e o % da base, e a linha da etapa
  ganha um selo "N fora". "Marcar/Desmarcar todos" e "Restaurar seleção" voltam
  ao estado inicial. A seleção é por projeto e zera ao abrir outro.
- **% da base** no fim de cada linha, com barra proporcional, mais uma linha de
  total.

## ⚠ A inconsistência a resolver

Com os números do Olim:

| | horas |
|---|---|
| Horas do projeto | 4.214 |
| − Personalizações | 1.006 |
| **Base** | **3.208** |
| Estimado das etapas exibidas | 5.115 |
| — sendo Específicos | 1.697 |

O estimado das etapas dá **159% da base**. O motivo: os **Específicos continuam
no numerador** enquanto a base já teve as personalizações descontadas. Ou:

1. **A base desconta e o numerador também** — Específicos saem das duas pontas, e
   a aba passa a medir só o esforço de implantação padrão; ou
2. **Nada é descontado** — base = 4.214 e Específicos entram normalmente; ou
3. **São coisas diferentes** — os 1.006 de "personalizações" não são os 1.697 de
   Específicos, e aí falta identificar de onde sai cada número.

Enquanto não fechar, os dois campos ficam editáveis para simular na tela.
