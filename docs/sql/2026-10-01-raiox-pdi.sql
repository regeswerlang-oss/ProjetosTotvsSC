-- ============================================================================
--  Raio X da célula — schema `pdi`
--  Matriz consultor × módulo com escala 0..5, no mesmo Postgres do app
--  (Supabase kpimalwnswxalwbidkog). Estado de 01/10/2026, já aplicado.
--  Este arquivo é o registro versionado do schema — rodar de novo é idempotente
--  nas tabelas, e as funções são todas CREATE OR REPLACE.
-- ============================================================================
create schema if not exists pdi;

create table if not exists pdi.niveis (
  nivel     smallint primary key,
  rotulo    text not null,
  descricao text,
  cor       text not null
);

create table if not exists pdi.consultores (
  id            uuid primary key default gen_random_uuid(),
  codigo        text not null unique,
  nome          text not null,
  celula        text,
  funcao        text,
  tipo          text,
  tempo_anos    numeric(6,2),
  prod_media    numeric(10,2),
  custo_medio   numeric(10,2),
  email         text,
  frente        text not null default 'Funcional',
  ativo         boolean not null default true,
  ordem         integer not null default 0,
  criado_em     timestamptz not null default now(),
  atualizado_em timestamptz not null default now()
);

create table if not exists pdi.grupos (
  id        uuid primary key default gen_random_uuid(),
  nome      text not null unique,
  cor       text not null default '#64748b',
  ordem     integer not null default 0,
  ativo     boolean not null default true,
  criado_em timestamptz not null default now()
);

create table if not exists pdi.modulos (
  id        uuid primary key default gen_random_uuid(),
  grupo_id  uuid references pdi.grupos(id) on delete set null,
  codigo    text not null unique,
  nome      text not null,
  sigla     text,
  critico   boolean not null default false,
  ativo     boolean not null default true,
  ordem     integer not null default 0,
  criado_em timestamptz not null default now()
);

create table if not exists pdi.avaliacoes (
  id            uuid primary key default gen_random_uuid(),
  consultor_id  uuid not null references pdi.consultores(id) on delete cascade,
  modulo_id     uuid not null references pdi.modulos(id) on delete cascade,
  nivel_auto    smallint check (nivel_auto   between 0 and 5),
  nivel_gestor  smallint check (nivel_gestor between 0 and 5),
  meta          smallint check (meta         between 0 and 5),
  meta_prazo    date,
  observacao    text,
  atualizado_em timestamptz not null default now(),
  unique (consultor_id, modulo_id)
);
create index if not exists avaliacoes_consultor_idx on pdi.avaliacoes(consultor_id);
create index if not exists avaliacoes_modulo_idx    on pdi.avaliacoes(modulo_id);

create table if not exists pdi.historico (
  id           bigserial primary key,
  consultor_id uuid not null,
  modulo_id    uuid not null,
  campo        text not null,          -- auto | gestor | meta
  valor_de     smallint,
  valor_para   smallint,
  autor        text,
  criado_em    timestamptz not null default now()
);
create index if not exists historico_consultor_idx on pdi.historico(consultor_id, criado_em desc);
create index if not exists historico_data_idx      on pdi.historico(criado_em desc);

-- RLS ligado e SEM policy: só service_role enxerga. O app chega pelo
-- DATABASE_URL do backend, que já é o dono da conexão — mesma convenção do
-- schema `cockpit`. Nunca expor `pdi` via PostgREST com anon key.
alter table pdi.niveis      enable row level security;
alter table pdi.consultores enable row level security;
alter table pdi.grupos      enable row level security;
alter table pdi.modulos     enable row level security;
alter table pdi.avaliacoes  enable row level security;
alter table pdi.historico   enable row level security;

