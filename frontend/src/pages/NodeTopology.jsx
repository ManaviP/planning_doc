import { useEffect, useMemo, useState } from 'react';
import { Background, Controls, Handle, Position, ReactFlow } from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import { motion } from 'framer-motion';
import { Aperture, Cpu, MemoryStick, ShieldAlert, X } from 'lucide-react';

import Panel from '../components/ui/Panel';
import Reveal from '../components/ui/Reveal';
import SectionHeader from '../components/ui/SectionHeader';
import StatusBadge from '../components/ui/StatusBadge';
import { useWorkloadContext } from '../context/WorkloadContext';

function TopologyNode({ data }) {
  const { metric, scenario, selected, animated } = data;
  const risk = scenario ? Number(scenario.predicted_failure_prob) * 100 : null;
  return (
    <motion.div
      className={`w-[280px] rounded-[28px] bg-slate-950/90 p-5 text-sm text-slate-100 ${selected ? 'border-2 border-sky-500' : 'border border-white/10'} ${animated ? 'puls-ring' : ''}`}
      title={`CPU ${Number(metric.cpu_usage_pct).toFixed(1)}% | Memory ${Number(metric.memory_usage_pct).toFixed(1)}% | Risk ${risk == null ? '—' : `${risk.toFixed(1)}%`} | Latency ${scenario ? `${Number(scenario.predicted_latency_ms).toFixed(1)}ms` : '—'}`}
      style={{
          boxShadow: `0 0 30px ${color(metric.cpu_usage_pct)}33, inset 0 0 20px ${color(metric.cpu_usage_pct)}1A`,
          borderColor: selected ? '#0ea5e9' : `${color(metric.cpu_usage_pct)}99`
      }}
      whileHover={{ y: -4, rotateX: 2, rotateY: -2 }}
    >
      <Handle position={Position.Left} type="target" style={{ opacity: 0 }} />
      <div className="mb-3 flex items-start justify-between gap-3">
        <div>
          <div className="flex items-center gap-3">
            <div className="flex h-11 w-11 items-center justify-center rounded-2xl border border-white/10 bg-white/[0.05] text-sky-200">
              <Aperture size={18} />
            </div>
            <div>
              <h3 className="text-[15px] font-bold text-white">{metric.node_name}</h3>
              <p className="text-xs text-slate-400">Pods: {metric.pod_count}</p>
            </div>
          </div>
        </div>
        <StatusBadge value={metric.available ? 'available' : 'unavailable'} className="px-3 py-1" />
      </div>
      <Bar label="CPU" value={Number(metric.cpu_usage_pct)} />
      <Bar label="Memory" value={Number(metric.memory_usage_pct)} />
      <div className="mt-3 flex flex-wrap gap-2 text-xs">
        <span className="rounded-full bg-slate-800 px-3 py-1 text-slate-200">Risk: {risk == null ? '—' : `${risk.toFixed(1)}%`}</span>
        <span className="rounded-full bg-slate-800 px-3 py-1 text-slate-200">Latency: {scenario ? `${Number(scenario.predicted_latency_ms).toFixed(1)} ms` : '—'}</span>
      </div>
      <Handle position={Position.Right} type="source" style={{ opacity: 0 }} />
    </motion.div>
  );
}

function color(value) {
  if (value < 60) return '#639922';
  if (value < 80) return '#BA7517';
  return '#A32D2D';
}

function Bar({ label, value }) {
  return (
    <div className="mt-3">
      <div className="mb-1 flex justify-between text-xs text-slate-300">
        <span>{label}</span>
        <span>{value.toFixed(1)}%</span>
      </div>
      <div className="h-1.5 rounded-full bg-slate-800">
        <div className="h-full rounded-full" style={{ width: `${Math.min(value, 100)}%`, backgroundColor: color(value) }} />
      </div>
    </div>
  );
}

const nodeTypes = { clusterNode: TopologyNode };

