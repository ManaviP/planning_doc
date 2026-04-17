import { AnimatePresence, motion } from 'framer-motion';
import {
  Activity,
  Binary,
  Boxes,
  BrainCircuit,
  FileStack,
  GitBranchPlus,
  LayoutDashboard,
  LineChart,
  Radar,
  Sparkles,
} from 'lucide-react';
import { NavLink, useLocation } from 'react-router-dom';

import ClusterStatusBar from '../ClusterStatusBar';
import StatusBadge from '../ui/StatusBadge';
import { useWorkloadContext } from '../../context/WorkloadContext';

const navItems = [
  { label: 'Overview', to: '/', icon: LayoutDashboard },
  { label: 'Submit workload', to: '/workloads', icon: GitBranchPlus },
  { label: 'Cluster', to: '/cluster', icon: Boxes },
  { label: 'Topology', to: '/topology', icon: Binary },
  { label: 'AI decision', to: '/decision', icon: BrainCircuit },
  { label: 'Preview', to: '/preview', icon: Sparkles },
  { label: 'Model eval', to: 'evaluation', icon: LineChart, requiresWorkload: true },
  { label: 'Pareto frontier', to: 'pareto', icon: Radar, requiresWorkload: true },
  { label: 'Deployment logs', to: 'logs', icon: FileStack, requiresWorkload: true },
];

export default function AppShell({ children }) {
  const location = useLocation();
  const { currentWorkloadId, wsStatus } = useWorkloadContext();
  const streamStatus = wsStatus === 'idle' ? 'standby' : wsStatus;

  return (
    <div className="relative min-h-screen overflow-hidden bg-[#020617] text-slate-100">
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_top_left,rgba(14,165,233,0.14),transparent_25%),radial-gradient(circle_at_80%_20%,rgba(99,102,241,0.12),transparent_20%),radial-gradient(circle_at_bottom_right,rgba(16,185,129,0.08),transparent_26%)]" />
      <div className="pointer-events-none absolute inset-0 bg-grid-mask opacity-50" />

      <div className="relative z-10 flex min-h-screen">
        <aside className="hidden w-[280px] shrink-0 border-r border-white/10 bg-slate-950/70 px-5 py-6 backdrop-blur-2xl lg:flex lg:flex-col">
          <div className="rounded-[28px] border border-white/10 bg-white/[0.04] p-5 shadow-[0_24px_80px_rgba(2,6,23,0.45)]">
            <div className="flex items-center gap-3">
              <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-gradient-to-br from-sky-400/30 via-cyan-300/10 to-indigo-500/20 text-sky-200 shadow-[0_0_35px_rgba(56,189,248,0.22)]">
                <Activity size={22} />
              </div>
              <div>
                <p className="text-xs uppercase tracking-[0.35em] text-sky-300/80">AI infra</p>
                <h1 className="mt-1 text-lg font-semibold text-white">Compute Allocator</h1>
              </div>
            </div>
            <p className="mt-4 text-sm leading-6 text-slate-400">
              Intelligent workload placement with live telemetry, transparent scoring, and deployment tracking.
            </p>
          </div>

          <nav className="mt-6 space-y-2">
            {navItems.map((item) => {
              const Icon = item.icon;
              const to = item.requiresWorkload && currentWorkloadId ? `/${item.to}/${currentWorkloadId}` : item.requiresWorkload ? '#' : item.to;
              const disabled = item.requiresWorkload && !currentWorkloadId;

              if (disabled) {
                return (
                  <span
                    key={item.label}
                    className="flex cursor-not-allowed items-center gap-3 rounded-2xl border border-transparent px-4 py-3 text-sm text-slate-500"
                  >
                    <Icon size={18} />
                    <span>{item.label}</span>
                  </span>
                );
              }

              return (
                <NavLink
                  key={item.label}
                  className={({ isActive }) =>
                    [
                      'group flex items-center gap-3 rounded-2xl border px-4 py-3 text-sm transition-all duration-300',
                      isActive
                        ? 'border-sky-400/30 bg-sky-400/10 text-white shadow-[0_0_24px_rgba(56,189,248,0.14)]'
                        : 'border-white/5 bg-white/[0.02] text-slate-300 hover:border-white/10 hover:bg-white/[0.05] hover:text-white',
                    ].join(' ')
                  }
                  to={to}
                >
                  <Icon size={18} className="transition-transform duration-300 group-hover:scale-110" />
                  <span>{item.label}</span>
                </NavLink>
              );
            })}
          </nav>

          <div className="mt-auto rounded-[28px] border border-white/10 bg-white/[0.04] p-5">
            <p className="text-xs uppercase tracking-[0.3em] text-slate-400">Realtime state</p>
            <div className="mt-3 flex items-center justify-between gap-3">
              <div>
                <p className="text-sm text-slate-400">Control plane stream</p>
                <p className="mt-1 text-sm text-white">Workload events + node snapshots</p>
              </div>
              <StatusBadge value={streamStatus} />
            </div>
            <p className="mt-4 text-xs leading-6 text-slate-500">
              Current workload context {currentWorkloadId ? 'is active across the decision views.' : 'will activate after a workload submission.'}
            </p>
          </div>
        </aside>

        <div className="flex min-h-screen flex-1 flex-col">
          <header className="sticky top-0 z-30 border-b border-white/10 bg-slate-950/55 px-4 py-4 backdrop-blur-2xl sm:px-6 lg:px-8">
            <div className="flex flex-wrap items-center justify-between gap-4">
              <div>
                <p className="text-xs uppercase tracking-[0.3em] text-slate-500">AI orchestration console</p>
                <h2 className="mt-1 text-xl font-semibold text-white">Operational intelligence cockpit</h2>
              </div>
              <div className="flex flex-wrap items-center gap-3">
                {currentWorkloadId ? (
                  <div className="rounded-full border border-white/10 bg-white/[0.04] px-4 py-2 text-xs text-slate-300">
                    Active workload <span className="font-mono text-sky-200">{currentWorkloadId}</span>
                  </div>
                ) : null}
                <StatusBadge value={streamStatus} />
              </div>
            </div>
          </header>

          <main className="flex-1 px-4 pb-10 pt-6 sm:px-6 lg:px-8">
            <ClusterStatusBar />
            <AnimatePresence mode="wait">
              <motion.div
                key={location.pathname}
                initial={{ opacity: 0, y: 18 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -14 }}
                transition={{ duration: 0.35, ease: 'easeOut' }}
              >
                {children}
              </motion.div>
            </AnimatePresence>
          </main>
        </div>
      </div>
    </div>
  );
}