-- ── Trigger de histórico ────────────────────────────────────────────────────
-- Toda mudança de nível ou meta vira linha datada. É o que alimenta a curva de
-- evolução — sem isso a aba Evolução não tem como reconstruir nada.
create or replace function pdi.fn_log_avaliacao() returns trigger
language plpgsql security definer as $$
begin
  new.atualizado_em := now();

  if tg_op = 'INSERT' then
    if new.nivel_auto is not null then
      insert into pdi.historico(consultor_id, modulo_id, campo, valor_de, valor_para)
      values (new.consultor_id, new.modulo_id, 'auto', null, new.nivel_auto);
    end if;
    if new.nivel_gestor is not null then
      insert into pdi.historico(consultor_id, modulo_id, campo, valor_de, valor_para)
      values (new.consultor_id, new.modulo_id, 'gestor', null, new.nivel_gestor);
    end if;
    if new.meta is not null then
      insert into pdi.historico(consultor_id, modulo_id, campo, valor_de, valor_para)
      values (new.consultor_id, new.modulo_id, 'meta', null, new.meta);
    end if;
    return new;
  end if;

  if new.nivel_auto is distinct from old.nivel_auto then
    insert into pdi.historico(consultor_id, modulo_id, campo, valor_de, valor_para)
    values (new.consultor_id, new.modulo_id, 'auto', old.nivel_auto, new.nivel_auto);
  end if;
  if new.nivel_gestor is distinct from old.nivel_gestor then
    insert into pdi.historico(consultor_id, modulo_id, campo, valor_de, valor_para)
    values (new.consultor_id, new.modulo_id, 'gestor', old.nivel_gestor, new.nivel_gestor);
  end if;
  if new.meta is distinct from old.meta then
    insert into pdi.historico(consultor_id, modulo_id, campo, valor_de, valor_para)
    values (new.consultor_id, new.modulo_id, 'meta', old.meta, new.meta);
  end if;
  return new;
end $$;

drop trigger if exists trg_log_avaliacao on pdi.avaliacoes;
create trigger trg_log_avaliacao
  before insert or update on pdi.avaliacoes
  for each row execute function pdi.fn_log_avaliacao();

-- ── API do schema — é só por aqui que /api/raiox escreve ────────────────────
create or replace function pdi.fn_snapshot() returns jsonb
language sql stable security definer as $$
  select jsonb_build_object(
    'niveis', (select coalesce(jsonb_agg(to_jsonb(n) order by n.nivel),'[]'::jsonb) from pdi.niveis n),
    'grupos', (select coalesce(jsonb_agg(to_jsonb(g) order by g.ordem, g.nome),'[]'::jsonb) from pdi.grupos g where g.ativo),
    'consultores', (select coalesce(jsonb_agg(to_jsonb(c) order by c.ordem, c.nome),'[]'::jsonb) from pdi.consultores c where c.ativo),
    'modulos', (select coalesce(jsonb_agg(to_jsonb(m) order by m.ordem, m.nome),'[]'::jsonb) from pdi.modulos m where m.ativo),
    'avaliacoes', (select coalesce(jsonb_agg(jsonb_build_object(
        'consultor_id', a.consultor_id, 'modulo_id', a.modulo_id,
        'nivel_auto', a.nivel_auto, 'nivel_gestor', a.nivel_gestor,
        'meta', a.meta, 'meta_prazo', a.meta_prazo, 'observacao', a.observacao,
        'atualizado_em', a.atualizado_em)),'[]'::jsonb) from pdi.avaliacoes a),
    'historico', (select coalesce(jsonb_agg(jsonb_build_object(
        'id', h.id, 'consultor_id', h.consultor_id, 'modulo_id', h.modulo_id,
        'campo', h.campo, 'de', h.valor_de, 'para', h.valor_para,
        'criado_em', h.criado_em) order by h.criado_em desc),'[]'::jsonb)
      from (select * from pdi.historico order by criado_em desc limit 3000) h),
    'total_historico', (select count(*) from pdi.historico),
    'gerado_em', now()
  );
$$;

