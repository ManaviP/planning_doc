import { useMemo, useState } from 'react';
import { ArrowDownUp, BadgeCheck, ChevronDown } from 'lucide-react';

const COLUMN_CONFIG = {
  target_node: 'Node',
  predicted_latency_ms: 'Latency (ms)',
  predicted_failure_prob: 'Failure risk',
  estimated_cost_usd: 'Est. cost (USD)',
  cost: 'Cost score',
  risk: 'Risk score',
  latency: 'Latency score',
  energy: 'Energy score',
  final: 'Final score',
  selected: 'Selected',
};

const scoreColors = (score) => {
  if (score >= 70) {
    return 'bg-emerald-500/15 text-emerald-200';
  }
  if (score >= 40) {
    return 'bg-amber-500/15 text-amber-100';
  }
  return 'bg-rose-500/15 text-rose-100';
};

export default function ScenarioTable({ scenarios, scores, finalScores, selectedScenarioId }) {
  const [sortConfig, setSortConfig] = useState({ key: 'final', direction: 'desc' });

  const scoresByScenario = useMemo(() => {
    return scores.reduce((accumulator, score) => {
      accumulator[score.scenario_id] ??= {};
      accumulator[score.scenario_id][score.agent_name] = Number(score.raw_score ?? 0);
      return accumulator;
    }, {});
  }, [scores]);

  const sortedRows = useMemo(() => {
    const rows = scenarios.map((scenario) => ({
      scenario,
      costScore: scoresByScenario[scenario.scenario_id]?.CostAgent ?? 0,
      riskScore: scoresByScenario[scenario.scenario_id]?.RiskAgent ?? 0,
      latencyScore: scoresByScenario[scenario.scenario_id]?.LatencyAgent ?? 0,
      energyScore: scoresByScenario[scenario.scenario_id]?.EnergyAgent ?? 0,
      finalScore: Number(finalScores?.[scenario.scenario_id] ?? 0),
    }));

    rows.sort((left, right) => {
      const leftValue = getSortValue(left, sortConfig.key);
      const rightValue = getSortValue(right, sortConfig.key);
      const comparison = leftValue > rightValue ? 1 : leftValue < rightValue ? -1 : 0;
      return sortConfig.direction === 'asc' ? comparison : -comparison;
    });

    return rows;
  }, [finalScores, scenarios, scoresByScenario, sortConfig]);

  const toggleSort = (key) => {
    setSortConfig((current) => ({
      key,
      direction: current.key === key && current.direction === 'desc' ? 'asc' : 'desc',
    }));
  };

  return (
    <div className="overflow-hidden rounded-[28px] border border-white/10 bg-slate-950/70 shadow-[0_24px_80px_rgba(2,6,23,0.45)]">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-white/10 px-5 py-4">
        <div>
          <p className="text-xs uppercase tracking-[0.3em] text-slate-500">Scenario ranking</p>
          <p className="mt-1 text-sm text-slate-300">Interactive comparison of candidate nodes and weighted agent outcomes.</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <div className="inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/4 px-3 py-2 text-xs text-slate-400">
            <ArrowDownUp size={14} />
            Sort any column
          </div>
          <div className="inline-flex items-center rounded-full border border-sky-400/20 bg-sky-400/10 px-3 py-2 text-xs font-semibold text-sky-200">
            {sortedRows.length} scenario{sortedRows.length === 1 ? '' : 's'}
          </div>
        </div>
      </div>
      {!sortedRows.length ? (
        <div className="px-5 py-10 text-center text-sm text-slate-400">
          No scenario rows are available yet. Submit a workload or wait for the decision pipeline to finish.
        </div>
      ) : null}
      <div className="overflow-x-auto">
        <table className="min-w-full border-collapse text-sm text-slate-100">
          <thead className="bg-slate-900/70 text-left text-[11px] uppercase tracking-[0.24em] text-slate-500">
            <tr>
              {Object.entries(COLUMN_CONFIG).map(([key, label]) => (
                <th key={key} className="px-4 py-4">
                  <button className="inline-flex items-center gap-1.5 transition hover:text-white" onClick={() => toggleSort(key)} type="button">
                    <span>{label}</span>
                    {sortConfig.key === key ? <ChevronDown className={`${sortConfig.direction === 'asc' ? 'rotate-180' : ''} transition`} size={14} /> : null}
                  </button>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {sortedRows.map(({ scenario, costScore, riskScore, latencyScore, energyScore, finalScore }) => {
              const isSelected = scenario.scenario_id === selectedScenarioId;
              return (
                <tr
                  key={scenario.scenario_id}
                  className={`border-t border-white/5 transition ${isSelected ? 'bg-sky-400/10' : 'bg-slate-950/30 hover:bg-white/3'}`}
                >
                  <td className="px-4 py-4 font-medium text-white">
                    <div className="flex items-center gap-3">
                      <span className="flex h-10 w-10 items-center justify-center rounded-2xl border border-white/10 bg-white/4 text-sky-200">
                        {scenario.target_node.slice(0, 2).toUpperCase()}
                      </span>
                      <div>
                        <p className="font-semibold text-white">{scenario.target_node}</p>
                        <p className="text-xs text-slate-500">{scenario.scenario_id.slice(-12)}</p>
                      </div>
                    </div>
                  </td>
                  <td className="px-4 py-4 text-slate-200">{Number(scenario.predicted_latency_ms).toFixed(2)}</td>
                  <td className="px-4 py-4 text-slate-200">{(Number(scenario.predicted_failure_prob) * 100).toFixed(2)}%</td>
                  <td className="px-4 py-4 text-slate-200">${Number(scenario.estimated_cost_usd).toFixed(4)}</td>
                  <td className="px-4 py-4"><span className={`inline-flex rounded-full px-3 py-1 text-xs font-semibold ${scoreColors(costScore)}`}>{costScore.toFixed(2)}</span></td>
                  <td className="px-4 py-4"><span className={`inline-flex rounded-full px-3 py-1 text-xs font-semibold ${scoreColors(riskScore)}`}>{riskScore.toFixed(2)}</span></td>
                  <td className="px-4 py-4"><span className={`inline-flex rounded-full px-3 py-1 text-xs font-semibold ${scoreColors(latencyScore)}`}>{latencyScore.toFixed(2)}</span></td>
                  <td className="px-4 py-4"><span className={`inline-flex rounded-full px-3 py-1 text-xs font-semibold ${scoreColors(energyScore)}`}>{energyScore.toFixed(2)}</span></td>
                  <td className={`px-4 py-4 ${isSelected ? 'font-bold text-sky-200' : 'text-white'}`}>{finalScore.toFixed(2)}</td>
                  <td className="px-4 py-4 text-center text-lg text-sky-200">{isSelected ? <BadgeCheck className="mx-auto" size={18} /> : '—'}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function getSortValue(row, key) {
  switch (key) {
    case 'target_node':
      return row.scenario.target_node;
    case 'predicted_latency_ms':
      return Number(row.scenario.predicted_latency_ms);
    case 'predicted_failure_prob':
      return Number(row.scenario.predicted_failure_prob);
    case 'estimated_cost_usd':
      return Number(row.scenario.estimated_cost_usd);
    case 'cost':
      return row.costScore;
    case 'risk':
      return row.riskScore;
    case 'latency':
      return row.latencyScore;
    case 'energy':
      return row.energyScore;
    case 'final':
      return row.finalScore;
    case 'selected':
      return row.scenario.scenario_id;
    default:
      return row.finalScore;
  }
}
