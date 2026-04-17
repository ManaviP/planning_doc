import { useMemo, useState } from 'react';
import { ShieldCheck, Sparkles } from 'lucide-react';
import { useLocation } from 'react-router-dom';

import Panel from '../components/ui/Panel';
import Reveal from '../components/ui/Reveal';
import SectionHeader from '../components/ui/SectionHeader';

const API_BASE_URL = 'http://localhost:8000';

const defaultPayload = {
  name: 'demo-preview',
  cpu_cores: 2,
  memory_gb: 4,
  priority: 3,
  policy: {
    max_monthly_budget_usd: 500,
    max_failure_probability: 0.15,
    max_latency_ms: 220,
    allowed_clouds: ['aws', 'azure', 'gcp'],
    allowed_regions: ['eu-west-1', 'westeurope', 'europe-west4'],
  },
  weights: {
    cost: 0.3,
    risk: 0.35,
    latency: 0.25,
    energy: 0.1,
  },
};

export default function PreviewControlPlane() {
  const location = useLocation();
  const initialPayload = useMemo(() => {
    const incoming = location.state?.previewPayload;
    if (!incoming || typeof incoming !== 'object') {
      return defaultPayload;
    }
    return {
      ...defaultPayload,
      ...incoming,
      policy: {
        ...defaultPayload.policy,
        ...(incoming.policy || {}),
      },
      weights: {
        ...defaultPayload.weights,
        ...(incoming.weights || {}),
      },
    };
  }, [location.state]);

  const [payload, setPayload] = useState(initialPayload);
  const [run, setRun] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [shadowId, setShadowId] = useState('');
  const [actuals, setActuals] = useState({
    actual_cost_monthly_usd: '',
    actual_latency_ms: '',
    actual_failure_probability: '',
  });
  const [actualsStatus, setActualsStatus] = useState('');
  const [trust, setTrust] = useState(null);

  const winner = run?.result?.winner ?? null;
  const ranked = run?.result?.ranked_options ?? [];
  const blocked = useMemo(() => (run?.result?.all_options ?? []).filter((item) => !item.allowed), [run]);

  const runPreview = async () => {
    setLoading(true);
    setError('');
    setActualsStatus('');
    try {
      const response = await fetch(`${API_BASE_URL}/preview/run`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      if (!response.ok) throw new Error(`Preview failed (${response.status})`);
      const data = await response.json();
      setRun(data);
    } catch (err) {
      setError(err.message || 'Preview request failed');
    } finally {
      setLoading(false);
    }
  };

  const registerShadow = async () => {
    if (!winner || !run?.run_id) return;
    setError('');
    setActualsStatus('');
    const body = {
      run_id: run.run_id,
      predicted_cost_monthly_usd: winner.cost_monthly_usd,
      predicted_latency_ms: winner.latency_ms,
      predicted_failure_probability: winner.failure_probability,
    };
    try {
      const response = await fetch(`${API_BASE_URL}/shadow/register`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      if (!response.ok) throw new Error(`Shadow register failed (${response.status})`);
      const data = await response.json();
      setShadowId(data.shadow_id);
      setActualsStatus('Shadow run registered. You can now attach actual outcomes.');
    } catch (err) {
      setError(err.message || 'Shadow registration failed');
    }
  };

  const loadTrust = async () => {
    setError('');
    try {
      const response = await fetch(`${API_BASE_URL}/shadow/trust/summary`);
      if (!response.ok) throw new Error(`Trust summary failed (${response.status})`);
      const data = await response.json();
      setTrust(data);
    } catch (err) {
      setError(err.message || 'Failed to load trust summary');
    }
  };

  const exportTemplates = async () => {
    if (!run?.run_id) return;
    setError('');
    try {
      const response = await fetch(`${API_BASE_URL}/preview/${run.run_id}/export`);
      if (!response.ok) throw new Error(`Export failed (${response.status})`);

      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const anchor = document.createElement('a');
      anchor.href = url;
      anchor.download = `preview-${run.run_id}.zip`;
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      window.URL.revokeObjectURL(url);
    } catch (err) {
      setError(err.message || 'Export request failed');
    }
  };

  const submitActuals = async () => {
    if (!shadowId) {
      setError('Register a shadow run before attaching actual outcomes.');
      return;
    }

    setError('');
    setActualsStatus('');

    const body = {
      actual_cost_monthly_usd: Number(actuals.actual_cost_monthly_usd),
      actual_latency_ms: Number(actuals.actual_latency_ms),
      actual_failure_probability: Number(actuals.actual_failure_probability),
    };

    if (
      Number.isNaN(body.actual_cost_monthly_usd)
      || Number.isNaN(body.actual_latency_ms)
      || Number.isNaN(body.actual_failure_probability)
    ) {
      setError('Provide numeric values for all actual outcome fields.');
      return;
    }

    try {
      const response = await fetch(`${API_BASE_URL}/shadow/${shadowId}/actuals`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      if (!response.ok) throw new Error(`Actuals submission failed (${response.status})`);
      setActualsStatus('Actual outcomes attached successfully.');
      await loadTrust();
    } catch (err) {
      setError(err.message || 'Failed to submit actual outcomes');
    }
  };

  return (
    <section className="mx-auto max-w-7xl space-y-8 px-1 py-2">
      <Reveal>
        <Panel className="p-8 sm:p-10">
          <SectionHeader
            eyebrow="Pre-deployment intelligence"
            title="Free preview control plane"
            description="Run cross-cloud recommendation with guardrails and confidence intervals before deployment."
          />
          <div className="mt-6 grid gap-4 md:grid-cols-2 lg:grid-cols-4">
            <Field label="Name" value={payload.name} onChange={(v) => setPayload((p) => ({ ...p, name: v }))} />
            <Field label="CPU cores" type="number" value={payload.cpu_cores} onChange={(v) => setPayload((p) => ({ ...p, cpu_cores: Number(v) }))} />
            <Field label="Memory GB" type="number" value={payload.memory_gb} onChange={(v) => setPayload((p) => ({ ...p, memory_gb: Number(v) }))} />
            <Field label="Priority (1-5)" type="number" value={payload.priority} onChange={(v) => setPayload((p) => ({ ...p, priority: Number(v) }))} />
          </div>
          <div className="mt-4 grid gap-4 lg:grid-cols-2">
            <div className="rounded-2xl border border-white/10 bg-white/3 p-4">
              <p className="mb-3 text-xs uppercase tracking-[0.2em] text-slate-500">Policy guardrails</p>
              <div className="grid gap-3 sm:grid-cols-2">
                <Field
                  label="Max monthly budget"
                  type="number"
                  value={payload.policy.max_monthly_budget_usd ?? ''}
                  onChange={(v) => setPayload((p) => ({
                    ...p,
                    policy: {
                      ...p.policy,
                      max_monthly_budget_usd: v === '' ? null : Number(v),
                    },
                  }))}
                />
                <Field
                  label="Max latency ms"
                  type="number"
                  value={payload.policy.max_latency_ms ?? ''}
                  onChange={(v) => setPayload((p) => ({
                    ...p,
                    policy: {
                      ...p.policy,
                      max_latency_ms: v === '' ? null : Number(v),
                    },
                  }))}
                />
                <Field
                  label="Max failure probability"
                  type="number"
                  value={payload.policy.max_failure_probability ?? ''}
                  onChange={(v) => setPayload((p) => ({
                    ...p,
                    policy: {
                      ...p.policy,
                      max_failure_probability: v === '' ? null : Number(v),
                    },
                  }))}
                />
              </div>
              <div className="mt-3 grid gap-3">
                <TextField
                  label="Allowed clouds (comma separated)"
                  value={(payload.policy.allowed_clouds || []).join(', ')}
                  onChange={(v) => setPayload((p) => ({
                    ...p,
                    policy: {
                      ...p.policy,
                      allowed_clouds: parseList(v),
                    },
                  }))}
                />
                <TextField
                  label="Allowed regions (comma separated)"
                  value={(payload.policy.allowed_regions || []).join(', ')}
                  onChange={(v) => setPayload((p) => ({
                    ...p,
                    policy: {
                      ...p.policy,
                      allowed_regions: parseList(v),
                    },
                  }))}
                />
              </div>
            </div>

            <div className="rounded-2xl border border-white/10 bg-white/3 p-4">
              <p className="mb-3 text-xs uppercase tracking-[0.2em] text-slate-500">Scoring weights</p>
              <div className="grid gap-3 sm:grid-cols-2">
                <Field
                  label="Cost"
                  type="number"
                  value={payload.weights.cost}
                  onChange={(v) => setPayload((p) => ({ ...p, weights: { ...p.weights, cost: Number(v) } }))}
                />
                <Field
                  label="Risk"
                  type="number"
                  value={payload.weights.risk}
                  onChange={(v) => setPayload((p) => ({ ...p, weights: { ...p.weights, risk: Number(v) } }))}
                />
                <Field
                  label="Latency"
                  type="number"
                  value={payload.weights.latency}
                  onChange={(v) => setPayload((p) => ({ ...p, weights: { ...p.weights, latency: Number(v) } }))}
                />
                <Field
                  label="Energy"
                  type="number"
                  value={payload.weights.energy}
                  onChange={(v) => setPayload((p) => ({ ...p, weights: { ...p.weights, energy: Number(v) } }))}
                />
              </div>
            </div>
          </div>
          <div className="mt-4 flex flex-wrap gap-3">
            <button className="control-button" onClick={runPreview} type="button" disabled={loading}>
              <Sparkles size={16} />
              {loading ? 'Running...' : 'Run preview'}
            </button>
            {run?.run_id ? (
              <button className="control-button" type="button" onClick={exportTemplates}>
                Export templates
              </button>
            ) : null}
            {winner ? (
              <button className="control-button" type="button" onClick={registerShadow}>
                <ShieldCheck size={16} /> Register shadow
              </button>
            ) : null}
            <button className="control-button" type="button" onClick={loadTrust}>Load trust summary</button>
          </div>
          {error ? <p className="mt-4 text-sm text-rose-300">{error}</p> : null}
          {shadowId ? <p className="mt-3 text-sm text-emerald-300">Shadow registered: {shadowId}</p> : null}
          {actualsStatus ? <p className="mt-3 text-sm text-sky-300">{actualsStatus}</p> : null}
        </Panel>
      </Reveal>

      {winner ? (
        <Reveal>
          <Panel className="p-6 sm:p-8">
            <SectionHeader
              eyebrow="Winner"
              title={`${winner.cloud.toUpperCase()} · ${winner.instance_type}`}
              description={run?.result?.explanation}
              align="start"
            />
            <div className="mt-5 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
              <Stat label="Monthly cost" value={`$${Number(winner.cost_monthly_usd).toFixed(2)}`} />
              <Stat label="Latency" value={`${Number(winner.latency_ms).toFixed(2)} ms`} />
              <Stat label="Failure" value={`${(Number(winner.failure_probability) * 100).toFixed(2)}%`} />
              <Stat label="Price source" value={winner.price_source} />
            </div>
            <div className="mt-4 rounded-2xl border border-white/10 bg-white/3 p-4 text-sm text-slate-300">
              Confidence (latency CI90): {winner.confidence?.latency_ms_ci90?.[0]} – {winner.confidence?.latency_ms_ci90?.[1]} ms
              <br />
              Confidence (failure CI85): {winner.confidence?.failure_probability_ci85?.[0]} – {winner.confidence?.failure_probability_ci85?.[1]}
            </div>
          </Panel>
        </Reveal>
      ) : null}

      {ranked.length ? (
        <Reveal>
          <Panel className="p-6 sm:p-8">
            <SectionHeader eyebrow="Ranked options" title="Allowed candidates" align="start" />
            <div className="mt-4 overflow-x-auto rounded-2xl border border-white/10">
              <table className="min-w-full text-sm">
                <thead className="bg-white/4 text-left text-slate-400">
                  <tr>
                    <th className="px-4 py-3">Cloud</th>
                    <th className="px-4 py-3">Region</th>
                    <th className="px-4 py-3">Instance</th>
                    <th className="px-4 py-3">Score</th>
                    <th className="px-4 py-3">Cost/mo</th>
                  </tr>
                </thead>
                <tbody>
                  {ranked.map((item) => (
                    <tr key={`${item.cloud}-${item.region}-${item.instance_type}`} className="border-t border-white/10">
                      <td className="px-4 py-3">{item.cloud}</td>
                      <td className="px-4 py-3">{item.region}</td>
                      <td className="px-4 py-3">{item.instance_type}</td>
                      <td className="px-4 py-3">{item.score}</td>
                      <td className="px-4 py-3">${Number(item.cost_monthly_usd).toFixed(2)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Panel>
        </Reveal>
      ) : null}

      {blocked.length ? (
        <Reveal>
          <Panel className="p-6 sm:p-8">
            <SectionHeader eyebrow="Guardrails" title="Blocked by policy" align="start" />
            <ul className="mt-4 space-y-2 text-sm text-amber-300">
              {blocked.map((item) => (
                <li key={`blocked-${item.cloud}-${item.instance_type}`}>
                  {item.cloud}/{item.region}/{item.instance_type} → {item.policy_violations.join(', ')}
                </li>
              ))}
            </ul>
          </Panel>
        </Reveal>
      ) : null}

      {trust ? (
        <Reveal>
          <Panel className="p-6 sm:p-8">
            <SectionHeader eyebrow="Shadow trust" title="Trust summary" align="start" />
            <div className="mt-4 grid gap-3 lg:grid-cols-2">
              <div className="grid gap-3 sm:grid-cols-3">
                <Stat label="Registered" value={String(trust.registered)} />
                <Stat label="Compared" value={String(trust.compared)} />
                <Stat label="Trust score" value={trust.trust_score == null ? '—' : String(trust.trust_score)} />
              </div>
              <div className="rounded-2xl border border-white/10 bg-white/3 p-4">
                <p className="mb-3 text-xs uppercase tracking-[0.2em] text-slate-500">Attach actual outcomes</p>
                <div className="grid gap-3 sm:grid-cols-3">
                  <Field
                    label="Actual cost"
                    type="number"
                    value={actuals.actual_cost_monthly_usd}
                    onChange={(v) => setActuals((a) => ({ ...a, actual_cost_monthly_usd: v }))}
                  />
                  <Field
                    label="Actual latency"
                    type="number"
                    value={actuals.actual_latency_ms}
                    onChange={(v) => setActuals((a) => ({ ...a, actual_latency_ms: v }))}
                  />
                  <Field
                    label="Actual failure"
                    type="number"
                    value={actuals.actual_failure_probability}
                    onChange={(v) => setActuals((a) => ({ ...a, actual_failure_probability: v }))}
                  />
                </div>
                <div className="mt-3 flex justify-end">
                  <button className="control-button" type="button" onClick={submitActuals}>Submit actuals</button>
                </div>
              </div>
            </div>
          </Panel>
        </Reveal>
      ) : null}
    </section>
  );
}

function TextField({ label, value, onChange }) {
  return (
    <label className="rounded-2xl border border-white/10 bg-white/3 p-3 text-sm text-slate-300">
      <span className="mb-2 block text-xs uppercase tracking-[0.2em] text-slate-500">{label}</span>
      <input
        className="w-full rounded-xl border border-white/10 bg-slate-950/70 px-3 py-2 text-sm text-white outline-none focus:border-sky-400/50"
        type="text"
        value={value}
        onChange={(event) => onChange(event.target.value)}
      />
    </label>
  );
}

function parseList(value) {
  return String(value)
    .split(',')
    .map((v) => v.trim())
    .filter(Boolean);
}

function Field({ label, value, onChange, type = 'text' }) {
  return (
    <label className="rounded-2xl border border-white/10 bg-white/3 p-3 text-sm text-slate-300">
      <span className="mb-2 block text-xs uppercase tracking-[0.2em] text-slate-500">{label}</span>
      <input
        className="w-full rounded-xl border border-white/10 bg-slate-950/70 px-3 py-2 text-sm text-white outline-none focus:border-sky-400/50"
        type={type}
        value={value}
        onChange={(event) => onChange(event.target.value)}
      />
    </label>
  );
}

function Stat({ label, value }) {
  return (
    <div className="rounded-2xl border border-white/10 bg-white/3 p-4">
      <p className="text-xs uppercase tracking-[0.2em] text-slate-500">{label}</p>
      <p className="mt-2 text-lg font-semibold text-white">{value}</p>
    </div>
  );
}
