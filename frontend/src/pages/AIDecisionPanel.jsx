import { useEffect, useMemo, useRef, useState } from 'react';
import { motion } from 'framer-motion';
import { BrainCircuit, Coins, ShieldCheck, Sparkles, TimerReset, Zap } from 'lucide-react';
import { Link, useNavigate, useParams } from 'react-router-dom';

import ParetoGraph from '../components/ParetoGraph';
import ScenarioTable from '../components/ScenarioTable';
import Panel from '../components/ui/Panel';
import Reveal from '../components/ui/Reveal';
import SectionHeader from '../components/ui/SectionHeader';
import SkeletonBlock from '../components/ui/SkeletonBlock';
import StatusBadge from '../components/ui/StatusBadge';
import { useWorkloadContext } from '../context/WorkloadContext';

const API_BASE_URL = 'http://localhost:8000';
const REQUEST_TIMEOUT_MS = 20000;

const DEFAULT_WEIGHTS = {
  CostAgent: 0.3,
  RiskAgent: 0.35,
  LatencyAgent: 0.25,
  EnergyAgent: 0.1,
};

async function fetchDecisionData(workloadId) {
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
  try {
    const response = await fetch(`${API_BASE_URL}/results/${workloadId}/decision-panel`, {
      signal: controller.signal,
    });
    if (!response.ok) throw new Error(`Failed to fetch decision data (${response.status})`);
    return await response.json();
  } catch (error) {
    if (error?.name === 'AbortError') {
      throw new Error('Request timed out while loading decision data. Please retry in a few seconds.');
    }
    throw error;
  } finally {
    window.clearTimeout(timeout);
  }
}

async function fetchLatestWorkloadId() {
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
  try {
    const response = await fetch(`${API_BASE_URL}/workloads`, { signal: controller.signal });
    if (!response.ok) return null;
    const rows = await response.json();
    if (!Array.isArray(rows) || rows.length === 0) return null;
    const active = rows.find((row) =>
      ['evaluating', 'ready_for_deployment', 'deploying', 'deployed'].includes(String(row?.status || '').toLowerCase()),
    );
    return (active ?? rows[0])?.workload_id ?? null;
  } catch (error) {
    if (error?.name === 'AbortError') {
      throw new Error('Request timed out while fetching workloads.');
    }
    throw error;
  } finally {
    window.clearTimeout(timeout);
  }
}

