import { useEffect, useMemo, useState } from 'react';
import { motion } from 'framer-motion';
import { ActivitySquare, Boxes, Cpu, MemoryStick, Shield } from 'lucide-react';

import Panel from '../components/ui/Panel';
import Reveal from '../components/ui/Reveal';
import SectionHeader from '../components/ui/SectionHeader';
import StatusBadge from '../components/ui/StatusBadge';
import { useWorkloadContext } from '../context/WorkloadContext';

function riskTone(probability) {
  if (probability == null) {
    return 'bg-slate-800 text-slate-300';
  }
  const pct = probability * 100;
  if (pct < 15) {
    return 'bg-emerald-500/15 text-emerald-200';
  }
  if (pct < 35) {
    return 'bg-amber-500/15 text-amber-100';
  }
  return 'bg-rose-500/15 text-rose-100';
}

function healthBorder(node, isSelected) {
  if (isSelected) {
    return 'border-2 border-sky-500';
  }
  const cpu = Number(node.cpu_usage_pct || 0);
  const memory = Number(node.memory_usage_pct || 0);
  if (cpu > 80 || memory > 85) {
    return 'border border-rose-500';
  }
  if ((cpu >= 60 && cpu <= 80) || (memory >= 70 && memory <= 85)) {
    return 'border border-amber-500';
  }
  return 'border border-emerald-500';
}

function barColor(value) {
  if (value < 60) return '#639922';
  if (value < 80) return '#BA7517';
  return '#A32D2D';
}

export default function ClusterOverview() {
  const { clusterNodes, latestDecision, wsEvents, currentWorkloadId } = useWorkloadContext();
  const [highlightedNode, setHighlightedNode] = useState(null);

  useEffect(() => {
    const newestEvent = wsEvents[0];
    if (!newestEvent || newestEvent.event_type !== 'DEPLOYMENT_SUCCESS') {
      return undefined;
    }
    if (newestEvent.workload_id !== currentWorkloadId) {
      return undefined;
    }
    const nodeName = newestEvent.payload?.node;
    setHighlightedNode(nodeName);
    const timeoutId = window.setTimeout(() => setHighlightedNode(null), 3000);
    return () => window.clearTimeout(timeoutId);
  }, [currentWorkloadId, wsEvents]);

  const scenarioMap = useMemo(() => {
    return (latestDecision?.all_scenarios ?? []).reduce((accumulator, scenario) => {
      accumulator[scenario.target_node] = scenario;
      return accumulator;
    }, {});
  }, [latestDecision]);

  const aggregate = useMemo(() => {
    const total = clusterNodes.length;
    const available = clusterNodes.filter((node) => node.available).length;
    const avgCpu = total ? clusterNodes.reduce((sum, node) => sum + Number(node.cpu_usage_pct || 0), 0) / total : 0;
    const avgMemory = total
      ? clusterNodes.reduce((sum, node) => sum + Number(node.memory_usage_pct || 0), 0) / total
      : 0;

    return { total, available, avgCpu, avgMemory };
  }, [clusterNodes]);

  return (
    <section className="mx-auto max-w-7xl space-y-8 px-1 py-2">
      <Reveal>
        <Panel className="p-8 sm:p-10">
          <SectionHeader
            eyebrow="Cluster observability"
            title="Infrastructure posture at a glance"
            description="Live node health comes from FastAPI metrics, while decision overlays pull from the latest negotiated allocation. The result is a concise operations narrative instead of disconnected charts."
          />
          <div className="mt-8 grid gap-4 md:grid-cols-4">
            <OverviewStat icon={Boxes} label="Nodes in fleet" value={aggregate.total} />
            <OverviewStat icon={Shield} label="Schedulable" value={aggregate.available} />
            <OverviewStat icon={Cpu} label="Average CPU" value={`${aggregate.avgCpu.toFixed(1)}%`} />
            <OverviewStat icon={MemoryStick} label="Average memory" value={`${aggregate.avgMemory.toFixed(1)}%`} />
          </div>
        </Panel>
      </Reveal>

      <div className="grid gap-6 md:grid-cols-2">
        {clusterNodes.map((node) => {
          const scenario = scenarioMap[node.node_name];
          const isSelected = latestDecision?.selected_scenario_id === scenario?.scenario_id;
          const isAnimated = highlightedNode === node.node_name && isSelected;
          return (
            <motion.article
              key={node.node_name}
              className={`rounded-[28px] bg-slate-950/80 p-6 shadow-[0_24px_80px_rgba(2,6,23,0.42)] ${healthBorder(node, isSelected)} ${isAnimated ? 'puls-ring' : ''}`}
              whileHover={{ y: -6, rotateX: 2, rotateY: -2 }}
            >
              <div className="mb-4 flex items-start justify-between gap-4">
                <div>
                  <div className="flex items-center gap-3">
                    <div className="flex h-12 w-12 items-center justify-center rounded-2xl border border-white/10 bg-white/[0.05] text-sky-200">
                      <ActivitySquare size={20} />
                    </div>
                    <div>
                      <h3 className="text-base font-bold text-white">{node.node_name}</h3>
                      <p className="mt-1 text-sm text-slate-400">Pods scheduled: {node.pod_count}</p>
                    </div>
                  </div>
                </div>
                <div className="flex flex-col items-end gap-2">
                  <StatusBadge value={node.available ? 'available' : 'unavailable'} className="px-3 py-1" />
                  {isSelected ? <StatusBadge value="active" className="px-3 py-1" /> : null}
                </div>
              </div>

              <MetricBar label="CPU" value={Number(node.cpu_usage_pct || 0)} />
              <MetricBar label="Memory" value={Number(node.memory_usage_pct || 0)} />

              <div className="mt-5 flex flex-wrap gap-3 text-sm">
                <span className={`rounded-full px-3 py-1 font-medium ${riskTone(scenario?.predicted_failure_prob)}`}>
                  Risk: {scenario ? `${(Number(scenario.predicted_failure_prob) * 100).toFixed(1)}%` : '—'}
                </span>
                {scenario ? (
                  <span className="rounded-full bg-slate-800 px-3 py-1 text-slate-200">
                    Latency: {Number(scenario.predicted_latency_ms).toFixed(1)} ms
                  </span>
                ) : null}
              </div>
            </motion.article>
          );
        })}
      </div>
    </section>
  );
}

function OverviewStat({ icon: Icon, label, value }) {
  return (
    <div className="rounded-[24px] border border-white/10 bg-white/[0.03] p-5">
      <div className="flex items-center gap-3 text-slate-400">
        <Icon size={16} />
        <span className="text-xs uppercase tracking-[0.28em]">{label}</span>
      </div>
      <p className="mt-4 text-3xl font-semibold text-white">{value}</p>
    </div>
  );
}

function MetricBar({ label, value }) {
  return (
    <div className="mt-4">
      <div className="mb-2 flex items-center justify-between text-sm text-slate-200">
        <span>{label}</span>
        <span>{value.toFixed(1)}%</span>
      </div>
      <div className="h-1.5 overflow-hidden rounded-full bg-slate-800">
        <div className="h-full rounded-full transition-all" style={{ width: `${Math.min(value, 100)}%`, backgroundColor: barColor(value) }} />
      </div>
    </div>
  );
}