create or replace function pdi.fn_set_nivel(
  p_consultor uuid, p_modulo uuid, p_campo text, p_valor smallint
) returns jsonb
language plpgsql security definer as $$
begin
  if p_campo not in ('auto','gestor','meta') then
    raise exception 'campo invalido: %', p_campo;
  end if;
  if p_valor is not null and (p_valor < 0 or p_valor > 5) then
    raise exception 'nivel fora da escala 0..5: %', p_valor;
  end if;

  insert into pdi.avaliacoes (consultor_id, modulo_id, nivel_auto, nivel_gestor, meta)
  values (p_consultor, p_modulo,
          case when p_campo='auto'   then p_valor end,
          case when p_campo='gestor' then p_valor end,
          case when p_campo='meta'   then p_valor end)
  on conflict (consultor_id, modulo_id) do update set
    nivel_auto   = case when p_campo='auto'   then p_valor else pdi.avaliacoes.nivel_auto   end,
    nivel_gestor = case when p_campo='gestor' then p_valor else pdi.avaliacoes.nivel_gestor end,
    meta         = case when p_campo='meta'   then p_valor else pdi.avaliacoes.meta         end;

  return (select jsonb_build_object('ok', true,
            'consultor_id', a.consultor_id, 'modulo_id', a.modulo_id,
            'nivel_auto', a.nivel_auto, 'nivel_gestor', a.nivel_gestor, 'meta', a.meta,
            'atualizado_em', a.atualizado_em)
          from pdi.avaliacoes a
          where a.consultor_id = p_consultor and a.modulo_id = p_modulo);
end $$;

create or replace function pdi.fn_set_detalhe(
  p_consultor uuid, p_modulo uuid, p_obs text, p_prazo date
) returns jsonb
language plpgsql security definer as $$
begin
  insert into pdi.avaliacoes (consultor_id, modulo_id, observacao, meta_prazo)
  values (p_consultor, p_modulo, nullif(p_obs,''), p_prazo)
  on conflict (consultor_id, modulo_id) do update set
    observacao = nullif(p_obs,''), meta_prazo = p_prazo;
  return jsonb_build_object('ok', true);
end $$;

create or replace function pdi.fn_set_frente(p_consultor uuid, p_frente text) returns jsonb
language plpgsql security definer as $$
declare v_f text := nullif(btrim(p_frente), '');
begin
  if v_f is null then raise exception 'frente vazia'; end if;
  update pdi.consultores set frente = v_f, atualizado_em = now() where id = p_consultor;
  return jsonb_build_object('ok', true, 'frente', v_f);
end $$;

create or replace function pdi.fn_upsert_modulo(
  p_codigo text, p_nome text, p_sigla text, p_grupo text, p_critico boolean default false
) returns jsonb
language plpgsql security definer as $$
declare v_grupo uuid; v_id uuid; v_ordem int;
begin
  select id into v_grupo from pdi.grupos where nome = p_grupo;
  if v_grupo is null then
    insert into pdi.grupos(nome, ordem)
    values (p_grupo, coalesce((select max(ordem)+1 from pdi.grupos),1))
    returning id into v_grupo;
  end if;
  select coalesce(max(ordem)+1,1) into v_ordem from pdi.modulos;
  insert into pdi.modulos(grupo_id, codigo, nome, sigla, critico, ordem)
  values (v_grupo, p_codigo, p_nome, nullif(p_sigla,''), p_critico, v_ordem)
  on conflict (codigo) do update set nome=excluded.nome, sigla=excluded.sigla,
    grupo_id=excluded.grupo_id, critico=excluded.critico, ativo=true
  returning id into v_id;
  return jsonb_build_object('ok', true, 'id', v_id);
end $$;

-- ATENÇÃO: existe também a assinatura antiga de 4 argumentos (sem p_frente),
-- herdada de um CREATE OR REPLACE que virou sobrecarga. O app sempre chama com
-- 5, então não há ambiguidade; derrube a velha quando puder:
--   drop function if exists pdi.fn_upsert_consultor(text, text, text, text);
create or replace function pdi.fn_upsert_consultor(
  p_codigo text, p_nome text, p_funcao text default null,
  p_celula text default '201', p_frente text default 'Funcional'
) returns jsonb
language plpgsql security definer as $$
declare v_id uuid;
begin
  insert into pdi.consultores(codigo, nome, funcao, celula, frente, ordem)
  values (p_codigo, p_nome, nullif(p_funcao,''), p_celula,
          coalesce(nullif(btrim(p_frente),''),'Funcional'),
          coalesce((select max(ordem)+1 from pdi.consultores),1))
  on conflict (codigo) do update set nome=excluded.nome,
    funcao=coalesce(excluded.funcao, pdi.consultores.funcao),
    frente=excluded.frente, ativo=true
  returning id into v_id;
  return jsonb_build_object('ok', true, 'id', v_id);
