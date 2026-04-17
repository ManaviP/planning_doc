import { motion, useScroll, useTransform } from 'framer-motion';
import {
  ArrowRight,
  Bot,
  Brain,
  Cpu,
  GitBranch,
  Layers3,
  ShieldCheck,
  Sparkles,
  Waves,
} from 'lucide-react';
import { Link } from 'react-router-dom';

import MetricCard from '../components/ui/MetricCard';
import Panel from '../components/ui/Panel';
import Reveal from '../components/ui/Reveal';
import ScenarioExplorer from '../components/ScenarioExplorer';
import SectionHeader from '../components/ui/SectionHeader';
import StatusBadge from '../components/ui/StatusBadge';
import { useWorkloadContext } from '../context/WorkloadContext';

const workflowSteps = [
  {
    title: 'Signal capture',
    copy: 'The platform continuously ingests workload intent, live node telemetry, and operational constraints before any placement is proposed.',
    icon: Waves,
  },
  {
    title: 'Multi-agent reasoning',
    copy: 'Independent evaluators score cost, risk, latency, and energy to keep the final decision explainable instead of opaque.',
    icon: Brain,
  },
  {
    title: 'Negotiated placement',
    copy: 'Candidate scenarios are ranked into an infrastructure-aware shortlist designed for resilient execution and measurable trade-offs.',
    icon: GitBranch,
  },
  {
    title: 'Live deployment loop',
    copy: 'Operators can observe pod progression, logs, and topology alignment in a single command-center style interface.',
    icon: ShieldCheck,
  },
];

const standoutCards = [
  {
    title: 'Decision transparency first',
    copy: 'Teams can inspect why a node won through clear scenario scores, workload constraints, and deployment outcomes.',
  },
  {
    title: 'Built for real infrastructure conversations',
    copy: 'This is more than a form-and-table demo. The UI mirrors how infra teams reason about fleet health, workload urgency, and deployment confidence.',
  },
  {
    title: 'AI-assisted, not black-box',
    copy: 'Human-readable trade-offs stay visible across telemetry, scenario ranking, frontier analysis, and runtime logs.',
  },
];

