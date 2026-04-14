import React, { useEffect, useState } from 'react'
import { ExternalLink, RefreshCw } from 'lucide-react'
import { getNews, type NewsArticle } from '../../lib/api'

const SENTIMENT_STYLES = {
  positive: { dot: 'bg-emerald-400', badge: 'bg-emerald-400/10 text-emerald-400 border-emerald-400/20', label: '↑ Positive' },
  negative: { dot: 'bg-red-400',     badge: 'bg-red-400/10 text-red-400 border-red-400/20',             label: '↓ Negative' },
  neutral:  { dot: 'bg-slate-500',   badge: 'bg-slate-500/10 text-slate-400 border-slate-500/20',       label: '→ Neutral'  },
}

const formatDate = (iso: string) => {
  try {
    return new Date(iso).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' })
  } catch { return iso }
}

const NewsFeed: React.FC<{ limit?: number }> = ({ limit = 30 }) => {
  const [articles, setArticles] = useState<NewsArticle[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const load = () => {
    let cancelled = false
    setLoading(true)
    setError(null)
    getNews(limit)
      .then((data) => { if (!cancelled) setArticles(data) })
      .catch((err) => { if (!cancelled) setError(err instanceof Error ? err.message : 'Failed to load news') })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }

  useEffect(load, [limit])

  if (loading) return (
    <div className="space-y-3">
      {Array.from({ length: 5 }).map((_, i) => (
        <div key={i} className="animate-pulse rounded-2xl border border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-950">
          <div className="h-4 w-3/4 rounded bg-slate-100 dark:bg-slate-800" />
          <div className="mt-2 h-3 w-1/2 rounded bg-slate-100 dark:bg-slate-800" />
        </div>
      ))}
    </div>
  )

  if (error) return (
    <div className="rounded-2xl border border-slate-200 bg-white p-6 text-center dark:border-slate-800 dark:bg-slate-950">
      <p className="text-sm text-red-500">{error}</p>
      <button onClick={load} className="mt-4 inline-flex items-center gap-2 rounded-xl border border-slate-200 px-4 py-2 text-xs dark:border-slate-700">
        <RefreshCw className="h-3.5 w-3.5" /> Retry
      </button>
    </div>
  )

  if (articles.length === 0) return (
    <div className="rounded-2xl border border-slate-200 bg-white p-8 text-center dark:border-slate-800 dark:bg-slate-950">
      <p className="text-sm text-slate-500">No articles available.</p>
    </div>
  )

  return (
    <div className="space-y-2.5">
      <div className="flex items-center justify-between">
        <p className="text-xs font-semibold uppercase tracking-widest text-slate-500">{articles.length} articles</p>
        <button onClick={load} className="inline-flex items-center gap-1.5 rounded-xl border border-slate-200 px-3 py-1.5 text-xs dark:border-slate-700">
          <RefreshCw className="h-3 w-3" /> Refresh
        </button>
      </div>

      {articles.map((article) => {
        const s = SENTIMENT_STYLES[article.sentiment ?? 'neutral']
        return (
          <div key={article.id} className="rounded-2xl border border-slate-200 bg-white p-4 transition hover:border-slate-300 dark:border-slate-800 dark:bg-slate-950">
            <div className="flex items-start gap-3">
              <span className={`mt-1.5 h-2 w-2 shrink-0 rounded-full ${s.dot}`} />
              <div className="min-w-0 flex-1">
                <div className="flex items-start justify-between gap-3">
                  {/* headline field (not title) */}
                  {article.url ? (
                    <a href={article.url} target="_blank" rel="noopener noreferrer"
                      className="text-sm font-medium text-slate-900 hover:underline dark:text-white">
                      {article.headline}
                    </a>
                  ) : (
                    <p className="text-sm font-medium text-slate-900 dark:text-white">{article.headline}</p>
                  )}
                  {article.url && (
                    <a href={article.url} target="_blank" rel="noopener noreferrer"
                      className="shrink-0 text-slate-400 transition hover:text-slate-600">
                      <ExternalLink className="h-3.5 w-3.5" />
                    </a>
                  )}
                </div>

                {article.summary && (
                  <p className="mt-1.5 line-clamp-2 text-xs leading-5 text-slate-500">{article.summary}</p>
                )}

                <div className="mt-2.5 flex flex-wrap items-center gap-2">
                  <span className={`inline-flex items-center rounded-full border px-2 py-0.5 font-mono text-[10px] font-medium uppercase tracking-widest ${s.badge}`}>
                    {s.label}
                  </span>
                  {article.source && <span className="font-mono text-[10px] uppercase tracking-widest text-slate-500">{article.source}</span>}
                  {article.published_at && <span className="font-mono text-[10px] text-slate-400">{formatDate(article.published_at)}</span>}
                  {article.category && <span className="font-mono text-[10px] text-slate-400">{article.category}</span>}
                </div>
              </div>
            </div>
          </div>
        )
      })}
    </div>
  )
}

export default NewsFeed