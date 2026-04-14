import React, { useMemo, useRef, useState } from 'react'
import { searchProductsStream } from '../lib/api'
import { motion } from 'framer-motion'

const SUGGESTIONS = [
  'Low-cost index funds',
  'Corporate bond ETFs',
  'High-yield savings accounts',
  'Robo-advisor portfolios',
  'Term insurance under ₹15k premium',
  'Child hospitalization cover',
]

const ProductSearch: React.FC = () => {
  const [query, setQuery] = useState('')
  const [history, setHistory] = useState<string[]>([])
  const [response, setResponse] = useState('')
  const [isStreaming, setIsStreaming] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const abortRef = useRef<(() => void) | null>(null)

  const recentHistory = useMemo(() => [...history].reverse().slice(0, 5), [history])

  const submitSearch = async (term: string) => {
    if (!term.trim() || isStreaming) return

    abortRef.current?.()

    setQuery(term)

    setHistory((prev) => {
      const deduped = prev.filter((x) => x !== term)
      return [...deduped, term]
    })

    setResponse('')
    setError(null)
    setIsStreaming(true)

    let cancelled = false
    abortRef.current = () => { cancelled = true }

    await searchProductsStream(
      term,
      (chunk) => {
        if (!cancelled) setResponse((prev) => prev + chunk)
      },
      () => {
        if (!cancelled) setIsStreaming(false)
      },
      (err) => {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : 'Search failed')
          setIsStreaming(false)
        }
      },
    )
  }

  return (
    <main className="space-y-6">

      <div className="grid gap-6 xl:grid-cols-[1.6fr_0.9fr]">

        {/* MAIN COLUMN */}
        <section className="space-y-6">

          {/* SEARCH PANEL */}
          <motion.div
            initial={{ opacity: 0, y: 14 }}
            animate={{ opacity: 1, y: 0 }}
            className="rounded-3xl border border-slate-800 bg-slate-900/60 backdrop-blur-xl p-8 shadow-[0_20px_80px_-20px_rgba(59,130,246,0.25)]"
          >

            <p className="text-xs uppercase tracking-[0.3em] text-blue-400">
              PRODUCT SEARCH
            </p>

            <h1 className="mt-3 text-4xl font-semibold text-white">
              Find financial products with clarity
            </h1>

            <p className="mt-2 text-sm text-slate-400">
              FinSight explains product suitability. It does not recommend specific products.
            </p>


            {/* INPUT */}
            <div className="mt-6 space-y-4">

              <label className="text-sm text-slate-400">
                Describe what you're looking for
              </label>

              <div className="flex gap-3">

                <input
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && submitSearch(query)}
                  placeholder="e.g. insurance for 5-year-old child"
                  className="flex-1 rounded-xl border border-slate-700 bg-slate-950/60 px-5 py-3 text-sm outline-none transition focus:border-blue-500 focus:ring-2 focus:ring-blue-500/30 placeholder:text-slate-500"
                />

                <button
                  onClick={() => submitSearch(query)}
                  disabled={isStreaming || !query.trim()}
                  className="rounded-xl bg-gradient-to-r from-blue-500 to-cyan-400 px-6 py-3 text-sm font-semibold text-white shadow-lg hover:scale-[1.03] hover:shadow-blue-500/40 transition disabled:opacity-40"
                >
                  {isStreaming ? 'Searching…' : 'Search'}
                </button>

              </div>


              {/* QUICK SUGGESTIONS */}
              <div>

                <p className="text-xs font-semibold uppercase tracking-widest text-slate-500">
                  Quick suggestions
                </p>

                <div className="mt-2 flex flex-wrap gap-2">

                  {SUGGESTIONS.map((s) => (

                    <button
                      key={s}
                      onClick={() => submitSearch(s)}
                      disabled={isStreaming}
                      className="rounded-full border border-slate-700 bg-slate-900 px-4 py-2 text-xs text-slate-400 transition hover:border-blue-400 hover:text-white"
                    >
                      {s}
                    </button>

                  ))}

                </div>

              </div>

            </div>

          </motion.div>


          {/* RESPONSE PANEL */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="rounded-3xl border border-slate-800 bg-slate-900/60 backdrop-blur-xl p-6 shadow-[0_10px_40px_-10px_rgba(14,165,233,0.25)]"
          >

            <div className="flex items-center justify-between">

              <h2 className="text-sm font-semibold uppercase tracking-widest text-slate-400">
                Response
              </h2>

              {isStreaming && (
                <span className="text-xs text-blue-400 animate-pulse">
                  Streaming…
                </span>
              )}

            </div>


            <div className="mt-4 min-h-[260px] rounded-2xl bg-slate-950/60 p-6 text-sm leading-relaxed text-slate-300">

              {error && <p className="text-red-400">{error}</p>}

              {!error && !response && (
                <p className="text-slate-500">
                  Search for a product to see an AI-powered explanation here.
                </p>
              )}

              {response && (
                <div className="whitespace-pre-wrap">
                  {response}
                  {isStreaming && <span className="ml-1 animate-pulse">▋</span>}
                </div>
              )}

              {!isStreaming && response && (
                <p className="mt-5 border-t border-slate-800 pt-4 text-xs text-slate-500">
                  FinSight explains products. It does not provide investment advice.
                </p>
              )}

            </div>

          </motion.div>

        </section>


        {/* HISTORY SIDEBAR */}
        <aside>

          <div className="rounded-3xl border border-slate-800 bg-slate-900/60 backdrop-blur-xl p-6">

            <p className="text-xs font-semibold uppercase tracking-widest text-blue-400">
              Search history
            </p>

            <h2 className="mt-2 text-lg font-semibold text-white">
              Recent searches
            </h2>


            <div className="mt-4 space-y-2">

              {recentHistory.length === 0 ? (

                <p className="rounded-xl bg-slate-950/60 p-4 text-sm text-slate-500">
                  No recent searches yet.
                </p>

              ) : (

                recentHistory.map((item) => (

                  <button
                    key={item}
                    onClick={() => submitSearch(item)}
                    disabled={isStreaming}
                    className="w-full rounded-xl border border-slate-800 bg-slate-950/60 px-4 py-3 text-left text-sm text-slate-400 transition hover:border-blue-400 hover:text-white"
                  >
                    {item}
                  </button>

                ))

              )}

            </div>

          </div>

        </aside>

      </div>

    </main>
  )
}

export default ProductSearch