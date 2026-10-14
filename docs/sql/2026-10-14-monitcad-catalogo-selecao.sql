-- Catálogo de tabelas + seleção por projeto (MONITCAD) - 14/10/2026
-- Pedido do Cássio Gularte (e-mail "Ajuste Controle de Cadastros TSC"):
--   * tela de checkbox, por projeto, com toda a lista de tabelas disponível;
--   * gestores cadastram tabela nova sem mexer na query.
-- Aditiva: sem seleção gravada, o script continua saindo da última medição.

-- 1) Catálogo GLOBAL: uma linha por tabela do Protheus, vale para todos os clientes.
create table if not exists cockpit.monitcad_catalogo (
  tabela      text primary key check (tabela ~ '^[A-Z][A-Z0-9]{2}$'),
  modulo      text not null,
  descricao   text not null default '',
  filtro      text,                       -- filtro padrão (raro; o do projeto vence)
  painel      text not null default 'cadastro' check (painel in ('cadastro','movimento')),
  origem      text not null default 'padrao' check (origem in ('padrao','manual')),
  ativo       boolean not null default true,
  created_by  text,
  created_at  timestamptz not null default now(),
  updated_by  text,
  updated_at  timestamptz not null default now()
);

-- 2) Seleção POR PROJETO (customer). modulo/filtro nulos = usa o do catálogo.
--    modulo preenchido = agrupamento só deste projeto (ex.: SA3 em Financeiro na Digitro).
create table if not exists cockpit.monitcad_selecao (
  customer    text not null,
  tabela      text not null references cockpit.monitcad_catalogo(tabela) on update cascade,
  modulo      text,
  filtro      text,
  updated_by  text,
  updated_at  timestamptz not null default now(),
  primary key (customer, tabela)
);

alter table cockpit.monitcad_catalogo enable row level security;
alter table cockpit.monitcad_selecao  enable row level security;
revoke all on cockpit.monitcad_catalogo from anon, authenticated;
revoke all on cockpit.monitcad_selecao  from anon, authenticated;

-- 3) Carga inicial do catálogo. A primeira inserção de cada tabela vence.
--    a) as 4 pedidas pelo Cássio em 14/10/2026, com a descrição dele
insert into cockpit.monitcad_catalogo (tabela, modulo, descricao, origem, created_by, updated_by) values
  ('DA0', 'Faturamento', 'Tabela de Precos (cabecalho)', 'padrao', 'cassio.gularte@totvs.com.br', 'cassio.gularte@totvs.com.br'),
  ('DA1', 'Faturamento', 'Tabela de Precos (itens)',     'padrao', 'cassio.gularte@totvs.com.br', 'cassio.gularte@totvs.com.br'),
  ('ACO', 'Faturamento', 'Regras de Desconto',           'padrao', 'cassio.gularte@totvs.com.br', 'cassio.gularte@totvs.com.br'),
  ('SAL', 'Compras',     'Grupos de Aprovacao',          'padrao', 'cassio.gularte@totvs.com.br', 'cassio.gularte@totvs.com.br')
on conflict (tabela) do nothing;

--    b) tudo o que já foi medido em algum cliente: módulo mais frequente,
--       descrição da medição mais recente
insert into cockpit.monitcad_catalogo (tabela, modulo, descricao, origem)
select t.tabela,
       mode() within group (order by t.modulo),
       (array_agg(t.descricao order by t.data_medicao desc) filter (where coalesce(t.descricao,'') <> ''))[1],
       'padrao'
  from cockpit.monitcad_tabelas t
 where t.tabela ~ '^[A-Z][A-Z0-9]{2}$' and t.modulo is not null
 group by t.tabela
on conflict (tabela) do nothing;

