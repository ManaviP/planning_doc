import { memo } from 'react';
import { motion } from 'framer-motion';

import CountMetric from './CountMetric';
import Panel from './Panel';

function MetricCard({ icon: Icon, label, value, suffix = '', hint, tone = 'sky' }) {
  return (
    <Panel className="h-full p-5" glow={tone} interactive>
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="text-xs font-medium uppercase tracking-[0.25em] text-slate-400">{label}</p>
          <div className="mt-4 flex items-end gap-1 text-3xl font-semibold text-white">
            <CountMetric value={value} />
            {suffix ? <span className="pb-1 text-sm text-slate-400">{suffix}</span> : null}
          </div>
          {hint ? <p className="mt-3 max-w-[18rem] text-sm leading-6 text-slate-400">{hint}</p> : null}
        </div>
        {Icon ? (
          <motion.div
            className="flex h-12 w-12 items-center justify-center rounded-2xl border border-white/10 bg-white/5 text-sky-200"
            whileHover={{ rotate: -6, scale: 1.04 }}
          >
            <Icon size={22} strokeWidth={1.8} />
          </motion.div>
        ) : null}
      </div>
    </Panel>
  );
}

export default memo(MetricCard);
