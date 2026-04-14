import React from 'react'

type TopBarProps = {
  title: string
}

const TopBar: React.FC<TopBarProps> = ({ title }) => {
  return (
    <header className="flex items-center justify-between gap-4 border-b border-slate-800 bg-slate-950/90 px-6 py-4 backdrop-blur">

      <div className="flex items-center gap-3">

        <div>

          <p className="text-sm font-semibold uppercase tracking-[0.2em] text-slate-400">
            {title}
          </p>

          <span className="inline-flex items-center rounded-full bg-slate-800 px-2.5 py-1 text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-300">
            Beta
          </span>

        </div>

      </div>

    </header>
  )
}

export default TopBar