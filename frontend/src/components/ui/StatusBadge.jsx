const toneMap = {
  pending: 'border-amber-400/20 bg-amber-400/10 text-amber-200',
  evaluating: 'border-sky-400/20 bg-sky-400/10 text-sky-200',
  ready_for_deployment: 'border-emerald-400/20 bg-emerald-400/10 text-emerald-200',
  deploying: 'border-indigo-400/20 bg-indigo-400/10 text-indigo-200',
  deployed: 'border-emerald-400/20 bg-emerald-400/10 text-emerald-200',
  cancelled: 'border-slate-400/20 bg-slate-400/10 text-slate-200',
  failed: 'border-rose-400/20 bg-rose-400/10 text-rose-200',
  delayed: 'border-violet-400/20 bg-violet-400/10 text-violet-200',
  available: 'border-emerald-400/20 bg-emerald-400/10 text-emerald-200',
  unavailable: 'border-rose-400/20 bg-rose-400/10 text-rose-200',
  active: 'border-sky-400/20 bg-sky-400/10 text-sky-200',
  connected: 'border-emerald-400/20 bg-emerald-400/10 text-emerald-200',
  connecting: 'border-sky-400/20 bg-sky-400/10 text-sky-200',
  reconnecting: 'border-amber-400/20 bg-amber-400/10 text-amber-200',
  idle: 'border-slate-400/20 bg-slate-400/10 text-slate-200',
  standby: 'border-slate-400/20 bg-slate-400/10 text-slate-200',
  default: 'border-white/10 bg-white/5 text-slate-200',
};

export default function StatusBadge({ value, className = '' }) {
  const tone = toneMap[String(value).toLowerCase()] ?? toneMap.default;

  return (
    <span
      className={[
        'inline-flex items-center rounded-full border px-3 py-1 text-xs font-semibold uppercase tracking-[0.22em]',
        tone,
        className,
      ]
        .filter(Boolean)
        .join(' ')}
    >
      {value}
    </span>
  );
}
