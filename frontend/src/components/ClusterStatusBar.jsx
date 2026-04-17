import { useEffect, useMemo, useState } from 'react';
import { Activity, Boxes, Cpu, Layers3, MemoryStick } from 'lucide-react';

import { useWorkloadContext } from '../context/WorkloadContext';
import StatusBadge from './ui/StatusBadge';

const REFRESH_INTERVAL_MS = 10000;
const API_BASE_URL = 'http://localhost:8000';
const REQUEST_TIMEOUT_MS = 8000;

export default function ClusterStatusBar() {
  const { clusterNodes, wsStatus } = useWorkloadContext();
  const [activeWorkloadCount, setActiveWorkloadCount] = useState(0);

  useEffect(() => {
    let mounted = true;

    const fetchActiveWorkloads = async () => {
      const controller = new AbortController();
      const timeout = window.setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
      try {
        const response = await fetch(`${API_BASE_URL}/results/stats/active-workloads`, {
          signal: controller.signal,
        });
        if (response.ok) {
          const data = await response.json();
          if (mounted) {
            setActiveWorkloadCount(data.count ?? 0);
          }
        }
      } catch (error) {
        console.error('Failed to fetch active workload count', error);
      } finally {
        window.clearTimeout(timeout);
      }
    };

    fetchActiveWorkloads();
    const intervalId = window.setInterval(fetchActiveWorkloads, REFRESH_INTERVAL_MS);

    return () => {
      mounted = false;
      window.clearInterval(intervalId);
    };
  }, []);

  const metrics = useMemo(() => {
    const total = clusterNodes.length;
    const available = clusterNodes.filter((node) => node.available).length;
    const averageCpu = total
      ? clusterNodes.reduce((sum, node) => sum + Number(node.cpu_usage_pct || 0), 0) / total
      : 0;
    const averageMemory = total
      ? clusterNodes.reduce((sum, node) => sum + Number(node.memory_usage_pct || 0), 0) / total
      : 0;

    return {
      total,
      available,
      averageCpu: averageCpu.toFixed(1),
      averageMemory: averageMemory.toFixed(1),
    };
  }, [clusterNodes]);

  const indicatorTone = wsStatus === 'connected' ? 'bg-emerald-400 live-dot' : wsStatus === 'connecting' ? 'bg-sky-400 live-dot' : 'bg-slate-500';
  const streamLabel = wsStatus === 'idle' ? 'standby' : wsStatus;

  return (
    <header className="relative mb-6 overflow-hidden rounded-[28px] border border-white/10 bg-slate-950/80 px-4 py-4 shadow-[0_20px_60px_rgba(2,6,23,0.42)] backdrop-blur-2xl sm:px-5">
      <div className="absolute inset-0 hidden bg-[radial-gradient(circle_at_top_right,rgba(56,189,248,0.1),transparent_35%)] md:block" />
      <div className="relative flex flex-wrap items-center justify-between gap-4">
        <div>
          <p className="text-[11px] uppercase tracking-[0.32em] text-sky-300/80">Live cluster status</p>
          <h2 className="mt-1 text-lg font-semibold text-white">Realtime compute telemetry</h2>
          <p className="mt-1 text-sm text-slate-400">Fleet posture, active demand, and workload event streaming.</p>
        </div>

        <div className="grid flex-1 grid-cols-2 gap-3 text-sm text-slate-200 xl:grid-cols-5">
          <StatusItem icon={Boxes} label="Nodes" value={metrics.total} />
          <StatusItem icon={Layers3} label="Available" value={metrics.available} />
          <StatusItem icon={Cpu} label="Avg CPU" value={`${metrics.averageCpu}%`} />
          <StatusItem icon={MemoryStick} label="Avg Memory" value={`${metrics.averageMemory}%`} />
          <StatusItem icon={Activity} label="Active workloads" value={activeWorkloadCount} />
        </div>

        <div className="flex items-center gap-3 rounded-full border border-white/10 bg-white/5 px-3 py-2 text-sm text-slate-200">
          <span className={`h-2.5 w-2.5 rounded-full ${indicatorTone}`} />
          <StatusBadge value={streamLabel} />
        </div>
      </div>
    </header>
  );
}

function StatusItem({ label, value, icon: Icon }) {
  return (
    <div className="rounded-2xl border border-white/10 bg-white/5 px-3 py-3 text-left shadow-[inset_0_1px_0_rgba(255,255,255,0.03)]">
      <div className="flex items-center gap-2 text-slate-400">
        {Icon ? <Icon size={14} /> : null}
        <p className="text-[11px] uppercase tracking-[0.24em]">{label}</p>
      </div>
      <p className="mt-2 text-lg font-semibold text-white">{value}</p>
    </div>
  );
}
