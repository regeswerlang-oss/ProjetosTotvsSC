-- Aba Integrações — Transmite após a reunião com a usuária-chave da Rio Deserto
-- (10/11/2026). Dois ajustes de banco:
--
-- 1. integ_params: parâmetros do monitoramento por base. Hoje só o prazo do
--    evento (tra_prazo_dias: 60, 90 ou 180). A Rio Deserto trabalha com 60.
-- 2. integ_ocorrencias: ocorrências do portal do Transmite que a base do
--    Protheus não enxerga (PDF que não abre, busca lenta, captura por e-mail),
--    registradas à mão para anexar ao chamado do PO de Produto.

alter table cockpit.protheus_ambientes
  add column if not exists integ_params jsonb not null default '{}'::jsonb;
comment on column cockpit.protheus_ambientes.integ_params is
  'Aba Integracoes: parametros por base. tra_prazo_dias = prazo do evento do Transmite (60/90/180).';

create table if not exists cockpit.integ_ocorrencias (
  id          bigserial primary key,
  customer    text not null,
  ambiente    text not null,
  grupo       text not null default 'transmite',
  ocorrido_em timestamptz not null,
  tipo        text not null check (tipo in ('pdf','busca','captura_email','status','outro')),
  usuario     text,
  descricao   text not null,
  chamado     text,
  criado_por  text,
  criado_em   timestamptz not null default now()
);
create index if not exists integ_ocorrencias_cli on cockpit.integ_ocorrencias (customer, ambiente, ocorrido_em desc);
alter table cockpit.integ_ocorrencias enable row level security;
comment on table cockpit.integ_ocorrencias is
  'Ocorrencias do portal do Transmite registradas a mao (aba Integracoes, M8).';

-- O prazo da Rio Deserto (60 × 90) fica para a usuária-chave confirmar (ação A6):
-- trocar pela própria tela (seletor na caixa do Transmite).
