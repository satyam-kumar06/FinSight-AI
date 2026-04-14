import React, { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  getMarketExplain,
  getMarketPatterns,
  type MarketExplainResponse,
  type MarketPatternsResponse,
} from '../lib/api'
import NewsFeed from '../components/News/NewsFeed'

const EXPLAIN_SUGGESTIONS = [
  'What is VIX?',
  'Why do rate hikes affect stocks?',
  'What happens when RBI cuts rates?',
  'How do FIIs impact Nifty?',
  'What is a bear market?',
]

const TABS = ['Explain', 'Patterns', 'News'] as const
type Tab = typeof TABS[number]

const QueryInput: React.FC<{
  value: string
  onChange: (v: string) => void
  onSubmit: () => void
  placeholder: string
  loading: boolean
  submitLabel?: string
}> = ({ value, onChange, onSubmit, placeholder, loading, submitLabel = 'Ask' }) => (
  <div className="flex items-center gap-3">

    <input
      value={value}
      onChange={(e) => onChange(e.target.value)}
      onKeyDown={(e) => e.key === 'Enter' && onSubmit()}
      placeholder={placeholder}
      className="flex-1 rounded-xl border border-slate-700 bg-slate-950/60 px-5 py-3 text-sm outline-none transition focus:border-blue-500 focus:ring-2 focus:ring-blue-500/30 placeholder:text-slate-500"
    />

    <button
      onClick={onSubmit}
      disabled={loading || !value.trim()}
      className="rounded-xl bg-gradient-to-r from-blue-500 to-cyan-400 px-5 py-3 text-sm font-semibold text-white shadow hover:scale-[1.02] transition disabled:opacity-40"
    >
      {loading ? '…' : submitLabel}
    </button>

  </div>
)