export default function AIDecisionPanel() {
  const params = useParams();
  const navigate = useNavigate();
  const workloadId = params.id ?? params.workload_id;

  const { setCurrentWorkloadId } = useWorkloadContext();

  const [workload, setWorkload] = useState(null);
  const [decision, setDecision] = useState(null);
  const [scenarios, setScenarios] = useState([]);
  const [scores, setScores] = useState([]);
  const [simulation, setSimulation] = useState(null);
  const [expanded, setExpanded] = useState(false);
  const [error, setError] = useState('');
  const [deployMessage, setDeployMessage] = useState('');
  const [deployingTarget, setDeployingTarget] = useState('');
  const [deploymentStatus, setDeploymentStatus] = useState(null);
  const [loading, setLoading] = useState(true);
  const inFlightRef = useRef(false);
  const simulationCache = useRef({});

  useEffect(() => {
    setCurrentWorkloadId(workloadId ?? null);
  }, [setCurrentWorkloadId, workloadId]);

  // ✅ FIX 2: Reset inFlightRef when workloadId changes so a new fetch is
  //    never blocked by a previous in-flight request for a different workload.
  useEffect(() => {
    inFlightRef.current = false;
    setSimulation(simulationCache.current[workloadId] ?? null);
  }, [workloadId]);

  // Decision data fetch
  useEffect(() => {
    let mounted = true;

    const load = async () => {
      if (inFlightRef.current) return;
      if (!workloadId) {
        setLoading(true);
        setError('');
        try {
          const fallbackId = await fetchLatestWorkloadId();
          if (!mounted) return;
          if (fallbackId) {
            navigate(`/decision/${fallbackId}`, { replace: true });
            setCurrentWorkloadId(fallbackId);
          } else {
            setError('No workloads found yet. Submit a workload first from the Workloads page.');
          }
        } catch (resolveError) {
          if (mounted) setError(resolveError.message || 'Failed to resolve a workload for decision view.');
        } finally {
          if (mounted) setLoading(false);
        }
        return;
      }

      inFlightRef.current = true;
      setLoading(true);
      setError('');

      try {
        let effectiveWorkloadId = workloadId;
        let result;
        try {
          result = await fetchDecisionData(effectiveWorkloadId);
        } catch (initialError) {
          if (String(initialError?.message || '').includes('(404)')) {
            const fallbackId = await fetchLatestWorkloadId();
            if (fallbackId && fallbackId !== workloadId) {
              effectiveWorkloadId = fallbackId;
              result = await fetchDecisionData(effectiveWorkloadId);
              navigate(`/decision/${effectiveWorkloadId}`, { replace: true });
              setCurrentWorkloadId(effectiveWorkloadId);
            } else {
              throw initialError;
            }
          } else {
            throw initialError;
          }
        }

        if (!mounted) return;
        setWorkload(result.workload);
        setDecision(result.decision);
        setScenarios(result.scenarios);
        setScores(result.scores);
      } catch (loadError) {
        if (mounted) setError(loadError.message || 'Failed to load decision data.');
      } finally {
        inFlightRef.current = false;
        if (mounted) setLoading(false);
      }
    };

    load();
    return () => { mounted = false; };
  }, [navigate, setCurrentWorkloadId, workloadId]);

  // ✅ FIX 3: Simulation effect no longer depends on `simulationLoaded` state.
  //    Instead it checks the cache directly, which is a ref (stable, never
  //    triggers re-render). This breaks the abort loop:
  //      OLD: set simulationLoaded=true → effect re-runs → cleanup aborts fetch
  //      NEW: cache ref checked synchronously; effect only re-runs on workloadId change.
  useEffect(() => {
    if (!workloadId) return;

    // Already cached — nothing to fetch.
    if (simulationCache.current[workloadId]) {
      setSimulation(simulationCache.current[workloadId]);
      return;
    }

    const controller = new AbortController();

    const fetchSimulation = async () => {
      try {
        const res = await fetch(
          `${API_BASE_URL}/results/${workloadId}/simulation?iterations=300`,
          { signal: controller.signal },
        );
        if (res.ok) {
          const data = await res.json();
          simulationCache.current[workloadId] = data;
          setSimulation(data);
        }
      } catch (err) {
        if (err?.name !== 'AbortError') {
          console.error('Simulation fetch failed:', err);
        }
      }
    };

    fetchSimulation();

    // Cleanup only aborts if workloadId actually changes — not on every render.
    return () => controller.abort();
  }, [workloadId]); // ✅ simulationLoaded removed from deps

  const triggerDeployment = async (target) => {
    if (!workloadId || deployingTarget) return;

    setDeployingTarget(target);
    setDeployMessage('');

    try {
      const response = await fetch(`${API_BASE_URL}/workloads/${workloadId}/deploy`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ target }),
      });

      const payload = await response.json().catch(() => ({}));
      if (!response.ok) {
        throw new Error(payload?.detail || `Deployment request failed (${response.status})`);
      }

      setDeployMessage(payload?.message || `Deployment triggered for ${target}.`);
      if (payload?.run_url) {
        setDeployMessage(`${payload.message} View run: ${payload.run_url}`);
      }
      const refreshed = await fetchDecisionData(workloadId);
      setWorkload(refreshed.workload);
      setDecision(refreshed.decision);
      setScenarios(refreshed.scenarios);
      setScores(refreshed.scores);
    } catch (deployError) {
      setDeployMessage(deployError?.message || 'Failed to trigger deployment.');
    } finally {
      setDeployingTarget('');
    }
  };

  const retryDeployment = async () => {
    if (!workloadId || deployingTarget) return;
    setDeployingTarget('retry');
    setDeployMessage('');
    try {
      const response = await fetch(`${API_BASE_URL}/workloads/${workloadId}/deploy/retry`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ target: deploymentStatus?.target || 'local' }),
      });
      const payload = await response.json().catch(() => ({}));
      if (!response.ok) {
        throw new Error(payload?.detail || `Retry failed (${response.status})`);
      }
      setDeployMessage(payload?.message || 'Deployment retry triggered.');
      const refreshed = await fetchDecisionData(workloadId);
      setWorkload(refreshed.workload);
      setDecision(refreshed.decision);
      setScenarios(refreshed.scenarios);
      setScores(refreshed.scores);
    } catch (retryError) {
      setDeployMessage(retryError?.message || 'Failed to retry deployment.');
    } finally {
      setDeployingTarget('');
    }
  };

  const cancelDeployment = async () => {
    if (!workloadId || deployingTarget) return;
    setDeployingTarget('cancel');
    setDeployMessage('');
    try {
      const response = await fetch(`${API_BASE_URL}/workloads/${workloadId}/deploy/cancel`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ reason: 'Cancelled from decision panel.' }),
      });
      const payload = await response.json().catch(() => ({}));
      if (!response.ok) {
        throw new Error(payload?.detail || `Cancel failed (${response.status})`);
      }
      setDeployMessage(payload?.message || 'Deployment cancelled.');
      const refreshed = await fetchDecisionData(workloadId);
      setWorkload(refreshed.workload);
      setDecision(refreshed.decision);
      setScenarios(refreshed.scenarios);
      setScores(refreshed.scores);
    } catch (cancelError) {
      setDeployMessage(cancelError?.message || 'Failed to cancel deployment.');
    } finally {
      setDeployingTarget('');
    }
  };

  useEffect(() => {
    if (!workloadId) return;

    let cancelled = false;
    const shouldPoll = ['deploying', 'ready_for_deployment', 'delayed'].includes(String(workload?.status || '').toLowerCase());
    const intervalMs = shouldPoll ? 5000 : 15000;

    const pollStatus = async () => {
      try {
        const response = await fetch(`${API_BASE_URL}/workloads/${workloadId}/deploy/status`);
        if (!response.ok) return;
        const payload = await response.json();
        if (!cancelled) {
          setDeploymentStatus(payload);
        }
      } catch {
        // keep silent: polling is best effort
      }
    };

    pollStatus();
    const timer = window.setInterval(pollStatus, intervalMs);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [workloadId, workload?.status]);

  const selectedScenario = useMemo(
    () => scenarios.find((s) => s.scenario_id === decision?.selected_scenario_id) ?? null,
    [decision?.selected_scenario_id, scenarios],
  );
  const structuredReasoning = useMemo(
    () => buildStructuredReasoning(decision),
    [decision],
  );

  const weights = decision?.weight_overrides
    ? { ...DEFAULT_WEIGHTS, ...decision.weight_overrides }
    : DEFAULT_WEIGHTS;

  const hasCustomWeights = Boolean(
    decision?.weight_overrides && Object.keys(decision.weight_overrides).length > 0,
  );

  const reasoningTone = getReasoningTone(workload, selectedScenario);

  const summaryCards = [
    { label: 'Selected node', value: selectedScenario?.target_node ?? 'Awaiting decision', icon: BrainCircuit },
    { label: 'Predicted latency', value: selectedScenario ? `${Number(selectedScenario.predicted_latency_ms).toFixed(2)} ms` : '—', icon: TimerReset },
    { label: 'Failure risk', value: selectedScenario ? `${(Number(selectedScenario.predicted_failure_prob) * 100).toFixed(2)}%` : '—', icon: ShieldCheck },
    { label: 'Estimated cost', value: selectedScenario ? `$${Number(selectedScenario.estimated_cost_usd).toFixed(4)}` : '—', icon: Coins },
  ];

  return (
    <section className="mx-auto max-w-7xl space-y-8 px-1 py-2">
      <Reveal>
        <Panel className="p-8 sm:p-10">
          <SectionHeader
            eyebrow="AI decision workspace"
            title="Deployment Decision Panel"
            description="Follow how the orchestrator translated workload intent into ranked infrastructure scenarios, weighted agent scores, and a selected deployment path."
            actions={
              <div className="space-y-2 text-right text-sm text-slate-400">
                <div>Workload <span className="font-mono text-sky-200">{workloadId}</span></div>
                {workload ? <StatusBadge value={workload.status} /> : null}
              </div>
            }
          />
          {loading ? (
            <div className="mt-8 grid gap-4 md:grid-cols-4">
              {Array.from({ length: 4 }).map((_, index) => (
                <SkeletonBlock key={index} className="h-32" />
              ))}
            </div>
          ) : null}
          {!loading && !error ? (
            <div className="mt-8 grid gap-4 md:grid-cols-2 xl:grid-cols-4">
              {summaryCards.map((card) => {
                const Icon = card.icon;
                return (
                  <motion.div key={card.label} className="rounded-3xl border border-white/10 bg-white/3 p-5" whileHover={{ y: -5 }}>
                    <div className="flex items-center justify-between gap-3">
                      <p className="text-xs uppercase tracking-[0.26em] text-slate-500">{card.label}</p>
                      <Icon size={16} className="text-sky-300" />
                    </div>
                    <p className="mt-4 text-xl font-semibold text-white">{card.value}</p>
                  </motion.div>
                );
              })}
            </div>
          ) : null}
        </Panel>
      </Reveal>

      {error ? <PanelMessage tone="error">{error}</PanelMessage> : null}

      {!loading && !error ? (
        <div className="space-y-8">
          <Reveal>
            <Panel className="p-6 sm:p-8">
              <SectionHeader
                eyebrow="Scenario ranking"
                title="Negotiated deployment shortlist"
                description="Ranked scenarios combine the latest agent votes with final weighted scores so reviewers can inspect the winner and the viable alternatives side by side."
              />
              <div className="mt-6">
                <ScenarioTable
                  finalScores={decision?.final_scores ?? {}}
                  scenarios={scenarios}
                  scores={scores}
                  selectedScenarioId={decision?.selected_scenario_id}
                />
              </div>
            </Panel>
          </Reveal>

          <div className="grid gap-6 xl:grid-cols-[0.9fr_1.1fr]">
            <Reveal>
              <Panel className="h-full p-6 sm:p-8">
                <SectionHeader
                  eyebrow="Agent mix"
                  title="Decision weight profile"
                  description="These weights shape how cost, risk, latency, and energy combine into the final placement outcome."
                  align="start"
                />
                <div className="mt-6 flex flex-wrap gap-3">
                  {Object.entries(weights).map(([agent, value]) => (
                    <span
                      key={agent}
                      className={`rounded-2xl border px-4 py-3 text-sm font-semibold ${
                        hasCustomWeights
                          ? 'border-amber-400/30 bg-amber-400/10 text-amber-100'
                          : 'border-white/10 bg-white/3 text-slate-200'
                      }`}
                    >
                      {agent.replace('Agent', '')} {Math.round(value * 100)}%
                    </span>
                  ))}
                </div>
                <div className="mt-8 rounded-3xl border border-white/10 bg-white/3 p-5 text-sm leading-7 text-slate-400">
                  {hasCustomWeights
                    ? 'Custom weighting is active for this workload, signalling that decision policy was adjusted for special operating priorities.'
                    : 'Default weights are active, keeping the decision profile stable and easy to compare across runs.'}
                </div>
              </Panel>
            </Reveal>

            <Reveal delay={0.08}>
              <Panel className={`p-6 sm:p-8 ${reasoningTone}`}>
                <div className="flex items-start justify-between gap-4">
                  <div>
                    <p className="text-xs uppercase tracking-[0.32em] text-slate-300">AI reasoning</p>
                    <h3 className="mt-3 text-2xl font-semibold text-white">Why this node won</h3>
                  </div>
                  <Sparkles size={18} className="text-sky-300" />
                </div>
                <p className="mt-5 text-lg leading-8 text-white/90">
                  {structuredReasoning.summary}
                </p>
                {structuredReasoning.whyThisNodeWon.length ? (
                  <div className="mt-5 rounded-2xl border border-white/10 bg-white/5 p-4">
                    <p className="text-xs uppercase tracking-[0.24em] text-slate-400">Why this node won</p>
                    <ul className="mt-3 list-disc space-y-2 pl-5 text-sm text-slate-100">
                      {structuredReasoning.whyThisNodeWon.map((line) => (
                        <li key={line}>{line}</li>
                      ))}
                    </ul>
                  </div>
                ) : null}
                {structuredReasoning.tradeoffs.length ? (
                  <div className="mt-4 rounded-2xl border border-white/10 bg-white/5 p-4">
                    <p className="text-xs uppercase tracking-[0.24em] text-slate-400">Tradeoffs</p>
                    <ul className="mt-3 list-disc space-y-2 pl-5 text-sm text-slate-100">
                      {structuredReasoning.tradeoffs.map((line) => (
                        <li key={line}>{line}</li>
                      ))}
                    </ul>
                  </div>
                ) : null}
                {selectedScenario ? (
                  <div className="mt-6 grid gap-3 sm:grid-cols-3">
                    <MiniFact icon={Zap} label="Latency" value={`${Number(selectedScenario.predicted_latency_ms).toFixed(2)} ms`} />
                    <MiniFact icon={ShieldCheck} label="Failure" value={`${(Number(selectedScenario.predicted_failure_prob) * 100).toFixed(2)}%`} />
                    <MiniFact icon={Coins} label="Cost" value={`$${Number(selectedScenario.estimated_cost_usd).toFixed(4)}`} />
                  </div>
                ) : null}
                {deploymentStatus ? (
                  <div className="mt-4 rounded-3xl border border-white/10 bg-white/3 p-4 text-sm text-slate-200">
                    <p className="text-xs uppercase tracking-[0.24em] text-slate-400">Deployment progress</p>
                    <p className="mt-2 font-semibold text-white">
                      {String(deploymentStatus.state || 'idle').replaceAll('_', ' ')}
                      {deploymentStatus.target ? ` · ${deploymentStatus.target}` : ''}
                    </p>
                    <p className="mt-1 text-slate-300">{deploymentStatus.message || 'No deployment activity yet.'}</p>
                    {deploymentStatus.run_url ? (
                      <a
                        className="mt-2 inline-block text-sky-300 hover:text-sky-200"
                        href={deploymentStatus.run_url}
                        target="_blank"
                        rel="noreferrer"
                      >
                        Open workflow run
                      </a>
                    ) : null}
                  </div>
                ) : null}
                {deployMessage ? <div className="mt-4"><PanelMessage tone="info">{deployMessage}</PanelMessage></div> : null}
                {workloadId ? (
                  <div className="mt-6 flex flex-wrap gap-3">
                    {['ready_for_deployment', 'delayed'].includes(String(workload?.status || '').toLowerCase()) ? (
                      <>
                        <button
                          className="control-button"
                          onClick={() => triggerDeployment('local')}
                          type="button"
                          disabled={Boolean(deployingTarget)}
                        >
                          {deployingTarget === 'local' ? 'Deploying to local...' : 'Deploy to Local K8s'}
                        </button>
                        <button
                          className="control-button"
                          onClick={() => triggerDeployment('staging')}
                          type="button"
                          disabled={Boolean(deployingTarget)}
                        >
                          {deployingTarget === 'staging' ? 'Triggering cloud deploy...' : 'Deploy to Cloud (Staging)'}
                        </button>
                      </>
                    ) : null}
                    {String(deploymentStatus?.state || '').toLowerCase() === 'failed' ? (
                      <button
                        className="control-button"
                        onClick={retryDeployment}
                        type="button"
                        disabled={Boolean(deployingTarget)}
                      >
                        {deployingTarget === 'retry' ? 'Retrying...' : 'Retry deployment'}
                      </button>
                    ) : null}
                    {['queued', 'starting', 'deploying', 'triggered'].includes(String(deploymentStatus?.state || '').toLowerCase()) ? (
                      <button
                        className="control-button"
                        onClick={cancelDeployment}
                        type="button"
                        disabled={Boolean(deployingTarget)}
                      >
                        {deployingTarget === 'cancel' ? 'Cancelling...' : 'Cancel deployment'}
                      </button>
                    ) : null}
                    <Link
                      className="control-button"
                      to="/preview"
                      state={{
                        previewPayload: {
                          name: workload?.name || 'decision-preview',
                          cpu_cores: Number(workload?.cpu_cores || 1),
                          memory_gb: Number(workload?.memory_gb || 1),
                          priority: Number(workload?.priority || 3),
                          policy: {
                            max_monthly_budget_usd: workload?.budget_usd ?? null,
                            max_failure_probability: workload?.failure_prob_sla ?? null,
                            max_latency_ms: workload?.latency_sla_ms ?? null,
                            allowed_clouds: ['aws', 'azure', 'gcp'],
                            allowed_regions: ['eu-west-1', 'westeurope', 'europe-west4'],
                          },
                          weights: {
                            cost: weights?.CostAgent ?? 0.3,
                            risk: weights?.RiskAgent ?? 0.35,
                            latency: weights?.LatencyAgent ?? 0.25,
                            energy: weights?.EnergyAgent ?? 0.1,
                          },
                        },
                      }}
                    >
                      Open preview control
                    </Link>
                    <Link className="control-button" to={`/evaluation/${workloadId}`}>Open model evaluation</Link>
                    <Link className="control-button" to={`/logs/${workloadId}`}>Open deployment logs</Link>
                  </div>
                ) : null}
              </Panel>
            </Reveal>
          </div>

          <Reveal>
            <Panel className="p-6 sm:p-8">
              <SectionHeader
                eyebrow="Simulation view"
                title="Monte Carlo confidence snapshot"
                description="The selected scenario is stress-tested with repeated perturbations so operators can see average latency, p95 latency, failure tendency, and SLA breach risk without leaving the decision workspace."
                align="start"
              />
              {simulation?.simulation ? (
                <div className="mt-6 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
                  <MiniFact icon={TimerReset} label="Latency mean" value={`${Number(simulation.simulation.latency_ms_mean).toFixed(2)} ms`} />
                  <MiniFact icon={Zap} label="Latency p95" value={`${Number(simulation.simulation.latency_ms_p95).toFixed(2)} ms`} />
                  <MiniFact icon={ShieldCheck} label="Failure mean" value={`${(Number(simulation.simulation.failure_prob_mean) * 100).toFixed(2)}%`} />
                  <MiniFact icon={BrainCircuit} label="SLA breach" value={`${(Number(simulation.simulation.sla_breach_rate) * 100).toFixed(2)}%`} />
                </div>
              ) : (
                <div className="mt-6 rounded-3xl border border-white/10 bg-white/3 p-5 text-sm text-slate-400">
                  {simulation?.available === false
                    ? simulation.reason || 'Simulation data is not available yet for this workload.'
                    : 'Simulation data is not available yet for this workload.'}
                </div>
              )}
            </Panel>
          </Reveal>

          <Reveal>
            <Panel className="p-6 sm:p-8">
              <SectionHeader
                eyebrow="Trade-off frontier"
                title="Cost versus risk context"
                description="The Pareto surface gives an executive view of how the selected scenario compares against the rest of the candidate set."
              />
              <div className="mt-6">
                <ParetoGraph scenarios={scenarios} selectedScenarioId={decision?.selected_scenario_id} />
              </div>
            </Panel>
          </Reveal>

          <Reveal>
            <Panel className="p-6 sm:p-8">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <SectionHeader
                  eyebrow="Prediction details"
                  title="Scenario deep dive"
                  description="Expand to inspect the predicted latency, failure, cost, and energy profile for each candidate node."
                  align="start"
                />
                <button className="control-button" onClick={() => setExpanded((current) => !current)} type="button">
                  {expanded ? 'Hide details' : 'Show details'}
                </button>
              </div>
              {expanded ? (
                <div className="mt-6 grid gap-6 lg:grid-cols-2">
                  {scenarios.map((scenario) => (
                    <motion.article
                      key={scenario.scenario_id}
                      className="rounded-[28px] border border-white/10 bg-white/3 p-5 text-sm text-slate-200"
                      whileHover={{ y: -4 }}
                    >
                      <div className="mb-4 flex items-center justify-between gap-4">
                        <div>
                          <h4 className="text-lg font-semibold text-white">{scenario.target_node}</h4>
                          <p className="text-xs text-slate-500">Scenario ID ending {scenario.scenario_id.slice(-10)}</p>
                        </div>
                        {scenario.scenario_id === decision?.selected_scenario_id ? <StatusBadge value="deployed" /> : null}
                      </div>
                      <ul className="space-y-3">
                        <li>Latency <strong className="ml-2 text-sky-300">{Number(scenario.predicted_latency_ms).toFixed(2)} ms</strong></li>
                        <li>Failure <strong className="ml-2 text-rose-300">{(Number(scenario.predicted_failure_prob) * 100).toFixed(2)}%</strong></li>
                        <li>Cost <strong className="ml-2 text-emerald-300">${Number(scenario.estimated_cost_usd).toFixed(4)}</strong></li>
                        <li>Energy <strong className="ml-2 text-amber-300">{Number(scenario.estimated_energy_kwh).toFixed(4)} kWh</strong></li>
                      </ul>
                      {workload ? (
                        <div className="mt-4 rounded-2xl border border-white/10 bg-slate-950/80 p-3 text-xs text-slate-400">
                          Inputs → cpu: {workload.cpu_cores}, memory: {workload.memory_gb}GB, SLA latency: {workload.latency_sla_ms}ms, failure SLA:{' '}
                          {(Number(workload.failure_prob_sla) * 100).toFixed(1)}%
                        </div>
                      ) : null}
                    </motion.article>
                  ))}
                </div>
              ) : null}
            </Panel>
          </Reveal>
        </div>
      ) : null}
    </section>
  );
}

