-- Compute Allocator schema (Supabase/PostgreSQL)
-- Safe to run multiple times due to IF NOT EXISTS guards.

create table if not exists workloads (
	workload_id text primary key,
	name text not null,
	container_image text not null,
	cpu_cores float8 not null,
	gpu_units float8,
	memory_gb float8 not null,
	latency_sla_ms int not null,
	failure_prob_sla float8 not null,
	risk_tolerance text not null,
	budget_usd float8,
	energy_preference text not null,
	priority int not null,
	submitted_at timestamptz not null,
	status text not null default 'pending'
);

create table if not exists deployment_scenarios (
	scenario_id text primary key,
	workload_id text not null references workloads(workload_id) on delete cascade,
	target_node text not null,
	predicted_latency_ms float8,
	predicted_failure_prob float8,
	estimated_cost_usd float8,
	estimated_energy_kwh float8
);

create table if not exists agent_scores (
	id bigserial primary key,
	scenario_id text references deployment_scenarios(scenario_id) on delete cascade,
	workload_id text not null references workloads(workload_id) on delete cascade,
	agent_name text not null,
	raw_score float8 not null,
	reasoning text
);

create table if not exists decision_results (
	workload_id text primary key references workloads(workload_id) on delete cascade,
	selected_scenario_id text references deployment_scenarios(scenario_id),
	final_scores jsonb,
	decision_reasoning text,
	decided_at timestamptz,
	weight_overrides jsonb
);

create table if not exists log_entries (
	id bigserial primary key,
	workload_id text not null references workloads(workload_id) on delete cascade,
	message text not null,
	level text not null default 'info',
	created_at timestamptz not null default now()
);

create table if not exists node_metrics_snapshots (
	id bigserial primary key,
	node_name text not null,
	cpu_usage_pct float8,
	memory_usage_pct float8,
	gpu_usage_pct float8,
	pod_count int,
	available boolean default true,
	collected_at timestamptz not null default now()
);

-- Deployment run tracking (durable status for UI polling and restart safety)
create table if not exists deployment_runs (
	run_id uuid primary key,
	workload_id text not null references workloads(workload_id) on delete cascade,
	target text not null,
	mode text not null,
	state text not null,
	message text,
	workflow_url text,
	run_url text,
	error_message text,
	created_at timestamptz not null default now(),
	updated_at timestamptz not null default now()
);

-- Tamper-evident audit chain per workload
create table if not exists audit_events (
	id bigserial primary key,
	workload_id text not null references workloads(workload_id) on delete cascade,
	action text not null,
	payload jsonb,
	payload_json text,
	previous_hash text,
	event_hash text not null,
	created_at timestamptz not null default now()
);

create index if not exists idx_workloads_submitted_at on workloads(submitted_at desc);
create index if not exists idx_workloads_status on workloads(status);
create index if not exists idx_scenarios_workload_id on deployment_scenarios(workload_id);
create index if not exists idx_scores_workload_id on agent_scores(workload_id);
create index if not exists idx_logs_workload_created on log_entries(workload_id, created_at desc);
create index if not exists idx_metrics_collected_at on node_metrics_snapshots(collected_at desc);
create index if not exists idx_audit_workload_created on audit_events(workload_id, created_at asc);
create index if not exists idx_deployment_runs_workload_updated on deployment_runs(workload_id, updated_at desc);