const Market: React.FC = () => {

  const [activeTab, setActiveTab] = useState<Tab>('Explain')

  const [explainQuery, setExplainQuery] = useState('')
  const [patternsQuery, setPatternsQuery] = useState('')

  const [explainLoading, setExplainLoading] = useState(false)
  const [patternsLoading, setPatternsLoading] = useState(false)

  const [explainError, setExplainError] = useState<string | null>(null)
  const [patternsError, setPatternsError] = useState<string | null>(null)

  const [explainResult, setExplainResult] =
    useState<MarketExplainResponse | null>(null)

  const [patternsResult, setPatternsResult] =
    useState<MarketPatternsResponse | null>(null)


  const handleExplainSubmit = async (q: string) => {
    if (!q.trim()) return

    setExplainLoading(true)
    setExplainError(null)

    try {
      setExplainResult(await getMarketExplain(q))
    } catch (err) {
      setExplainError(
        err instanceof Error
          ? err.message
          : 'Failed to fetch explanation',
      )
    } finally {
      setExplainLoading(false)
    }
  }


  const handlePatternsSubmit = async (q: string) => {
    if (!q.trim()) return

    setPatternsLoading(true)
    setPatternsError(null)

    try {
      setPatternsResult(await getMarketPatterns(q))
    } catch (err) {
      setPatternsError(
        err instanceof Error
          ? err.message
          : 'Failed to fetch patterns',
      )
    } finally {
      setPatternsLoading(false)
    }
  }


  return (
    <main className="space-y-6 max-w-4xl">

      {/* TAB BAR */}
      <div className="flex gap-2">

        {TABS.map((tab) => (

          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className={`rounded-xl px-5 py-2 text-sm font-medium transition
            ${
              activeTab === tab
                ? 'bg-gradient-to-r from-blue-500 to-cyan-400 text-white shadow'
                : 'border border-slate-800 text-slate-400 hover:border-blue-400 hover:text-white'
            }`}
          >
            {tab}
          </button>

        ))}

      </div>


      {/* ================= EXPLAIN TAB ================= */}

      {activeTab === 'Explain' && (

        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          className="space-y-5"
        >

          <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-4 text-xs text-slate-400 backdrop-blur-xl">
            FinSight explains markets. It does not predict price movements or give investment advice.
          </div>


          <QueryInput
            value={explainQuery}
            onChange={setExplainQuery}
            onSubmit={() => handleExplainSubmit(explainQuery)}
            placeholder="Ask a market question…"
            loading={explainLoading}
          />


          {/* suggestion chips */}

          <div className="flex flex-wrap gap-2">

            {EXPLAIN_SUGGESTIONS.map((chip) => (

              <button
                key={chip}
                onClick={() => {
                  setExplainQuery(chip)
                  handleExplainSubmit(chip)
                }}
                className="rounded-full border border-slate-800 bg-slate-900 px-4 py-2 text-xs text-slate-400 transition hover:border-blue-400 hover:text-white"
              >
                {chip}
              </button>

            ))}

          </div>


          {explainLoading && (
            <p className="animate-pulse text-sm text-slate-500">
              Loading explanation…
            </p>
          )}

          {explainError && (
            <p className="text-sm text-red-400">
              {explainError}
            </p>
          )}


          <AnimatePresence mode="wait">

            {explainResult && (

              <motion.div
                initial={{ opacity: 0, y: 12 }}
                animate={{ opacity: 1, y: 0 }}
                className="rounded-3xl border border-slate-800 bg-slate-900/60 p-6 backdrop-blur-xl space-y-5"
              >

                {/* reasons */}

                {explainResult.possible_reasons?.length > 0 && (

                  <div>

                    <p className="mb-2 text-xs uppercase tracking-widest text-blue-400">
                      Possible Reasons
                    </p>

                    <ul className="space-y-2 text-sm text-slate-300">

                      {explainResult.possible_reasons.map((r, i) => (

                        <li key={i}>
                          • {r}
                        </li>

                      ))}

                    </ul>

                  </div>

                )}


                {explainResult.background && (

                  <p className="text-sm text-slate-300 leading-relaxed">
                    {explainResult.background}
                  </p>

                )}


                {explainResult.historical_context && (

                  <p className="border-l-2 border-blue-400 pl-4 text-sm italic text-slate-400">
                    {explainResult.historical_context}
                  </p>

                )}


                {explainResult.what_to_watch?.length > 0 && (

                  <div>

                    <p className="mb-2 text-xs uppercase tracking-widest text-blue-400">
                      What to Watch
                    </p>

                    <div className="flex flex-wrap gap-2">

                      {explainResult.what_to_watch.map((p, i) => (

                        <span
                          key={i}
                          className="rounded-full border border-slate-800 bg-slate-950 px-3 py-1 text-xs text-slate-400"
                        >
                          {p}
                        </span>

                      ))}

                    </div>

                  </div>

                )}


                {explainResult.sources_used?.length > 0 && (

                  <p className="border-t border-slate-800 pt-3 text-xs text-slate-500">
                    Sources: {explainResult.sources_used.join(', ')}
                  </p>

                )}

              </motion.div>

            )}

          </AnimatePresence>

        </motion.div>

      )}


      {/* ================= PATTERNS TAB ================= */}

      {activeTab === 'Patterns' && (

        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          className="space-y-5"
        >

          <QueryInput
            value={patternsQuery}
            onChange={setPatternsQuery}
            onSubmit={() => handlePatternsSubmit(patternsQuery)}
            placeholder="e.g. What happened after RBI raised rates?"
            loading={patternsLoading}
            submitLabel="Search"
          />


          {patternsLoading && (
            <p className="animate-pulse text-sm text-slate-500">
              Searching patterns…
            </p>
          )}

          {patternsError && (
            <p className="text-sm text-red-400">
              {patternsError}
            </p>
          )}


          {patternsResult && (

            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="rounded-3xl border border-slate-800 bg-slate-900/60 backdrop-blur-xl p-6 space-y-5"
            >

              {/* TABLE */}

              <div className="overflow-x-auto rounded-xl border border-slate-800">

                <table className="w-full text-left text-sm">

                  <thead className="bg-slate-950 text-xs uppercase tracking-widest text-slate-500">

                    <tr>
                      <th className="px-4 py-3">Date</th>
                      <th className="px-4 py-3">Headline</th>
                      <th className="px-4 py-3">Nifty 1D</th>
                      <th className="px-4 py-3">Nifty 1W</th>
                    </tr>

                  </thead>

                  <tbody className="divide-y divide-slate-800">

                    {patternsResult.similar_events.map((event, idx) => (

                      <tr key={idx}>

                        <td className="px-4 py-3 text-slate-500">
                          {event.date}
                        </td>

                        <td className="px-4 py-3 text-slate-300">
                          {event.headline}
                        </td>

                        <td className="px-4 py-3 font-mono text-emerald-400">
                          {event.nifty_1d ?? '—'}
                        </td>

                        <td className="px-4 py-3 font-mono text-emerald-400">
                          {event.nifty_1w ?? '—'}
                        </td>

                      </tr>

                    ))}

                  </tbody>

                </table>

              </div>


              {patternsResult.pattern_summary && (

                <p className="text-sm text-slate-300">
                  {patternsResult.pattern_summary}
                </p>

              )}


              {patternsResult.key_factors?.length > 0 && (

                <div>

                  <p className="text-xs uppercase tracking-widest text-blue-400">
                    Key Factors
                  </p>

                  <ul className="list-disc pl-5 text-sm text-slate-300">

                    {patternsResult.key_factors.map((f, i) => (
                      <li key={i}>{f}</li>
                    ))}

                  </ul>

                </div>

              )}

            </motion.div>

          )}

        </motion.div>

      )}


      {/* ================= NEWS TAB ================= */}

      {activeTab === 'News' && (
        <NewsFeed limit={40} />
      )}

    </main>
  )
}

export default Market