end $$;

-- Saída de pessoa é arquivamento, nunca delete: o histórico de níveis fica.
create or replace function pdi.fn_arquivar(p_tipo text, p_id uuid) returns jsonb
language plpgsql security definer as $$
begin
  if p_tipo = 'modulo' then
    update pdi.modulos set ativo = false where id = p_id;
  elsif p_tipo = 'consultor' then
    update pdi.consultores set ativo = false where id = p_id;
  else
    raise exception 'tipo invalido: %', p_tipo;
  end if;
  return jsonb_build_object('ok', true);
end $$;

-- ── Semente da escala ───────────────────────────────────────────────────────
insert into pdi.niveis (nivel, rotulo, descricao, cor) values
 (0,'Não conhece','Sem contato com o módulo','#e2e8f0'),
 (1,'Conhece','Sabe o que é e para que serve; navega no básico','#cffafe'),
 (2,'Treinado','Recebeu treinamento formal do módulo','#a5f3fc'),
 (3,'Acompanhou','Acompanhou uma implantação conduzida por outro','#5eead4'),
 (4,'Implantou','Conduziu implantação do módulo em cliente','#2dd4bf'),
 (5,'Especialista','Referência técnica: resolve exceções e capacita os demais','#0d9488')
on conflict (nivel) do update set rotulo=excluded.rotulo, descricao=excluded.descricao, cor=excluded.cor;

-- ============================================================================
--  Recorte por pessoa (01/10/2026)
--  O consultor (perfil 'consultoria') enxerga só a própria linha. O vínculo
--  login→consultor é o e-mail, preenchido no Cadastro → Equipe. Sem e-mail o
--  consultor não vê nada: falhar fechado é melhor que mostrar a pessoa errada.
-- ============================================================================
create unique index if not exists consultores_email_idx
  on pdi.consultores (lower(email)) where email is not null;

create or replace function pdi.fn_set_email(p_consultor uuid, p_email text) returns jsonb
language plpgsql security definer as $$
declare v_e text := lower(nullif(btrim(p_email), ''));
begin
  if v_e is not null and v_e not like '%@%' then
    raise exception 'e-mail invalido: %', p_email;
  end if;
  if v_e is not null and exists (select 1 from pdi.consultores
        where lower(email) = v_e and id <> p_consultor) then
    raise exception 'esse e-mail ja esta vinculado a outro consultor';
  end if;
  update pdi.consultores set email = v_e, atualizado_em = now() where id = p_consultor;
  return jsonb_build_object('ok', true, 'email', v_e);
end $$;

-- Mesma forma do fn_snapshot(), com uma linha só. Módulos, grupos e níveis vêm
-- inteiros — são as COLUNAS da matriz, não dado de ninguém. O que fica de fora
-- são as outras pessoas.
create or replace function pdi.fn_snapshot_consultor(p_consultor uuid) returns jsonb
language sql stable security definer as $$
  select jsonb_build_object(
    'niveis', (select coalesce(jsonb_agg(to_jsonb(n) order by n.nivel),'[]'::jsonb) from pdi.niveis n),
    'grupos', (select coalesce(jsonb_agg(to_jsonb(g) order by g.ordem, g.nome),'[]'::jsonb) from pdi.grupos g where g.ativo),
    'consultores', (select coalesce(jsonb_agg(to_jsonb(c)),'[]'::jsonb)
                    from pdi.consultores c where c.ativo and c.id = p_consultor),
    'modulos', (select coalesce(jsonb_agg(to_jsonb(m) order by m.ordem, m.nome),'[]'::jsonb) from pdi.modulos m where m.ativo),
    'avaliacoes', (select coalesce(jsonb_agg(jsonb_build_object(
        'consultor_id', a.consultor_id, 'modulo_id', a.modulo_id,
        'nivel_auto', a.nivel_auto, 'nivel_gestor', a.nivel_gestor,
        'meta', a.meta, 'meta_prazo', a.meta_prazo, 'observacao', a.observacao,
        'atualizado_em', a.atualizado_em)),'[]'::jsonb)
      from pdi.avaliacoes a where a.consultor_id = p_consultor),
    'historico', (select coalesce(jsonb_agg(jsonb_build_object(
        'id', h.id, 'consultor_id', h.consultor_id, 'modulo_id', h.modulo_id,
        'campo', h.campo, 'de', h.valor_de, 'para', h.valor_para,
        'criado_em', h.criado_em) order by h.criado_em desc),'[]'::jsonb)
      from (select * from pdi.historico where consultor_id = p_consultor
            order by criado_em desc limit 3000) h),
    'gerado_em', now()
  );