function MiniFact({ icon: Icon, label, value }) {
  return (
    <div className="rounded-2xl border border-white/10 bg-white/3 p-4">
      <div className="flex items-center gap-2 text-xs uppercase tracking-[0.24em] text-slate-400">
        <Icon size={14} />
        {label}
      </div>
      <div className="mt-3 text-lg font-semibold text-white">{value}</div>
    </div>
  );
}

function getReasoningTone(workload, selectedScenario) {
  if (!workload || !selectedScenario) return 'border-slate-800 bg-slate-950/80';
  const latency = Number(selectedScenario.predicted_latency_ms);
  const risk = Number(selectedScenario.predicted_failure_prob);
  const latencyLimit = Number(workload.latency_sla_ms);
  const riskLimit = Number(workload.failure_prob_sla);
  if (risk <= riskLimit && latency <= latencyLimit) return 'border-emerald-500/40 bg-emerald-500/10';
  if (risk <= riskLimit * 1.1 && latency <= latencyLimit * 1.1) return 'border-amber-500/40 bg-amber-500/10';
  return 'border-rose-500/40 bg-rose-500/10';
}

function PanelMessage({ children, tone = 'info' }) {
  const toneClass =
    tone === 'error'
      ? 'border-rose-500/40 bg-rose-500/10 text-rose-100'
      : 'border-slate-700 bg-slate-900 text-slate-200';
  return (
    <div className={`rounded-3xl border px-5 py-4 text-sm ${toneClass}`}>
      {children}
    </div>
  );
}

function buildStructuredReasoning(decision) {
  const structured = decision?.reasoning_structured;
  if (structured && typeof structured === 'object') {
    return {
      summary: structured.summary || 'Decision reasoning is not available yet.',
      whyThisNodeWon: Array.isArray(structured.why_this_node_won) ? structured.why_this_node_won : [],
      tradeoffs: Array.isArray(structured.tradeoffs) ? structured.tradeoffs : [],
    };
  }

  const text = String(decision?.decision_reasoning || '').trim();
  if (!text) {
    return {
      summary: 'Decision reasoning is not available yet.',
      whyThisNodeWon: [],
      tradeoffs: [],
    };
  }

  const lines = text.split('\n').map((line) => line.trim()).filter(Boolean);
  const bulletLines = lines
    .filter((line) => line.startsWith('-'))
    .map((line) => line.replace(/^-\s*/, ''));

  return {
    summary: lines[0] || text,
    whyThisNodeWon: bulletLines,
    tradeoffs: [],
  };
}