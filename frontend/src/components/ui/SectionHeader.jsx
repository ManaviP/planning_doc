export default function SectionHeader({ eyebrow, title, description, actions = null, align = 'between' }) {
  return (
    <div className={`flex flex-wrap gap-4 ${align === 'start' ? 'items-start justify-start' : 'items-end justify-between'}`}>
      <div className="max-w-3xl">
        {eyebrow ? <p className="text-xs font-medium uppercase tracking-[0.35em] text-sky-300/85">{eyebrow}</p> : null}
        <h2 className="mt-3 text-2xl font-semibold tracking-tight text-white sm:text-3xl">{title}</h2>
        {description ? <p className="mt-3 text-sm leading-7 text-slate-400 sm:text-base">{description}</p> : null}
      </div>
      {actions}
    </div>
  );
}