$$;

-- ============================================================================
--  Abrir um módulo em subgrupos (01/10/2026) — o caso "Qualidade"
--  Não precisou de schema novo: quando um módulo é grande demais para uma
--  coluna só, ele VIRA UM GRUPO e as suas frentes viram os módulos. O nível
--  hierárquico já existia; o que muda é onde a linha é desenhada.
--
--  Duas regras ao repetir isso em outro módulo:
--   1. as bandas da matriz são blocos CONTÍGUOS de `modulos.ordem` — abra as
--      posições seguidas antes de inserir, senão o grupo aparece partido;
--   2. arquive o módulo antigo em vez de apagar. Se ele já tiver avaliação,
--      decida antes para onde a nota vai (em geral, para o item "Outros").
-- ============================================================================
update pdi.modulos set ativo = false where codigo = 'QUALIDADE';   -- tinha 0 avaliações

update pdi.grupos set ordem = ordem + 1 where ordem >= 5;
insert into pdi.grupos (nome, cor, ordem) values ('Qualidade', '#be185d', 5)
on conflict (nome) do update set cor = excluded.cor, ordem = excluded.ordem, ativo = true;

update pdi.modulos set ordem = ordem + 3 where ordem >= 17;

insert into pdi.modulos (grupo_id, codigo, nome, sigla, critico, ordem)
select g.id, v.codigo, v.nome, 'SIGAQIE', false, v.ordem
from (values
  ('QUA_ENTRADA',  'Inspeção de Entradas',  16),
  ('QUA_PROCESSO', 'Inspeção de Processos', 17),
  ('QUA_NAO_CONF', 'Não Conformidade',      18),
  ('QUA_OUTROS',   'Outros',                19)
) as v(codigo, nome, ordem)
join pdi.grupos g on g.nome = 'Qualidade'
on conflict (codigo) do update set nome = excluded.nome, sigla = excluded.sigla,
  grupo_id = excluded.grupo_id, ordem = excluded.ordem, ativo = true;

-- ============================================================================
--  Segunda rodada de aberturas (01/10/2026) — Contratos, Faturamento, TAF e
--  Smart View. Mesma regra da Qualidade: o módulo vira GRUPO e as frentes dele
--  viram os módulos. Nenhum dos quatro tinha avaliação lançada.
--
--  A faixa comercial/fiscal (Faturamento, Comercial & Fiscal, TAF) ficou numa
--  família só de laranja/âmbar em valores diferentes: lado a lado na matriz,
--  os três se leem como parentes sem virar a mesma cor.
-- ============================================================================
update pdi.modulos set ativo = false where codigo in ('TAF', 'CONTRATOS', 'RELATORIOS');

insert into pdi.grupos (nome, cor, ordem) values
  ('Suprimentos & Logística',    '#0891b2',  1),
  ('Financeiro & Controladoria', '#7c3aed',  2),
  ('Gestão de Contratos',        '#a855f7',  3),
  ('Faturamento',                '#ea580c',  4),
  ('Comercial & Fiscal',         '#d97706',  5),
  ('TAF',                        '#b45309',  6),
  ('Manufatura & Manutenção',    '#dc2626',  7),
  ('Qualidade',                  '#be185d',  8),
  ('Serviços & Projetos',        '#059669',  9),
  ('Tecnologia & Plataforma',    '#475569', 10),
  ('Smart View',                 '#0ea5e9', 11)
