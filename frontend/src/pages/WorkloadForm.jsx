import { useEffect, useMemo, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import {
  ArrowRight,
  CircleAlert,
  DatabaseZap,
  GitCompareArrows,
  Rocket,
  Send,
  Sparkles,
} from 'lucide-react';

import Panel from '../components/ui/Panel';
import Reveal from '../components/ui/Reveal';
import SectionHeader from '../components/ui/SectionHeader';
import StatusBadge from '../components/ui/StatusBadge';
import { useWorkloadContext } from '../context/WorkloadContext';

const API_BASE_URL = 'http://localhost:8000';
const RECENT_WORKLOADS_POLL_MS = 10000;

const defaultWorkload = {
  name: '',
  container_image: 'python:3.11-slim',
  cpu_cores: 1,
  gpu_units: '',
  memory_gb: 1,
  latency_sla_ms: 500,
  failure_prob_sla_pct: 10,
  risk_tolerance: 'medium',
  budget_usd: '',
  energy_preference: 'any',
  priority: '3',
};

const numericRules = {
  cpu_cores: { min: 0.1, max: 32 },
  gpu_units: { min: 0, max: 8 },
  memory_gb: { min: 0.1, max: 256 },
  latency_sla_ms: { min: 10, max: 30000 },
  failure_prob_sla_pct: { min: 1, max: 99 },
};

export default function WorkloadForm() {
  const navigate = useNavigate();
  const { setCurrentWorkloadId } = useWorkloadContext();

  const [workloadA, setWorkloadA] = useState(defaultWorkload);
  const [workloadB, setWorkloadB] = useState({ ...defaultWorkload, name: 'Competing workload' });
  const [showCompetition, setShowCompetition] = useState(false);
  const [errorsA, setErrorsA] = useState({});
  const [errorsB, setErrorsB] = useState({});
  const [submitting, setSubmitting] = useState(false);
  const [toast, setToast] = useState('');
  const [globalError, setGlobalError] = useState('');
  const [recentWorkloads, setRecentWorkloads] = useState([]);

  useEffect(() => {
    const timer = toast ? window.setTimeout(() => setToast(''), 3500) : null;
    return () => {
      if (timer) {
        window.clearTimeout(timer);
      }
    };
  }, [toast]);

  const refreshRecentWorkloads = async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/workloads`);
      if (!response.ok) {
        throw new Error(`Failed to fetch recent workloads (${response.status})`);
      }
      const rows = await response.json();
      setRecentWorkloads(Array.isArray(rows) ? rows.slice(0, 10) : []);
    } catch (error) {
      console.error('Failed to fetch recent workloads', error);
      return;
    }
  };

  useEffect(() => {
    refreshRecentWorkloads();
    const intervalId = window.setInterval(refreshRecentWorkloads, RECENT_WORKLOADS_POLL_MS);

    return () => {
      window.clearInterval(intervalId);
    };
  }, []);

  const setField = (target, updater) => {
    if (target === 'A') {
      setWorkloadA((current) => updater(current));
      return;
    }
    setWorkloadB((current) => updater(current));
  };

  const validateWorkload = (form) => {
    const nextErrors = {};

    if (!String(form.name).trim()) nextErrors.name = 'Name is required.';
    if (!String(form.container_image).trim()) nextErrors.container_image = 'Container image is required.';

    Object.entries(numericRules).forEach(([field, limits]) => {
      const value = form[field];
      if (field === 'gpu_units' && (value === '' || value == null)) {
        return;
      }
      const numericValue = Number(value);
      if (Number.isNaN(numericValue)) {
        nextErrors[field] = 'Enter a numeric value.';
        return;
      }
      if (numericValue < limits.min || numericValue > limits.max) {
        nextErrors[field] = `Value must be between ${limits.min} and ${limits.max}.`;
      }
    });

    if (form.budget_usd !== '' && Number(form.budget_usd) < 0) {
      nextErrors.budget_usd = 'Budget must be 0 or greater.';
    }

    return nextErrors;
  };

  const buildPayload = (form) => ({
    name: String(form.name).trim(),
    container_image: String(form.container_image).trim(),
    cpu_cores: Number(form.cpu_cores),
    gpu_units: form.gpu_units === '' ? null : Number(form.gpu_units),
    memory_gb: Number(form.memory_gb),
    latency_sla_ms: Number(form.latency_sla_ms),
    failure_prob_sla: Number(form.failure_prob_sla_pct) / 100,
    risk_tolerance: form.risk_tolerance,
    budget_usd: form.budget_usd === '' ? null : Number(form.budget_usd),
    energy_preference: form.energy_preference,
    priority: Number(form.priority),
  });

  const buildPreviewPayload = (form) => ({
    name: String(form.name || 'preview-workload').trim() || 'preview-workload',
    cpu_cores: Number(form.cpu_cores || 1),
    memory_gb: Number(form.memory_gb || 1),
    priority: Number(form.priority || 3),
    policy: {
      max_monthly_budget_usd: form.budget_usd === '' ? null : Number(form.budget_usd),
      max_failure_probability: Number(form.failure_prob_sla_pct || 10) / 100,
      max_latency_ms: Number(form.latency_sla_ms || 500),
      allowed_clouds: ['aws', 'azure', 'gcp'],
      allowed_regions: ['eu-west-1', 'westeurope', 'europe-west4'],
    },
    weights: {
      cost: 0.3,
      risk: 0.35,
      latency: 0.25,
      energy: 0.1,
    },
  });

  const submitSingle = async () => {
    const validationErrors = validateWorkload(workloadA);
    setErrorsA(validationErrors);
    if (Object.keys(validationErrors).length > 0) {
      return;
    }

    setSubmitting(true);
    setGlobalError('');
    try {
      const response = await fetch(`${API_BASE_URL}/workloads`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(buildPayload(workloadA)),
      });
      if (!response.ok) {
        throw new Error(await response.text());
      }
      const created = await response.json();
      setCurrentWorkloadId(created.workload_id);
      navigate(`/decision/${created.workload_id}`);
    } catch (error) {
      setGlobalError(error.message || 'Submission failed.');
    } finally {
      setSubmitting(false);
    }
  };

  const submitCompetition = async () => {
    const nextErrorsA = validateWorkload(workloadA);
    const nextErrorsB = validateWorkload(workloadB);
    setErrorsA(nextErrorsA);
    setErrorsB(nextErrorsB);
    if (Object.keys(nextErrorsA).length > 0 || Object.keys(nextErrorsB).length > 0) {
      return;
    }

    setSubmitting(true);
    setGlobalError('');
    try {
      const response = await fetch(`${API_BASE_URL}/simulate/competition`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          workload_a: buildPayload(workloadA),
          workload_b: buildPayload(workloadB),
        }),
      });
      if (!response.ok) {
        throw new Error(await response.text());
      }

      const result = await response.json();
      const workloadAId = result.workload_a_id ?? result.workload_id_a ?? result.workload_id;
      const workloadBId = result.workload_b_id ?? result.workload_id_b;
      if (!workloadAId) {
        throw new Error('Competition endpoint did not return workload_a_id.');
      }

      setCurrentWorkloadId(workloadAId);
      setToast(`Both submitted. Workload B: ${workloadBId ?? 'unknown'}`);
      navigate(`/decision/${workloadAId}`);
    } catch (error) {
      setGlobalError(error.message || 'Competition simulation submission failed.');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <section className="mx-auto max-w-7xl space-y-8 px-1 py-2">
      <Reveal>
        <Panel className="p-8 sm:p-10">
          <SectionHeader
            eyebrow="Workload intake"
            title="Launch a workload into the AI allocator"
            description="Capture workload intent, resource posture, and risk tolerances in a product-grade command surface. You can submit a single request or simulate contention between two workloads without touching backend logic."
          />
          <div className="mt-8 grid gap-4 lg:grid-cols-3">
            <FeatureCard icon={Rocket} title="Single workload flow" copy="Send one workload directly into scenario ranking and deployment." />
            <FeatureCard icon={GitCompareArrows} title="Competition simulation" copy="Model contention by submitting two workloads in one coordinated request." />
            <FeatureCard icon={DatabaseZap} title="Live activity table" copy="Recent workload submissions stay visible through backend-powered live refresh." />
          </div>
        </Panel>
      </Reveal>

      {toast ? <Banner tone="success">{toast}</Banner> : null}
      {globalError ? <Banner tone="error">{globalError}</Banner> : null}

      <div className="grid gap-8 xl:grid-cols-[1.05fr_0.95fr]">
        <div className="space-y-6">
          <Reveal>
            <Panel className="p-6 sm:p-8">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <SectionHeader
                  eyebrow="Submission mode"
                  title="Primary workload"
                  description="This payload becomes the active decision context after submission."
                  align="start"
                />
                <div className="flex flex-wrap gap-3">
                  <button
                    className="control-button"
                    disabled={submitting}
                    onClick={() => navigate('/preview', { state: { previewPayload: buildPreviewPayload(workloadA) } })}
                    type="button"
                  >
                    <Sparkles size={16} />
                    Preview first
                  </button>
                  <button className="control-button" disabled={submitting} onClick={submitSingle} type="button">
                    <Send size={16} />
                    {submitting ? 'Submitting...' : 'Submit workload'}
                  </button>
                </div>
              </div>
              <div className="mt-6">
                <FormFields errors={errorsA} form={workloadA} setField={(name, value) => setField('A', (current) => ({ ...current, [name]: value }))} />
              </div>
            </Panel>
          </Reveal>

          <Reveal delay={0.08}>
            <Panel className="p-6 sm:p-8">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <SectionHeader
                  eyebrow="Contention lab"
                  title="Optional competing workload"
                  description="Turn this on to demonstrate how the platform behaves when multiple workloads compete for the same cluster capacity."
                  align="start"
                />
                <button className="control-button" onClick={() => setShowCompetition((current) => !current)} type="button">
                  <GitCompareArrows size={16} />
                  {showCompetition ? 'Hide comparison flow' : 'Enable comparison flow'}
                </button>
              </div>

              {showCompetition ? (
                <div className="mt-6 space-y-5">
                  <FormFields errors={errorsB} form={workloadB} setField={(name, value) => setField('B', (current) => ({ ...current, [name]: value }))} />
                  <div className="flex justify-end">
                    <button className="control-button" disabled={submitting} onClick={submitCompetition} type="button">
                      <Sparkles size={16} />
                      {submitting ? 'Submitting...' : 'Submit both workloads'}
                    </button>
                  </div>
                </div>
              ) : (
                <div className="mt-6 rounded-[24px] border border-dashed border-white/10 bg-white/[0.02] p-6 text-sm leading-7 text-slate-400">
                  Enable comparison mode when you want to demo priority, contention, and delayed allocation behavior without changing any system rules.
                </div>
              )}
            </Panel>
          </Reveal>
        </div>

        <div className="space-y-6">
          <Reveal>
            <Panel className="p-6 sm:p-8">
              <SectionHeader
                eyebrow="Submission guidance"
                title="Reviewer-friendly defaults"
                description="Use compact `nginx:stable` or `python:3.11-slim` images for clean demos. The UI keeps the form expressive while the system logic stays untouched."
                align="start"
              />
              <div className="mt-6 space-y-4 text-sm leading-7 text-slate-400">
                <div className="rounded-[24px] border border-white/10 bg-white/[0.03] p-5">
                  <p className="font-semibold text-white">Suggested demo configuration</p>
                  <p className="mt-2">CPU 0.25–1.0, memory 0.25–1.0 GB, latency SLA 500–800 ms, and medium risk tolerance usually create fast, stable demo runs.</p>
                </div>
                <div className="rounded-[24px] border border-white/10 bg-white/[0.03] p-5">
                  <p className="font-semibold text-white">What the panel sees</p>
                  <p className="mt-2">The dashboard highlights workload intent, AI-backed trade-offs, and deployment proof points in a clear, polished flow.</p>
                </div>
              </div>
            </Panel>
          </Reveal>

          <Reveal delay={0.08}>
            <Panel className="p-6 sm:p-8">
              <SectionHeader
                eyebrow="Recent activity"
                title="Latest workload submissions"
                description="Recent runs stay visible here so reviewers can jump directly into decisions and deployment traces."
                align="start"
              />
              <div className="mt-6 overflow-hidden rounded-[24px] border border-white/10">
                <table className="min-w-full text-left text-sm text-slate-200">
                  <thead className="bg-white/[0.04] text-[11px] uppercase tracking-[0.24em] text-slate-500">
                    <tr>
                      <th className="px-4 py-4">Name</th>
                      <th className="px-4 py-4">Status</th>
                      <th className="px-4 py-4">Priority</th>
                      <th className="px-4 py-4">Submitted</th>
                      <th className="px-4 py-4">Action</th>
                    </tr>
                  </thead>
                  <tbody>
                    {recentWorkloads.map((workload) => (
                      <tr key={workload.workload_id} className="border-t border-white/5">
                        <td className="px-4 py-4 text-white">{workload.name}</td>
                        <td className="px-4 py-4"><StatusBadge value={workload.status} /></td>
                        <td className="px-4 py-4">{workload.priority}</td>
                        <td className="px-4 py-4 text-slate-400">{new Date(workload.submitted_at).toLocaleString()}</td>
                        <td className="px-4 py-4">
                          <Link className="inline-flex items-center gap-2 text-sm font-semibold text-sky-300 hover:text-sky-200" to={`/decision/${workload.workload_id}`}>
                            View decision
                            <ArrowRight size={15} />
                          </Link>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Panel>
          </Reveal>
        </div>
      </div>
    </section>
  );
}

function FormFields({ form, setField, errors }) {
  const fields = useMemo(
    () => [
      {
        name: 'name',
        label: 'Name',
        hint: 'Human-readable workload label',
        input: <input className="input" type="text" value={form.name} onChange={(event) => setField('name', event.target.value)} />,
      },
      {
        name: 'container_image',
        label: 'Container image',
        hint: 'Example: nginx:stable',
        input: (
          <input className="input" placeholder="python:3.11-slim" type="text" value={form.container_image} onChange={(event) => setField('container_image', event.target.value)} />
        ),
      },
      {
        name: 'cpu_cores',
        label: 'CPU cores',
        hint: '0.1 to 32',
        input: <input className="input" max={32} min={0.1} step={0.1} type="number" value={form.cpu_cores} onChange={(event) => setField('cpu_cores', event.target.value)} />,
      },
      {
        name: 'gpu_units',
        label: 'GPU units',
        hint: 'Optional',
        input: <input className="input" max={8} min={0} step={0.5} type="number" value={form.gpu_units} onChange={(event) => setField('gpu_units', event.target.value)} />,
      },
      {
        name: 'memory_gb',
        label: 'Memory (GB)',
        hint: '0.1 to 256',
        input: <input className="input" max={256} min={0.1} step={0.1} type="number" value={form.memory_gb} onChange={(event) => setField('memory_gb', event.target.value)} />,
      },
      {
        name: 'latency_sla_ms',
        label: 'Latency SLA (ms)',
        hint: '10 to 30000',
        input: <input className="input" max={30000} min={10} step={10} type="number" value={form.latency_sla_ms} onChange={(event) => setField('latency_sla_ms', event.target.value)} />,
      },
      {
        name: 'failure_prob_sla_pct',
        label: 'Failure SLA (%)',
        hint: '1 to 99',
        input: <input className="input" max={99} min={1} step={1} type="number" value={form.failure_prob_sla_pct} onChange={(event) => setField('failure_prob_sla_pct', event.target.value)} />,
      },
      {
        name: 'risk_tolerance',
        label: 'Risk tolerance',
        hint: 'Allocation attitude',
        input: (
          <select className="input" value={form.risk_tolerance} onChange={(event) => setField('risk_tolerance', event.target.value)}>
            <option value="low">low</option>
            <option value="medium">medium</option>
            <option value="high">high</option>
          </select>
        ),
      },
      {
        name: 'budget_usd',
        label: 'Budget USD',
        hint: 'Optional ceiling',
        input: <input className="input" min={0} step={0.01} type="number" value={form.budget_usd} onChange={(event) => setField('budget_usd', event.target.value)} />,
      },
      {
        name: 'energy_preference',
        label: 'Energy preference',
        hint: 'Efficiency weighting',
        input: (
          <select className="input" value={form.energy_preference} onChange={(event) => setField('energy_preference', event.target.value)}>
            <option value="any">any</option>
            <option value="low_power">low_power</option>
          </select>
        ),
      },
      {
        name: 'priority',
        label: 'Priority',
        hint: '1 lowest, 5 highest',
        input: (
          <select className="input" value={form.priority} onChange={(event) => setField('priority', event.target.value)}>
            <option value="1">1</option>
            <option value="2">2</option>
            <option value="3">3</option>
            <option value="4">4</option>
            <option value="5">5</option>
          </select>
        ),
      },
    ],
    [form, setField],
  );

  return (
    <div className="grid gap-4 md:grid-cols-2">
      {fields.map((field) => (
        <label key={field.name} className="rounded-[24px] border border-white/10 bg-white/[0.03] p-4">
          <span className="block text-xs uppercase tracking-[0.26em] text-slate-500">{field.label}</span>
          <p className="mt-1 text-sm text-slate-400">{field.hint}</p>
          <div className="mt-4">{field.input}</div>
          {errors[field.name] ? <span className="mt-2 inline-flex text-xs text-rose-300">{errors[field.name]}</span> : null}
        </label>
      ))}
    </div>
  );
}

function FeatureCard({ icon: Icon, title, copy }) {
  return (
    <motion.div className="rounded-[24px] border border-white/10 bg-white/[0.03] p-5" whileHover={{ y: -6 }}>
      <div className="flex h-11 w-11 items-center justify-center rounded-2xl border border-white/10 bg-sky-400/10 text-sky-200">
        <Icon size={18} />
      </div>
      <h3 className="mt-4 text-lg font-semibold text-white">{title}</h3>
      <p className="mt-2 text-sm leading-7 text-slate-400">{copy}</p>
    </motion.div>
  );
}

function Banner({ children, tone }) {
  const toneClass = tone === 'success' ? 'border-emerald-400/20 bg-emerald-400/10 text-emerald-100' : 'border-rose-400/20 bg-rose-400/10 text-rose-100';

  return (
    <div className={`inline-flex items-center gap-2 rounded-[20px] border px-4 py-3 text-sm ${toneClass}`}>
      <CircleAlert size={16} />
      {children}
    </div>
  );
}