export default function NodeTopology() {
  const { clusterNodes, latestDecision, wsEvents, currentWorkloadId } = useWorkloadContext();
  const [selectedNode, setSelectedNode] = useState(null);
  const [animatedNode, setAnimatedNode] = useState(null);
  const [pulseEdge, setPulseEdge] = useState([]);

  const scenarioMap = useMemo(() => {
    return (latestDecision?.all_scenarios ?? []).reduce((accumulator, scenario) => {
      accumulator[scenario.target_node] = scenario;
      return accumulator;
    }, {});
  }, [latestDecision]);

  useEffect(() => {
    const newestEvent = wsEvents[0];
    if (!newestEvent || newestEvent.event_type !== 'DEPLOYMENT_SUCCESS' || newestEvent.workload_id !== currentWorkloadId) {
      return undefined;
    }
    const targetNode = newestEvent.payload?.node;
    setAnimatedNode(targetNode);
    setPulseEdge([
      {
        id: `pulse-${targetNode}`,
        source: 'center-anchor',
        target: targetNode,
        animated: true,
        style: { stroke: '#378ADD', strokeDasharray: '5 5' },
      },
    ]);
    const animationTimeout = window.setTimeout(() => setAnimatedNode(null), 3000);
    const edgeTimeout = window.setTimeout(() => setPulseEdge([]), 2500);
    return () => {
      window.clearTimeout(animationTimeout);
      window.clearTimeout(edgeTimeout);
    };
  }, [currentWorkloadId, wsEvents]);

  const nodes = useMemo(() => {
    const spacing = 320;
    const startX = 120;
    const y = 220;
    const flowNodes = clusterNodes.map((metric, index) => ({
      id: metric.node_name,
      type: 'clusterNode',
      position: { x: startX + index * spacing, y },
      data: {
        metric,
        scenario: scenarioMap[metric.node_name],
        selected: latestDecision?.selected_scenario_id === scenarioMap[metric.node_name]?.scenario_id,
        animated: animatedNode === metric.node_name,
      },
    }));

    flowNodes.unshift({
      id: 'center-anchor',
      type: 'input',
      position: { x: startX + ((Math.max(clusterNodes.length, 1) - 1) * spacing) / 2, y: 30 },
      data: { label: '' },
      hidden: true,
      selectable: false,
      draggable: false,
    });

    return flowNodes;
  }, [animatedNode, clusterNodes, latestDecision?.selected_scenario_id, scenarioMap]);

  const selectedMetric = clusterNodes.find((node) => node.node_name === selectedNode) ?? null;
  const selectedScenario = selectedMetric ? scenarioMap[selectedMetric.node_name] : null;

  return (
    <section className="relative mx-auto space-y-6 px-1 py-2">
      <Reveal>
        <Panel className="p-8 sm:p-10">
          <SectionHeader
            eyebrow="Infrastructure graph"
            title="Node topology with runtime overlays"
            description="Use the visual graph to inspect how fleet health, scenario risk, and deployment success map across the cluster. The side drawer surfaces detailed node context without disrupting the canvas."
          />
        </Panel>
      </Reveal>

      <div className="relative mx-auto flex max-w-[1400px] gap-6">
        <div className="h-[680px] flex-1 overflow-hidden rounded-[32px] border border-white/10 bg-slate-950/70 shadow-[0_24px_80px_rgba(2,6,23,0.42)]">
          <ReactFlow
            edges={pulseEdge}
            fitView
            nodeTypes={nodeTypes}
            nodes={nodes}
            onNodeClick={(_, node) => {
              if (node.id !== 'center-anchor') {
                setSelectedNode(node.id);
              }
            }}
            proOptions={{ hideAttribution: true }}
          >
            <Background color="#132034" gap={20} />
            <Controls />
          </ReactFlow>
        </div>

        <aside
          className={`fixed right-0 top-[96px] z-20 h-[calc(100vh-96px)] w-[320px] border-l border-white/10 bg-slate-950/95 p-5 shadow-2xl shadow-slate-950 transition-transform duration-200 ease-in-out ${selectedMetric ? 'translate-x-0' : 'translate-x-full'}`}
        >
        {selectedMetric ? (
          <>
            <div className="mb-4 flex items-start justify-between gap-3">
              <div>
                <h3 className="text-xl font-semibold text-white">{selectedMetric.node_name}</h3>
                <p className="text-sm text-slate-400">Realtime node telemetry</p>
              </div>
              <button className="rounded-full border border-white/10 px-3 py-2 text-sm text-slate-200 hover:border-sky-500" onClick={() => setSelectedNode(null)} type="button">
                <X size={15} />
              </button>
            </div>

            <dl className="space-y-3 text-sm text-slate-200">
              <Metric icon={Cpu} label="CPU usage" value={`${Number(selectedMetric.cpu_usage_pct).toFixed(1)}%`} />
              <Metric icon={MemoryStick} label="Memory usage" value={`${Number(selectedMetric.memory_usage_pct).toFixed(1)}%`} />
              <Metric label="GPU usage" value={selectedMetric.gpu_usage_pct == null ? '—' : `${Number(selectedMetric.gpu_usage_pct).toFixed(1)}%`} />
              <Metric label="Pod count" value={selectedMetric.pod_count} />
              <Metric label="Available" value={selectedMetric.available ? 'true' : 'false'} />
              <Metric label="Collected at" value={selectedMetric.collected_at} />
            </dl>

            <div className="mt-6 rounded-[24px] border border-white/10 bg-white/[0.03] p-4">
              <h4 className="mb-3 text-sm font-semibold uppercase tracking-wide text-sky-300">Predicted values</h4>
              {selectedScenario ? (
                <dl className="space-y-2 text-sm text-slate-200">
                  <Metric label="Predicted latency" value={`${Number(selectedScenario.predicted_latency_ms).toFixed(2)} ms`} />
                  <Metric label="Failure probability" value={`${(Number(selectedScenario.predicted_failure_prob) * 100).toFixed(2)}%`} />
                  <Metric label="Estimated cost" value={`$${Number(selectedScenario.estimated_cost_usd).toFixed(4)}`} />
                  <Metric label="Estimated energy" value={`${Number(selectedScenario.estimated_energy_kwh).toFixed(4)} kWh`} />
                </dl>
              ) : (
                <p className="text-sm text-slate-400">No decision scenario is available for this node.</p>
              )}
            </div>
          </>
        ) : null}
        </aside>
      </div>
    </section>
  );
}

function Metric({ label, value, icon: Icon }) {
  return (
    <div className="flex items-center justify-between gap-3">
      <dt className="flex items-center gap-2 text-slate-400">{Icon ? <Icon size={14} /> : <ShieldAlert size={14} />} {label}</dt>
      <dd className="text-right text-white">{value}</dd>
    </div>
  );
}