on conflict (nome) do update set cor = excluded.cor, ordem = excluded.ordem, ativo = true;

insert into pdi.modulos (grupo_id, codigo, nome, sigla, critico, ordem)
select g.id, v.codigo, v.nome, v.sigla, false, 900 + row_number() over ()
from (values
  ('Gestão de Contratos', 'CTR_COMPRAS',    'Compras',             'SIGAGCT'),
  ('Gestão de Contratos', 'CTR_VENDAS',     'Vendas',              'SIGAGCT'),
  ('Faturamento',         'FAT_CENARIOS',   'Cenários Comerciais', 'SIGAFAT'),
  ('Faturamento',         'FAT_APP',        'APP',                 'SIGAFAT'),
  ('TAF',                 'TAF_CONFIG',     'Configuração',        'TAF'),
  ('TAF',                 'TAF_REINF',      'Reinf',               'TAF'),
  ('TAF',                 'TAF_EFD',        'EFD Contribuições',   'TAF'),
  ('TAF',                 'TAF_SPED',       'Sped Fiscal',         'TAF'),
  ('TAF',                 'TAF_INTEG',      'Integração',          'TAF'),
  ('Smart View',          'SV_CONFIG',      'Configuração',        'Smart View'),
  ('Smart View',          'SV_CAPACITACAO', 'Capacitação',         'Smart View'),
  ('Smart View',          'SV_DESENV',      'Desenvolvimento',     'Smart View')
) as v(grupo, codigo, nome, sigla)
join pdi.grupos g on g.nome = v.grupo
on conflict (codigo) do update set nome = excluded.nome, sigla = excluded.sigla,
  grupo_id = excluded.grupo_id, ativo = true;

-- O Faturamento que já existia passa a ser um item do próprio grupo.
update pdi.modulos m set grupo_id = g.id
from pdi.grupos g where g.nome = 'Faturamento' and m.codigo = 'FATURAMENTO';

-- Ordem definitiva — blocos contíguos, um por grupo.
update pdi.modulos m set ordem = v.ord
from (values
  ('COMPRAS',1),('ESTOQUE_CUSTOS',2),('IMPORTACAO',3),('GFE',4),('TMS',5),
  ('FINANCEIRO',6),('CONTABILIDADE',7),('ATIVO_FIXO',8),
  ('CTR_COMPRAS',9),('CTR_VENDAS',10),
  ('FAT_CENARIOS',11),('FATURAMENTO',12),('FAT_APP',13),
  ('FISCAL',14),
  ('TAF_CONFIG',15),('TAF_REINF',16),('TAF_EFD',17),('TAF_SPED',18),('TAF_INTEG',19),
  ('PCP',20),('CHAO_FABRICA',21),('MNT',22),
  ('QUA_ENTRADA',23),('QUA_PROCESSO',24),('QUA_NAO_CONF',25),('QUA_OUTROS',26),
  ('SERVICOS',27),('PMS',28),('TAE',29),
  ('CONFIGURADOR',30),('ADVPL_TLPP',31),('FLUIG',32),('INTEGRACOES',33),
  ('SV_CONFIG',34),('SV_CAPACITACAO',35),('SV_DESENV',36)
) as v(cod, ord) where m.codigo = v.cod;

-- ============================================================================
--  Família de grupos (01/10/2026)
--  Um rótulo ACIMA do grupo, usado só no FILTRO. No grid cada grupo continua
--  sendo a sua própria faixa. É o que permite uma opção "Fiscal" na lista e
--  duas bandas (Fiscal e TAF) na matriz, sem inventar um terceiro nível de
--  cabeçalho. `familia` nula = o grupo é a própria família.
-- ============================================================================
alter table pdi.grupos add column if not exists familia text;

update pdi.grupos set nome = 'Fiscal' where nome = 'Comercial & Fiscal';
update pdi.grupos set familia = 'Fiscal' where nome in ('Fiscal', 'TAF');
