import { useEffect, useMemo, useState } from 'react';
import { useParams } from 'react-router-dom';
import { Gauge, Sparkles, TrendingUp } from 'lucide-react';

import ParetoGraph from '../components/ParetoGraph';
import Panel from '../components/ui/Panel';
import Reveal from '../components/ui/Reveal';
import SectionHeader from '../components/ui/SectionHeader';
import { apiUrl } from '../config/api';
import { useWorkloadContext } from '../context/WorkloadContext';

export default function ParetoGraphPage() {
  const params = useParams();
  const workloadId = params.id ?? params.workload_id;
  const { setCurrentWorkloadId } = useWorkloadContext();
  const [scenarios, setScenarios] = useState([]);
  const [selectedScenarioId, setSelectedScenarioId] = useState(null);

  useEffect(() => {
    setCurrentWorkloadId(workloadId ?? null);
  }, [setCurrentWorkloadId, workloadId]);

  useEffect(() => {
    if (!workloadId) {
      return undefined;
    }

    let mounted = true;
    const load = async () => {
      try {
        const response = await fetch(apiUrl(`/results/${workloadId}/decision-panel`));
        if (!response.ok) {
          throw new Error(`Pareto data request failed: ${response.status}`);
        }
        const payload = await response.json();
        if (!mounted) {
          return;
        }
        setScenarios(Array.isArray(payload?.scenarios) ? payload.scenarios : []);
        setSelectedScenarioId(payload?.decision?.selected_scenario_id ?? null);
      } catch (error) {
        console.error(error);
      }
    };

    load();
    const intervalId = window.setInterval(load, 10000);
    return () => {
      mounted = false;
      window.clearInterval(intervalId);
    };
  }, [workloadId]);

  const chartData = useMemo(
    () =>
      scenarios.map((scenario) => ({
        ...scenario,
        x: Number(scenario.estimated_cost_usd),
        y: Number(scenario.predicted_failure_prob),
        selected: scenario.scenario_id === selectedScenarioId,
      })),
    [scenarios, selectedScenarioId],
  );

  const frontierData = useMemo(() => {
    const sorted = [...chartData].sort((left, right) => left.x - right.x);
    let minFailureSoFar = Number.POSITIVE_INFINITY;
    const nonDominated = [];
    for (const point of sorted) {
      if (point.y < minFailureSoFar) {
        nonDominated.push(point);
        minFailureSoFar = point.y;
      }
    }
    return nonDominated;
  }, [chartData]);

  return (
    <section className="mx-auto max-w-7xl space-y-6 px-1 py-2">
      <Reveal>
        <Panel className="p-8 sm:p-10">
          <SectionHeader
            eyebrow="Trade-off analytics"
            title="Pareto frontier explorer"
            description="Each point represents a persisted deployment scenario. The visualization helps explain why the chosen node sits on the best visible cost-risk envelope for the workload."
          />

          <div className="mt-8 grid gap-4 md:grid-cols-3">
            <MiniStat icon={Sparkles} label="Scenario count" value={chartData.length} />
            <MiniStat icon={TrendingUp} label="Pareto points" value={frontierData.length} />
            <MiniStat icon={Gauge} label="Selected scenario" value={selectedScenarioId ? 'active' : 'waiting'} />
          </div>
        </Panel>
      </Reveal>

      <Reveal delay={0.08}>
        <ParetoGraph scenarios={scenarios} selectedScenarioId={selectedScenarioId} />
      </Reveal>

      <Reveal delay={0.12}>
        <Panel className="p-6">
          <p className="text-sm leading-7 text-slate-400">
            The frontier highlights scenarios that remain non-dominated on cost and failure risk. This allows reviewers to see why a node was competitive
            without exposing the platform&apos;s deeper orchestration heuristics.
          </p>
        </Panel>
      </Reveal>
    </section>
  );
}

function MiniStat({ label, value, icon: Icon }) {
  return (
    <div className="rounded-[24px] border border-white/10 bg-white/[0.03] p-5">
      <div className="flex items-center gap-2 text-slate-500">
        <Icon size={15} />
        <span className="text-xs uppercase tracking-[0.28em]">{label}</span>
      </div>
      <div className="mt-4 text-2xl font-semibold text-white">{value}</div>
    </div>
  );
}
