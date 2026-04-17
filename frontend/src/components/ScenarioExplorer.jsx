import { useMemo, useState } from 'react';
import { SlidersHorizontal } from 'lucide-react';

import { useWorkloadContext } from '../context/WorkloadContext';
import Panel from './ui/Panel';
import SectionHeader from './ui/SectionHeader';
import StatusBadge from './ui/StatusBadge';

function dominates(a, b) {
  const av = [a.estimated_cost_usd, a.predicted_latency_ms, a.predicted_failure_prob, a.estimated_energy_kwh];
  const bv = [b.estimated_cost_usd, b.predicted_latency_ms, b.predicted_failure_prob, b.estimated_energy_kwh];
  return av.every((x, i) => x <= bv[i]) && av.some((x, i) => x < bv[i]);
}

function paretoFront(scenarios) {
  return scenarios.filter((candidate) => !scenarios.some((other) => other.scenario_id !== candidate.scenario_id && dominates(other, candidate)));
}

function clamp(v, min, max) {
  return Math.max(min, Math.min(max, v));
}

export default function ScenarioExplorer() {
  const { latestDecision, currentWorkloadId } = useWorkloadContext();
  const scenarios = latestDecision?.all_scenarios ?? [];

  const [budgetUsd, setBudgetUsd] = useState(1.0);
  const [latencySla, setLatencySla] = useState(800);
  const [riskTolerance, setRiskTolerance] = useState('medium');
  const [energyPreference, setEnergyPreference] = useState('any');
  const [disabledNodes, setDisabledNodes] = useState([]);

  const visibleScenarios = useMemo(() => {
    return scenarios.filter((s) => !disabledNodes.includes(s.target_node));
  }, [scenarios, disabledNodes]);

  const recomputed = useMemo(() => {
    if (!visibleScenarios.length) {
      return { ranked: [], pareto: [], selected: null };
    }

    const weights = {
      cost: budgetUsd > 0 ? 0.35 : 0.25,
      risk: riskTolerance === 'low' ? 0.4 : riskTolerance === 'high' ? 0.2 : 0.3,
      latency: latencySla < 700 ? 0.3 : 0.2,
      energy: energyPreference === 'efficient' ? 0.2 : 0.1,
    };
    const total = Object.values(weights).reduce((a, b) => a + b, 0);
    Object.keys(weights).forEach((k) => {
      weights[k] = weights[k] / total;
    });

    const maxCost = Math.max(...visibleScenarios.map((s) => Number(s.estimated_cost_usd || 0)), 1);
    const maxEnergy = Math.max(...visibleScenarios.map((s) => Number(s.estimated_energy_kwh || 0)), 1);

    const ranked = visibleScenarios.map((s) => {
      const costScore = 100 - (Number(s.estimated_cost_usd || 0) / maxCost) * 100;
      const riskScore = 100 - Number(s.predicted_failure_prob || 0) * 100;
      const latencyScore = 100 - Math.min(Number(s.predicted_latency_ms || 0) / Math.max(latencySla, 1), 1) * 100;
      const energyScore = 100 - (Number(s.estimated_energy_kwh || 0) / maxEnergy) * 100;
      const budgetPenalty = budgetUsd > 0 && Number(s.estimated_cost_usd || 0) > budgetUsd ? 12 : 0;

      const final =
        costScore * weights.cost +
        riskScore * weights.risk +
        latencyScore * weights.latency +
        energyScore * weights.energy -
        budgetPenalty;

      return {
        ...s,
        score: Number(clamp(final, 0, 100).toFixed(3)),
      };
    });

    const pareto = paretoFront(ranked);
    const selected = [...pareto].sort((a, b) => b.score - a.score)[0] ?? null;

    return {
      ranked: ranked.sort((a, b) => b.score - a.score),
      pareto,
      selected,
    };
  }, [visibleScenarios, budgetUsd, latencySla, riskTolerance, energyPreference]);

  if (!currentWorkloadId || !scenarios.length) {
    return (
      <Panel className="p-7">
        <SectionHeader
          eyebrow="What-if explorer"
          title="Interactive scenario explorer"
          description="Submit a workload first to unlock interactive what-if recomputation for budget, SLA, risk, energy, and node availability."
          align="start"
        />
      </Panel>
    );
  }

  const allNodes = [...new Set(scenarios.map((s) => s.target_node))];

  const toggleNode = (node) => {
    setDisabledNodes((prev) => (prev.includes(node) ? prev.filter((n) => n !== node) : [...prev, node]));
  };

  return (
    <Panel className="p-7">
      <div className="flex items-center justify-between gap-4">
        <SectionHeader
          eyebrow="What-if explorer"
          title="Realtime simulation panel"
          description="Tune policy knobs and instantly recompute scenario ranking, Pareto candidates, and final selection without changing backend state."
          align="start"
        />
        <div className="flex h-10 w-10 items-center justify-center rounded-xl border border-white/10 bg-white/5 text-sky-200">
          <SlidersHorizontal size={18} />
        </div>
      </div>

      <div className="mt-5 grid gap-4 md:grid-cols-2 xl:grid-cols-5">
        <Control label="Budget (USD/hr)">
          <input type="number" step="0.1" min="0" value={budgetUsd} onChange={(e) => setBudgetUsd(Number(e.target.value || 0))} className="input-field" />
        </Control>
        <Control label="Latency SLA (ms)">
          <input type="number" min="50" value={latencySla} onChange={(e) => setLatencySla(Number(e.target.value || 50))} className="input-field" />
        </Control>
        <Control label="Risk tolerance">
          <select className="input-field" value={riskTolerance} onChange={(e) => setRiskTolerance(e.target.value)}>
            <option value="low">low</option>
            <option value="medium">medium</option>
            <option value="high">high</option>
          </select>
        </Control>
        <Control label="Energy preference">
          <select className="input-field" value={energyPreference} onChange={(e) => setEnergyPreference(e.target.value)}>
            <option value="any">any</option>
            <option value="balanced">balanced</option>
            <option value="efficient">efficient</option>
          </select>
        </Control>
        <Control label="Pareto candidates">
          <div className="mt-2 text-2xl font-semibold text-white">{recomputed.pareto.length}</div>
        </Control>
      </div>

      <div className="mt-5 flex flex-wrap gap-2">
        {allNodes.map((node) => {
          const disabled = disabledNodes.includes(node);
          return (
            <button
              key={node}
              type="button"
              onClick={() => toggleNode(node)}
              className={`rounded-full border px-3 py-1.5 text-xs ${disabled ? 'border-rose-400/40 bg-rose-400/10 text-rose-200' : 'border-emerald-400/30 bg-emerald-400/10 text-emerald-200'}`}
            >
              {node} {disabled ? '(disabled)' : '(active)'}
            </button>
          );
        })}
      </div>

      <div className="mt-6 overflow-x-auto rounded-2xl border border-white/10">
        <table className="min-w-full text-sm">
          <thead className="bg-white/5 text-slate-300">
            <tr>
              <th className="px-4 py-3 text-left">Scenario</th>
              <th className="px-4 py-3 text-left">Node</th>
              <th className="px-4 py-3 text-left">Score</th>
              <th className="px-4 py-3 text-left">Latency</th>
              <th className="px-4 py-3 text-left">Failure</th>
              <th className="px-4 py-3 text-left">Cost</th>
              <th className="px-4 py-3 text-left">Energy</th>
              <th className="px-4 py-3 text-left">Pareto</th>
            </tr>
          </thead>
          <tbody>
            {recomputed.ranked.map((row) => {
              const isPareto = recomputed.pareto.some((p) => p.scenario_id === row.scenario_id);
              const isSelected = recomputed.selected?.scenario_id === row.scenario_id;
              return (
                <tr key={row.scenario_id} className="border-t border-white/10 text-slate-200">
                  <td className="px-4 py-3 font-mono text-xs text-slate-300">{row.scenario_id}</td>
                  <td className="px-4 py-3">{row.target_node}</td>
                  <td className="px-4 py-3 font-semibold text-white">{row.score.toFixed(2)}</td>
                  <td className="px-4 py-3">{Number(row.predicted_latency_ms).toFixed(1)} ms</td>
                  <td className="px-4 py-3">{(Number(row.predicted_failure_prob) * 100).toFixed(1)}%</td>
                  <td className="px-4 py-3">${Number(row.estimated_cost_usd).toFixed(4)}</td>
                  <td className="px-4 py-3">{Number(row.estimated_energy_kwh).toFixed(4)} kWh</td>
                  <td className="px-4 py-3">
                    {isSelected ? <StatusBadge value="active" className="mr-2" /> : null}
                    {isPareto ? <StatusBadge value="available" /> : <StatusBadge value="unavailable" />}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </Panel>
  );
}

function Control({ label, children }) {
  return (
    <div className="rounded-2xl border border-white/10 bg-white/4 p-4">
      <p className="text-[11px] uppercase tracking-[0.24em] text-slate-400">{label}</p>
      <div className="mt-2">{children}</div>
    </div>
  );
}
