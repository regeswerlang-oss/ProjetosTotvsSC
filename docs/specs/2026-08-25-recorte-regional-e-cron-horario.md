# Sync horário + recorte regional/carteira (25/08/2026)

## O pedido

1. "Essa sincronização preciso deixar de forma automática de hora em horas."
2. "Sincronize e traga apenas projetos da minha região e clientes."

## 1. Automático de hora em hora — já estava de pé

O `pg_cron` do Supabase (projeto `kpimalwnswxalwbidkog`) tem o **jobid 7,
`projetos-sync`, `0 * * * *`**, chamando por `pg_net`:

```sql
select net.http_get(
  url := 'https://projetos-totvs-sc.vercel.app/api/cron/sync',
  headers := jsonb_build_object('Authorization','Bearer <CRON_SECRET>'),
  timeout_milliseconds := 60000);
```

`cron.job_run_details` mostra `succeeded` em todas as execuções recentes e o
`max(synced_at)` de `cockpit.projetos` acompanha a hora cheia. **Não foi preciso
criar nada** — o botão "⟳ Sincronizar API" segue existindo só para forçar na hora.

Conferência rápida:

```sql
select jobid, schedule, active from cron.job where jobname = 'projetos-sync';
select status, start_time from cron.job_run_details where jobid = 7
 order by start_time desc limit 5;
select count(*), max(synced_at) from cockpit.projetos;
```

## 2. Recorte: quem entra na base

A API PCI devolve **todos** os ~1.758 projetos da TOTVS SC. Passam a entrar só os
que casam com **uma** destas três regras (`no_recorte()` em `api/index.py`):

1. `regiao_coordenador_projeto` ∈ `SYNC_REGIOES` (**201, 202, 211** — SC Sul);
2. `regiao_coordenador_auxiliar` ∈ `SYNC_REGIOES` — pega o caso "titular de outra
   região, auxiliar nosso" (30 projetos);
3. `regiao_cliente_projeto` ∈ `SYNC_REGIOES` **e** status não encerrado
   (`SYNC_ENCERRADOS = finalizado, cancelado`) — cliente da regional com projeto
   vivo coordenado por outra região (PRODUZA/203, GROWTH/601, SOLFACIL/302);
4. ou o cliente está em `cockpit.clientes` (a carteira do Cockpit, 38 clientes) —
   vale mesmo com coordenador de fora.

A regra 3 **precisa** do corte por status: sem ele, `regiao_cliente_projeto = 201`
sozinha arrastaria 644 projetos finalizados (quase todo o resto da base).

Variáveis de ambiente (opcionais, já têm default no código):

| Nome | Default | Efeito |
|---|---|---|
| `SYNC_REGIOES` | `201,202,211` | vazio **desliga o filtro** (volta ao comportamento antigo) |
| `SYNC_PURGE` | `1` | `0` mantém na base o que saiu do recorte |

## 3. Purga — a base não cresce sozinha

Filtrar o `insert` não apaga o que já estava lá, e um projeto que troca de
coordenador/região ficaria preso para sempre. Por isso o `/api/cron/sync` termina
chamando `purga_fora_do_recorte()`, um `delete` com a **mesma regra em SQL**.

> Mexeu em `no_recorte()`, mexa no SQL da purga — e vice-versa. São duas cópias da
> mesma regra, uma em Python (o que entra) e outra em SQL (o que fica).

Limpeza inicial rodada em 25/08/2026: **644 apagados** (todos `Finalizado`),
1.758 → **1.114 projetos**, 221 Em Execução. Nada de irreversível: para trazer de
volta, é só afrouxar `SYNC_REGIOES` e sincronizar.

## 4. O que mudou no código

- `api/index.py`: constantes `SYNC_REGIOES` / `SYNC_PURGE` / `SYNC_ENCERRADOS`;
  `clientes_cockpit()` (cache de 5 min de `cockpit.clientes`), `no_recorte()`,
  `filtra_recorte()`, `purga_fora_do_recorte()`; `/api/sync` e `/api/cron/sync`
  filtram antes de gravar e devolvem `ignorados` (e o cron, `apagados`);
  `/api/health` mostra o recorte ativo.
- `web/index.html`: o alerta do botão informa quantos ficaram de fora; tooltip
  novo.

Cuidado deliberado em `clientes_cockpit()`: se o banco falhar, ela devolve o
último valor conhecido em vez de um conjunto vazio — carteira vazia + purga
ligada apagaria projetos bons.
