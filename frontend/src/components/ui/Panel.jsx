import { motion } from 'framer-motion';

const defaultTransition = { duration: 0.45, ease: 'easeOut' };

export default function Panel({
  as: Component = 'section',
  className = '',
  children,
  interactive = false,
  glow = 'sky',
  ...props
}) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      transition={defaultTransition}
      viewport={{ once: true, margin: '-40px' }}
      whileInView={{ opacity: 1, y: 0 }}
    >
      <Component
        className={[
          'glass-panel relative overflow-hidden rounded-[28px] border border-white/10 bg-white/[0.04] backdrop-blur-xl',
          interactive ? 'transition-transform duration-300 hover:-translate-y-1 hover:border-white/15' : '',
          glow === 'emerald' ? 'shadow-[0_20px_80px_rgba(16,185,129,0.08)]' : '',
          glow === 'rose' ? 'shadow-[0_20px_80px_rgba(244,63,94,0.08)]' : '',
          glow === 'sky' ? 'shadow-[0_20px_80px_rgba(56,189,248,0.08)]' : '',
          className,
        ]
          .filter(Boolean)
          .join(' ')}
        {...props}
      >
        <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_top_right,rgba(56,189,248,0.14),transparent_42%)]" />
        <div className="relative z-10">{children}</div>
      </Component>
    </motion.div>
  );
}
