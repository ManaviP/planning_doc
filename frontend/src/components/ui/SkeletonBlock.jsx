export default function SkeletonBlock({ className = '' }) {
  return <div className={['animate-pulse rounded-2xl bg-white/5 shimmer', className].filter(Boolean).join(' ')} />;
}
