import React from 'react'
import Sidebar from './Sidebar'
import TopBar from './TopBar'
import { Outlet, useLocation } from 'react-router-dom'

const pageTitles: Record<string, string> = {
  '/': 'Home',
  '/analyze': 'Document Analyzer',
  '/products': 'Product Search',
  '/market': 'Market Intelligence',
}

const AppLayout: React.FC = () => {
  const location = useLocation()
  const title = pageTitles[location.pathname] ?? 'FinSight AI'

  return (
    <div className="flex h-screen overflow-hidden bg-gradient-to-br from-slate-950 via-slate-950 to-slate-900 text-slate-100">
      <Sidebar />

      <div className="flex flex-1 flex-col overflow-hidden">
        <TopBar title={title} />

        <main className="flex-1 overflow-y-auto px-8 py-6">
          <div className="mx-auto max-w-7xl">
            <Outlet />
          </div>
        </main>
      </div>
    </div>
  )
}

export default AppLayout