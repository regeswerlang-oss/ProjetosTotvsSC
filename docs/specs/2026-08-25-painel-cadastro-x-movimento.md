# Separar cadastro de movimento na aba Cadastros — 25/08/2026

## O pedido e o que ele encontrou

"Mover estas tabelas da aba Cadastros para a aba Movimentos, ajustando o banco."
Duas descobertas mudaram a forma da solução:

1. **Não existia classificação.** `cockpit.monitcad_tabelas` guarda
   `tabela, descricao, modulo, realizado, estimativa…` e a aba mostrava **tudo**
   o que veio na medição. Não havia campo para virar de um painel para o outro.
2. **A aba Movimentos não conta tabelas.** Desde `77f792f` ela é cobertura de
   cenários (`monitmov_dimensoes` / `monitmov_itens` / `monitmov_cenarios`, com
   análise e dim1..dim4). Não há linha de "SD2 = 277" para receber.

Ou seja: **migrar registro de um painel para o outro é impossível** — as duas
pontas têm formatos diferentes. O que faz sentido é a tabela **sair de
Cadastros**, e é isso que foi feito.

## A coluna `painel`

`cockpit.monitcad_tabelas.painel` — `'cadastro'` (default) ou `'movimento'`,
com check constraint e índice `(medicao_id, painel)`.

Default `'cadastro'` de propósito: linha nova sem classificação continua onde
sempre esteve, então nenhuma importação antiga quebra.

Marcadas em 25/08/2026: **34 tabelas, 297 linhas de histórico**. O histórico
**não** foi apagado — a decisão é reversível com um `update`.

| Grupo | Tabelas |
|---|---|
| Compras | SC1, SC7, SC8 |
| Faturamento | SC5, SC6 |
| Notas e livros | SF1, SD1, SF2, SD2, SF3 |
| Financeiro | SE1, SE2, SEB |
| PCP | SC2 |
| Saldos de estoque | SB2, SB8, SB9, SBF, SBJ |
| Ativo | SN3, SN4 |
| Contábil | CV3 |
| Loja | SL1, SL2 |
| Contratos | CN9, CNB |
| Field Service | AB3, AB4, AB5, AB6, AB7, AB8, AB9, ABC |

Critério: **documento e saldo nascem da operação, não do cadastramento.** Somados
junto, distorciam a contagem do projeto — e a pergunta que respondem ("a operação
já rodou?") é a da aba Cobertura, por cenário, não por contagem de tabela.

## Onde o filtro precisa estar

`painel='cadastro'` entra em **todas** as consultas da aba, não só na lista:

- lista de tabelas da última medição;
- agregado por módulo;
- série histórica (`/api/monitcad/<customer>`);
- `SQL_EVO_MEDICOES` e `SQL_EVO_MATRIZ` (visão Evolução).

Esquecer uma delas faz o total do KPI brigar com a soma da lista logo abaixo —
o tipo de inconsistência que destrói a confiança no painel inteiro.

## O importador classifica — e é isso que segura

`TABELAS_MOVIMENTO` em `api/index.py` + `_painel_da_tabela()`: o insert do
`/upload` já grava o painel. **Sem isso, a próxima medição gerada por um script
antigo traria SD2 de volta como `'cadastro'` e a tabela reapareceria na aba.**
Mesmo raciocínio do `TABELAS_IGNORADAS` (SX5/SX6/SX7): a regra mora no
importador, não só no script do Protheus, porque o script tem cópias por cliente
e uma delas sempre fica para trás.

## Efeito medido (25/08/2026, última medição de cada cliente)

| Cliente | Ambiente | Tabelas cad. | Tabelas mov. | Registros cad. | Registros mov. |
|---|---|---:|---:|---:|---:|
| 000348D0 | produção | 43 | 13 | 484 | 178 |
| 000348D0 | teste | 43 | 13 | 484 | 178 |
| TFEHXQ00 | produção | 57 | 14 | 867 | 0 |
| TFEHXQ00 | teste | 122 | 32 | 41.512 | 3.177 |

A Dígitro perde 178 registros do KPI de Cadastros e o Olim/teste 3.177 — é a
correção pretendida, não perda de dado: as linhas continuam na tabela.

## Reverter

```sql
update cockpit.monitcad_tabelas set painel = 'cadastro' where painel = 'movimento';
```

E tirar as tabelas de `TABELAS_MOVIMENTO`, senão o próximo import remarca.
