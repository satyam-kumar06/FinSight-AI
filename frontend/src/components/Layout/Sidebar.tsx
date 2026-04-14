import React from 'react'
import { Link, useLocation } from 'react-router-dom'
import { Box, FileText, Search, TrendingUp, Sparkles } from 'lucide-react'

const navItems = [
  { name: 'Home', href: '/', icon: Sparkles },
  { name: 'Analyze Doc', href: '/analyze', icon: FileText },
  { name: 'Product Search', href: '/products', icon: Search },
  { name: 'Market', href: '/market', icon: TrendingUp },
]

const Sidebar: React.FC = () => {
  const location = useLocation()

  return (
    <aside className="flex h-full min-h-screen w-72 flex-col justify-between border-r border-slate-800 bg-slate-950/90 px-6 py-8 backdrop-blur-xl">
      <div>
        <div className="mb-12 flex items-center gap-3 text-2xl font-semibold text-white">
          <Box className="h-9 w-9 text-blue-400" />
          <span>FinSight AI</span>
        </div>

        <nav className="space-y-2">
          {navItems.map((item) => {
            const Icon = item.icon
            const active = location.pathname === item.href

            return (
              <Link
                key={item.name}
                to={item.href}
                className={`group flex items-center gap-3 rounded-xl px-4 py-3 text-sm font-medium transition ${
                  active
                    ? 'bg-gradient-to-r from-blue-500/20 to-cyan-400/10 text-white'
                    : 'text-slate-400 hover:bg-slate-900 hover:text-white'
                }`}
              >
                <Icon
                  className={`h-5 w-5 transition ${
                    active
                      ? 'text-blue-400'
                      : 'text-slate-500 group-hover:text-white'
                  }`}
                />

                {item.name}
              </Link>
            )
          })}
        </nav>
      </div>

      <div className="rounded-2xl border border-slate-800 bg-slate-900/70 p-4 text-sm text-slate-400 backdrop-blur-xl">
        FinSight explains. It never advises.
      </div>
    </aside>
  )
}

export default Sidebar