--    c) o conjunto núcleo do front (PADRAO_MONITCAD)
insert into cockpit.monitcad_catalogo (tabela, modulo, descricao, origem) values
  ('SA2', 'Compras', 'Fornecedores'), ('SA5', 'Compras', 'Amarracao Produto x Fornecedor'),
  ('SC1', 'Compras', 'Solicitacao de Compra'), ('SC7', 'Compras', 'Pedido de Compra'),
  ('SC8', 'Compras', 'Cotacoes'), ('SAH', 'Configurador', 'Unidades de Medida'),
  ('SM2', 'Configurador', 'Moedas'), ('CT1', 'Contabilidade', 'Plano de Contas'),
  ('CT5', 'Contabilidade', 'Lancamentos Padrao'), ('CTD', 'Contabilidade', 'Itens Contabeis'),
  ('CTH', 'Contabilidade', 'Classes de Valor'), ('CTT', 'Contabilidade', 'Centro de Custo / Unidade Negocio'),
  ('CV3', 'Contabilidade', 'Saldos Contabeis'), ('CN9', 'Contratos', 'Contratos (cabecalho)'),
  ('NNR', 'Estoque', 'Locais de Estoque'), ('SB1', 'Estoque', 'Cadastro de Produto'),
  ('SBM', 'Estoque', 'Grupos de Produto'), ('SA1', 'Faturamento', 'Clientes'),
  ('SA3', 'Faturamento', 'Vendedores'), ('SA4', 'Faturamento', 'Transportadoras'),
  ('SC5', 'Faturamento', 'Pedido de Venda (cabecalho)'), ('SC6', 'Faturamento', 'Pedido de Venda (itens)'),
  ('SA6', 'Financeiro', 'Bancos'), ('SE1', 'Financeiro', 'Contas a Receber'),
  ('SE2', 'Financeiro', 'Contas a Pagar'), ('SE4', 'Financeiro', 'Condicoes de Pagamento'),
  ('SED', 'Financeiro', 'Naturezas Financeiras'), ('SF1', 'Financeiro', 'Cabecalho NF Entrada'),
  ('SD1', 'Financeiro', 'Itens NF Entrada'), ('SF2', 'Financeiro', 'Cabecalho NF Saida'),
  ('SD2', 'Fiscal', 'Itens NF Saida'), ('SF3', 'Fiscal', 'Livros Fiscais'),
  ('SF4', 'Fiscal', 'Tipos de Entrada e Saida (TES)'), ('SG1', 'PCP', 'Estrutura de Produto'),
  ('SRA', 'RH', 'Funcionarios'), ('AA1', 'Servico', 'Atendentes'),
  ('SL1', 'Loja', 'Venda Frente de Loja')
on conflict (tabela) do nothing;

-- 4) painel: mesma lista de TABELAS_MOVIMENTO do api/index.py
update cockpit.monitcad_catalogo set painel = 'movimento'
 where tabela in ('SC1','SC7','SC8','SC5','SC6','SF1','SD1','SF2','SD2','SF3',
                  'SE1','SE2','SEB','SC2','SB2','SB8','SB9','SBF','SBJ','SN3','SN4',
                  'CV3','SL1','SL2','AB3','AB4','AB5','AB6','AB7','AB8','AB9','ABC',
                  'CN9','CNB');

-- 5) Digitro (000348D0): seleção = as 42 da última medição de produção
--    + SA3 (Financeiro, decisão do Reges em 23/09) + DA0, DA1, ACO + SAL.
insert into cockpit.monitcad_selecao (customer, tabela, modulo, filtro, updated_by)
select '000348D0', t.tabela,
       case when t.modulo is distinct from c.modulo then t.modulo end,
       nullif(t.filtro, ''), 'reges.werlang@totvs.com.br'
  from cockpit.monitcad_tabelas t
  join cockpit.monitcad_medicoes m on m.id = t.medicao_id
  join cockpit.monitcad_catalogo c on c.tabela = t.tabela
 where m.customer = '000348D0' and m.ambiente = 'producao'
   and m.data_medicao = (select max(data_medicao) from cockpit.monitcad_medicoes
                          where customer = '000348D0' and ambiente = 'producao')
on conflict do nothing;

insert into cockpit.monitcad_selecao (customer, tabela, modulo, updated_by) values
  ('000348D0', 'SA3', 'Financeiro', 'reges.werlang@totvs.com.br'),
  ('000348D0', 'DA0', null, 'reges.werlang@totvs.com.br'),
  ('000348D0', 'DA1', null, 'reges.werlang@totvs.com.br'),
  ('000348D0', 'ACO', null, 'reges.werlang@totvs.com.br'),
  ('000348D0', 'SAL', null, 'reges.werlang@totvs.com.br')
on conflict (customer, tabela) do update set modulo = excluded.modulo;
