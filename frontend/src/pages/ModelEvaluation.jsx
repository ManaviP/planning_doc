import { useEffect, useMemo, useState } from 'react';
import { Activity, FlaskConical, Gauge } from 'lucide-react';
import { useParams } from 'react-router-dom';
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';

import Panel from '../components/ui/Panel';
import Reveal from '../components/ui/Reveal';
import SectionHeader from '../components/ui/SectionHeader';
import { apiUrl } from '../config/api';
const REQUEST_TIMEOUT_MS = 20000;

export default function ModelEvaluation() {
  const { id } = useParams();
  const [evaluation, setEvaluation] = useState(null);
  const [simulation, setSimulation] = useState(null);
  const [simulationReason, setSimulationReason] = useState('');
  const [iterations, setIterations] = useState(300);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [refreshKey, setRefreshKey] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    const timeout = window.setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);

    async function load() {
      if (!id) return;
      setLoading(true);
      setError('');
      try {
        const evalResp = await fetch(apiUrl(`/results/${id}/evaluation`), {
          signal: controller.signal,
        });

        if (!evalResp.ok) {
          throw new Error(`Evaluation request failed: ${evalResp.status}`);
        }

        const evalJson = await evalResp.json();
        if (evalJson?.available === false) {
          setEvaluation(null);
          setSimulation(null);
          setSimulationReason('');
          setError(evalJson.reason || 'Model evaluation is not available yet for this workload.');
          return;
        }
        setEvaluation(evalJson);

        try {
          const simResp = await fetch(apiUrl(`/results/${id}/simulation?iterations=${iterations}`), {
            signal: controller.signal,
          });
          if (simResp.ok) {
            const simJson = await simResp.json();
            if (simJson?.available === false) {
              setSimulation(null);
              setSimulationReason(simJson.reason || 'Simulation is not available yet.');
            } else {
              setSimulation(simJson);
              setSimulationReason('');
            }
          } else {
            setSimulation(null);
            setSimulationReason('Simulation request failed.');
          }
        } catch (simErr) {
          if (simErr?.name === 'AbortError') {
             setSimulationReason('Simulation request timed out. Try refreshing.');
          } else {
             setSimulationReason('Simulation is temporarily unavailable.');
          }
        }
      } catch (err) {
        if (err?.name === 'AbortError') {
          setError('Evaluation request timed out. The operation was too slow or you refreshed. Please try again.');
        } else {
          setError(err.message || 'Failed to load model evaluation');
        }
      } finally {
        setLoading(false);
      }
    }

    load();

    return () => {
      window.clearTimeout(timeout);
      controller.abort();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id, refreshKey]);

  const predVsActual = useMemo(() => {
    if (!evaluation) return [];
    return [
      {
        metric: 'Latency (ms)',
        predicted: Number(evaluation.predicted.latency_ms || 0),
        actual: Number(evaluation.actual.latency_ms || 0),
      },
      {
        metric: 'Failure (%)',
        predicted: Number(evaluation.predicted.failure_probability || 0) * 100,
        actual: Number(evaluation.actual.failure_probability || 0) * 100,
      },
      {
        metric: 'Demand',
        predicted: Number(evaluation.predicted.resource_demand || 0),
        actual: Number(evaluation.actual.resource_demand || 0),
      },
    ];
  }, [evaluation]);

  if (loading) {
    return (
      <section className="mx-auto max-w-7xl space-y-6 px-1 py-2">
        <div className="shimmer h-48 rounded-[28px] border border-white/10 bg-white/5" />
        <div className="shimmer h-64 rounded-[28px] border border-white/10 bg-white/5" />
      </section>
    );
  }

  if (error) {
    return (
      <section className="mx-auto max-w-7xl px-1 py-2">
        <Panel className="p-8">
          <p className="text-rose-300">{error}</p>
        </Panel>
      </section>
    );
  }

  return (
    <section className="mx-auto max-w-7xl space-y-8 px-1 py-2">
      <Reveal>
        <Panel className="p-8 sm:p-10">
          <SectionHeader
            eyebrow="Model evaluation"
            title="Prediction Accuracy Dashboard"
            description="Compare predicted vs actual behavior for selected workload and inspect Monte Carlo simulation confidence before production hardening."
          />
          <div className="mt-5 flex flex-wrap items-center gap-3 rounded-2xl border border-white/10 bg-white/4 p-4">
            <label className="text-xs uppercase tracking-[0.22em] text-slate-400">
              Simulation iterations
            </label>
            <input
              type="number"
              min={20}
              max={5000}
              step={20}
              value={iterations}
              onChange={(e) => setIterations(Number(e.target.value || 20))}
              className="input-field w-40"
            />
            <button type="button" className="control-button" onClick={() => setRefreshKey((x) => x + 1)}>
              Refresh evaluation
            </button>
          </div>
          <div className="mt-7 grid gap-4 md:grid-cols-4">
            <Kpi icon={Gauge} label="Overall accuracy" value={`${(Number(evaluation?.accuracy?.overall_accuracy || 0) * 100).toFixed(1)}%`} />
            <Kpi icon={Activity} label="Latency error" value={`${Number(evaluation?.errors?.latency_abs_error || 0).toFixed(2)} ms`} />
            <Kpi icon={Activity} label="Failure error" value={`${(Number(evaluation?.errors?.failure_abs_error || 0) * 100).toFixed(2)} pp`} />
            <Kpi icon={FlaskConical} label="Sim SLA breach" value={`${(Number(simulation?.simulation?.sla_breach_rate || 0) * 100).toFixed(1)}%`} />
          </div>
        </Panel>
      </Reveal>

      <Reveal>
        <Panel className="p-7">
          <h3 className="text-lg font-semibold text-white">Predicted vs Actual</h3>
          <p className="mt-2 text-sm text-slate-400">Direct comparison across key prediction dimensions.</p>
          <div className="mt-6 h-80 w-full">
            <ResponsiveContainer>
              <BarChart data={predVsActual}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(148,163,184,0.2)" />
                <XAxis dataKey="metric" stroke="#94a3b8" />
                <YAxis stroke="#94a3b8" />
                <Tooltip
                  contentStyle={{
                    backgroundColor: '#020617',
                    border: '1px solid rgba(148,163,184,0.3)',
                    borderRadius: 12,
                    color: '#e2e8f0',
                  }}
                />
                <Bar dataKey="predicted" fill="#38bdf8" radius={[6, 6, 0, 0]} />
                <Bar dataKey="actual" fill="#22c55e" radius={[6, 6, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Panel>
      </Reveal>

      <Reveal>
        <Panel className="p-7">
          <h3 className="text-lg font-semibold text-white">Simulation Summary (Monte Carlo)</h3>
          {simulation?.simulation ? (
            <div className="mt-5 grid gap-4 md:grid-cols-3">
              <Stat label="Iterations" value={String(simulation?.simulation?.iterations ?? 0)} />
              <Stat label="Latency mean" value={`${Number(simulation?.simulation?.latency_ms_mean || 0).toFixed(2)} ms`} />
              <Stat label="Latency p95" value={`${Number(simulation?.simulation?.latency_ms_p95 || 0).toFixed(2)} ms`} />
              <Stat label="Failure mean" value={`${(Number(simulation?.simulation?.failure_prob_mean || 0) * 100).toFixed(2)}%`} />
              <Stat label="Failure p95" value={`${(Number(simulation?.simulation?.failure_prob_p95 || 0) * 100).toFixed(2)}%`} />
              <Stat label="Demand mean" value={Number(simulation?.simulation?.demand_mean || 0).toFixed(3)} />
            </div>
          ) : (
            <div className="mt-5 rounded-2xl border border-white/10 bg-white/4 p-4 text-sm text-slate-300">
              {simulationReason || 'Simulation is not available yet.'}
            </div>
          )}
        </Panel>
      </Reveal>
    </section>
  );
}

function Kpi({ icon: Icon, label, value }) {
  return (
    <div className="rounded-2xl border border-white/10 bg-white/4 p-4">
      <div className="flex items-center gap-2 text-slate-400">
        <Icon size={15} />
        <p className="text-[11px] uppercase tracking-[0.24em]">{label}</p>
      </div>
      <p className="mt-3 text-2xl font-semibold text-white">{value}</p>
    </div>
  );
}

function Stat({ label, value }) {
  return (
    <div className="rounded-2xl border border-white/10 bg-white/4 p-4">
      <p className="text-[11px] uppercase tracking-[0.24em] text-slate-400">{label}</p>
      <p className="mt-3 text-lg font-semibold text-white">{value}</p>
    </div>
  );
}