export default function DashboardHome() {
  const { clusterNodes, latestDecision, currentWorkloadId, wsStatus } = useWorkloadContext();
  const { scrollYProgress } = useScroll();
  const streamStatus = wsStatus === 'idle' ? 'standby' : wsStatus;

  const heroY = useTransform(scrollYProgress, [0, 1], [0, -140]);
  const orbitY = useTransform(scrollYProgress, [0, 1], [0, 180]);

  const availableNodes = clusterNodes.filter((node) => node.available).length;
  const avgCpu = clusterNodes.length
    ? clusterNodes.reduce((sum, node) => sum + Number(node.cpu_usage_pct || 0), 0) / clusterNodes.length
    : 0;
  const bestScore = latestDecision?.selected_scenario_id
    ? Number(latestDecision.final_scores?.[latestDecision.selected_scenario_id] ?? 0)
    : 0;

  return (
    <div className="space-y-10">
      <section className="relative overflow-hidden rounded-[32px] border border-white/10 bg-slate-950/70 px-6 py-12 shadow-[0_30px_120px_rgba(2,6,23,0.55)] sm:px-10 lg:px-12">
        <motion.div className="absolute -right-12 top-8 h-48 w-48 rounded-full bg-sky-400/20 blur-3xl" style={{ y: orbitY }} />
        <motion.div className="absolute bottom-0 left-0 h-56 w-56 rounded-full bg-indigo-500/20 blur-3xl" style={{ y: heroY }} />
        <div className="relative z-10 grid gap-10 lg:grid-cols-[1.1fr_0.9fr] lg:items-center">
          <div>
            <Reveal>
              <div className="inline-flex items-center gap-2 rounded-full border border-sky-400/20 bg-sky-400/10 px-4 py-2 text-xs font-medium uppercase tracking-[0.35em] text-sky-200">
                <Sparkles size={14} />
                Premium AI infrastructure orchestration
              </div>
            </Reveal>
            <Reveal delay={0.05}>
              <h1 className="mt-6 max-w-4xl text-4xl font-semibold tracking-tight text-white sm:text-5xl xl:text-6xl">
                Make workload placement look as intelligent as the system behind it.
              </h1>
            </Reveal>
            <Reveal delay={0.1}>
              <p className="mt-6 max-w-3xl text-base leading-8 text-slate-300 sm:text-lg">
                This dashboard turns a functioning allocator into a product-grade control plane: crisp telemetry, transparent AI reasoning,
                topology context, and deployment confidence in one polished operator experience.
              </p>
            </Reveal>
            <Reveal delay={0.15} className="mt-8 flex flex-wrap items-center gap-4">
              <Link
                className="inline-flex items-center gap-2 rounded-full bg-sky-400 px-5 py-3 text-sm font-semibold text-slate-950 transition hover:bg-sky-300"
                to="/workloads"
              >
                Launch a workload
                <ArrowRight size={16} />
              </Link>
              <Link
                className="inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/[0.04] px-5 py-3 text-sm font-semibold text-white transition hover:border-white/20 hover:bg-white/[0.08]"
                to="/cluster"
              >
                Inspect live cluster
              </Link>
              <StatusBadge value={streamStatus} className="px-4 py-3 text-[10px]" />
            </Reveal>
          </div>

          <Reveal delay={0.2} className="grid gap-4 sm:grid-cols-2">
            <MetricCard
              hint="Healthy nodes ready for negotiation-aware deployment."
              icon={Layers3}
              label="Available nodes"
              tone="emerald"
              value={availableNodes}
            />
            <MetricCard hint="Fleet-wide live CPU pressure." icon={Cpu} label="Avg CPU load" suffix="%" value={avgCpu} />
            <MetricCard
              hint="Latest selected scenario score from the negotiation engine."
              icon={Bot}
              label="Decision confidence"
              suffix="pts"
              value={bestScore}
            />
            <MetricCard
              hint={currentWorkloadId ? 'An active workload is currently threaded through decision views.' : 'Submit a workload to unlock decision-specific views.'}
              icon={ShieldCheck}
              label="Context armed"
              tone="rose"
              value={currentWorkloadId ? 1 : 0}
            />
          </Reveal>
        </div>
      </section>

      <section className="grid gap-6 xl:grid-cols-[1.25fr_0.75fr]">
        <Reveal>
          <Panel className="p-8">
            <SectionHeader
              eyebrow="Why this stands out"
              title="A dashboard that makes the platform feel credible in minutes"
              description="The experience is designed to impress quickly with maturity, operator empathy, AI transparency, and a strong operational narrative."
            />
            <div className="mt-8 grid gap-4 md:grid-cols-3">
              {standoutCards.map((card, index) => (
                <motion.div
                  key={card.title}
                  className="rounded-[24px] border border-white/10 bg-white/[0.03] p-5"
                  initial={{ opacity: 0, y: 18 }}
                  transition={{ delay: 0.08 * index, duration: 0.45 }}
                  viewport={{ once: true }}
                  whileHover={{ y: -6, rotateX: 2, rotateY: -2 }}
                  whileInView={{ opacity: 1, y: 0 }}
                >
                  <p className="text-sm font-semibold text-white">{card.title}</p>
                  <p className="mt-3 text-sm leading-7 text-slate-400">{card.copy}</p>
                </motion.div>
              ))}
            </div>
          </Panel>
        </Reveal>

        <Reveal delay={0.1}>
          <Panel className="h-full p-8" glow="emerald">
            <p className="text-xs uppercase tracking-[0.35em] text-emerald-300/80">Operator takeaway</p>
            <h3 className="mt-4 text-2xl font-semibold text-white">Control, clarity, and trust</h3>
            <p className="mt-4 text-sm leading-7 text-slate-400">
              Instead of hiding behind raw infra metrics, the platform surfaces just enough decision context for reviewers and operators to see why
              it is credible: data-informed, AI-assisted, and deployment-aware.
            </p>
            <div className="mt-6 space-y-3 text-sm text-slate-300">
              <div className="rounded-2xl border border-white/10 bg-white/[0.03] px-4 py-3">Live node telemetry powers placement confidence.</div>
              <div className="rounded-2xl border border-white/10 bg-white/[0.03] px-4 py-3">Negotiation scores remain visible and defensible.</div>
              <div className="rounded-2xl border border-white/10 bg-white/[0.03] px-4 py-3">Deployment outcomes stay tied to the selected scenario.</div>
            </div>
          </Panel>
        </Reveal>
      </section>

      <Reveal>
        <Panel className="p-8 sm:p-10">
          <SectionHeader
            eyebrow="AI workflow"
            title="How the orchestration journey unfolds"
            description="The platform experience is structured like a modern SaaS narrative: signal intake, scenario generation, AI scoring, and controlled deployment feedback."
          />
          <div className="mt-10 grid gap-5 lg:grid-cols-4">
            {workflowSteps.map((step, index) => {
              const Icon = step.icon;
              return (
                <motion.article
                  key={step.title}
                  className="group relative overflow-hidden rounded-[28px] border border-white/10 bg-white/[0.03] p-6"
                  whileHover={{ y: -8, rotateX: 3, rotateY: -3 }}
                >
                  <div className="absolute right-4 top-4 text-4xl font-semibold text-white/5">0{index + 1}</div>
                  <div className="flex h-12 w-12 items-center justify-center rounded-2xl border border-white/10 bg-sky-400/10 text-sky-200">
                    <Icon size={22} />
                  </div>
                  <h3 className="mt-5 text-lg font-semibold text-white">{step.title}</h3>
                  <p className="mt-3 text-sm leading-7 text-slate-400">{step.copy}</p>
                </motion.article>
              );
            })}
          </div>
        </Panel>
      </Reveal>

      <Reveal>
        <ScenarioExplorer />
      </Reveal>

      <section className="grid gap-6 lg:grid-cols-3">
        <Reveal>
          <Panel className="p-7" interactive>
            <p className="text-xs uppercase tracking-[0.35em] text-slate-500">Live surfaces</p>
            <h3 className="mt-3 text-xl font-semibold text-white">Cluster intelligence</h3>
            <p className="mt-3 text-sm leading-7 text-slate-400">Move from macro health to node-level metrics, availability state, and deployment pressure in a single jump.</p>
            <Link className="mt-6 inline-flex items-center gap-2 text-sm font-semibold text-sky-300 hover:text-sky-200" to="/cluster">
              Explore cluster views
              <ArrowRight size={16} />
            </Link>
          </Panel>
        </Reveal>
        <Reveal delay={0.08}>
          <Panel className="p-7" interactive glow="emerald">
            <p className="text-xs uppercase tracking-[0.35em] text-slate-500">Explainability</p>
            <h3 className="mt-3 text-xl font-semibold text-white">Decision transparency</h3>
            <p className="mt-3 text-sm leading-7 text-slate-400">Scenario tables, reasoning bands, and Pareto trade-offs help teams understand value and operational quality at a glance.</p>
            <Link className="mt-6 inline-flex items-center gap-2 text-sm font-semibold text-sky-300 hover:text-sky-200" to={currentWorkloadId ? `/decision/${currentWorkloadId}` : '/workloads'}>
              Review AI decisions
              <ArrowRight size={16} />
            </Link>
          </Panel>
        </Reveal>
        <Reveal delay={0.16}>
          <Panel className="p-7" interactive glow="rose">
            <p className="text-xs uppercase tracking-[0.35em] text-slate-500">Delivery proof</p>
            <h3 className="mt-3 text-xl font-semibold text-white">Deployment confidence</h3>
            <p className="mt-3 text-sm leading-7 text-slate-400">From candidate selection to pod lifecycle, the operator gets an audit trail that feels production-grade.</p>
            <Link className="mt-6 inline-flex items-center gap-2 text-sm font-semibold text-sky-300 hover:text-sky-200" to={currentWorkloadId ? `/logs/${currentWorkloadId}` : '/workloads'}>
              Open deployment logs
              <ArrowRight size={16} />
            </Link>
          </Panel>
        </Reveal>
      </section>
    </div>
  );
}
