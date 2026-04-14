import axios from 'axios'

const api = axios.create({
  baseURL: '',
  headers: { 'Content-Type': 'application/json' },
})

// ─── Types (matched exactly to backend models.py) ─────────────────────────────

export type UploadDocumentResponse = {
  session_id: string
  document_type: string
  page_count: number
  key_terms: string[]
  message: string
}

// ClausesResponse → clauses: List[RiskyClause]
export type RiskyClause = {
  clause_type: string
  excerpt: string
  risk_level: 'high' | 'medium' | 'low'
  plain_explanation: string
}

export type ClauseResponse = {
  session_id: string
  clauses: RiskyClause[]
  total_found: number
}

// MarketExplainResponse fields from models.py
export type MarketExplainResponse = {
  query: string
  possible_reasons: string[]
  background: string
  historical_context: string
  what_to_watch: string[]
  sources_used: string[]
}

export type MarketPatternsResponse = {
  similar_events: Array<{
    headline: string
    date: string
    nifty_1d: number | null
    nifty_1w: number | null
  }>
  pattern_summary: string
  key_factors: string[]
  what_to_watch: string[]
  disclaimer: string
}

// NewsArticle — id is int, field is 'headline' not 'title'
export type NewsArticle = {
  id: number
  headline: string
  source: string
  url: string
  published_at: string
  category: string
  sentiment?: 'positive' | 'negative' | 'neutral'
  summary?: string
}

// ─── Streaming helper ─────────────────────────────────────────────────────────

async function readStream(
  res: Response,
  onChunk: (chunk: string) => void,
): Promise<void> {
  if (!res.ok) throw new Error(`Request failed: ${res.status} ${res.statusText}`)
  if (!res.body) throw new Error('No response body')

  const reader = res.body.getReader()
  const decoder = new TextDecoder('utf-8')

  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    const raw = decoder.decode(value, { stream: true })
    for (const line of raw.split('\n')) {
      if (line.startsWith('data: ')) {
        const token = line.slice(6).trim()
        if (token && token !== '[DONE]') onChunk(token)
      } else if (line.trim()) {
        onChunk(line)
      }
    }
  }
}

// ─── Document ─────────────────────────────────────────────────────────────────

export async function uploadDocument(formData: FormData): Promise<UploadDocumentResponse> {
  const { data } = await api.post<UploadDocumentResponse>('/api/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return data
}

// ChatRequest: { session_id, question }
export async function chatStream(
  sessionId: string,
  question: string,
  onChunk: (chunk: string) => void,
  onComplete?: () => void,
  onError?: (err: unknown) => void,
): Promise<void> {
  try {
    const res = await fetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ session_id: sessionId, question }),
    })
    await readStream(res, onChunk)
    onComplete?.()
  } catch (err) {
    onError?.(err)
  }
}

export async function getClauses(sessionId: string): Promise<ClauseResponse> {
  const { data } = await api.get<ClauseResponse>('/api/clauses', {
    params: { session_id: sessionId },
  })
  return data
}

export async function deleteSession(sessionId: string): Promise<void> {
  await api.delete('/api/session', { params: { session_id: sessionId } })
}

// ─── Products ─────────────────────────────────────────────────────────────────

export async function searchProductsStream(
  query: string,
  onChunk: (chunk: string) => void,
  onComplete?: () => void,
  onError?: (err: unknown) => void,
): Promise<void> {
  try {
    const res = await fetch('/api/products/search', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query }),
    })
    await readStream(res, onChunk)
    onComplete?.()
  } catch (err) {
    onError?.(err)
  }
}

// ─── Market ───────────────────────────────────────────────────────────────────

export async function getMarketExplain(query: string): Promise<MarketExplainResponse> {
  const { data } = await api.get<MarketExplainResponse>('/api/market/explain', {
    params: { query },
  })
  return data
}

export async function getMarketPatterns(query: string): Promise<MarketPatternsResponse> {
  const { data } = await api.get<MarketPatternsResponse>('/api/market/patterns', {
    params: { query },
  })
  return data
}

// ─── News ─────────────────────────────────────────────────────────────────────

export async function getNews(limit = 30): Promise<NewsArticle[]> {
  const { data } = await api.get<{ articles: NewsArticle[]; total: number; last_updated: string }>('/api/news', {
    params: { limit },
  })
  return data.articles ?? []
}

// NewsExplainRequest: { headline, url? }
export async function explainNews(headline: string, url?: string): Promise<MarketExplainResponse> {
  const { data } = await api.post<MarketExplainResponse>('/api/news/explain', {
    headline,
    url: url ?? null,
  })
  return data
}