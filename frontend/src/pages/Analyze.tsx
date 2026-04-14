import React, { useCallback, useEffect, useRef, useState } from 'react'
import { AlertTriangle, FileText, Upload } from 'lucide-react'
import {
  uploadDocument,
  chatStream,
  getClauses,
  type UploadDocumentResponse,
  type ClauseResponse,
} from '../lib/api'

/* ───────── FileDropzone ───────── */

type FileDropzoneProps = {
  uploaded: UploadDocumentResponse | null
  uploading: boolean
  fileName: string
  onFileSelect: (file: File) => void
  onClear: () => void
}

const FileDropzone: React.FC<FileDropzoneProps> = ({
  uploaded,
  uploading,
  fileName,
  onFileSelect,
  onClear,
}) => {
  const [dragging, setDragging] = useState(false)

  const handleFiles = useCallback(
    (files: FileList | null) => {
      if (!files || files.length === 0) return
      onFileSelect(files[0])
    },
    [onFileSelect],
  )

  return (
    <div
      onDragOver={(e) => {
        e.preventDefault()
        setDragging(true)
      }}
      onDragLeave={() => setDragging(false)}
      onDrop={(e) => {
        e.preventDefault()
        setDragging(false)
        handleFiles(e.dataTransfer.files)
      }}
      className={`rounded-3xl border border-dashed p-8 text-center transition backdrop-blur-xl ${
        dragging
          ? 'border-blue-400 bg-slate-900/80'
          : 'border-slate-800 bg-slate-900/60 hover:border-blue-400'
      }`}
    >
      {uploaded ? (
        <div className="flex flex-col items-center gap-4 py-6">
          <FileText className="h-6 w-6 text-blue-400" />

          <div>
            <p className="text-sm font-semibold text-white">
              {fileName}
            </p>

            <p className="text-xs text-slate-400">
              Document ready for analysis
            </p>
          </div>

          <button
            onClick={onClear}
            className="rounded-full border border-slate-700 px-4 py-2 text-xs text-slate-400 hover:border-blue-400 hover:text-white"
          >
            Remove
          </button>
        </div>
      ) : (
        <>
          <Upload className="mx-auto mb-4 h-6 w-6 text-slate-400" />

          <p className="text-sm font-semibold text-white">
            {uploading ? 'Uploading…' : 'Upload a document'}
          </p>

          <p className="mt-2 text-sm text-slate-400">
            Drag and drop a PDF file here
          </p>

          {!uploading && (
            <>
              <input
                type="file"
                accept=".pdf"
                onChange={(e) => handleFiles(e.target.files)}
                className="hidden"
                id="document-upload"
              />

              <label
                htmlFor="document-upload"
                className="mt-6 inline-flex cursor-pointer rounded-xl bg-gradient-to-r from-blue-500 to-cyan-400 px-5 py-3 text-sm font-semibold text-white shadow hover:scale-[1.02]"
              >
                Choose file
              </label>
            </>
          )}
        </>
      )}
    </div>
  )
}

/* ───────── Document Info Card ───────── */

const DocumentInfoCard: React.FC<{
  meta: UploadDocumentResponse
  fileName: string
}> = ({ meta, fileName }) => (
  <div className="rounded-3xl border border-slate-800 bg-slate-900/60 backdrop-blur-xl p-6">
    <h2 className="text-base font-semibold text-white">
      Document info
    </h2>

    <div className="mt-4 grid gap-2 sm:grid-cols-2 text-sm">
      {[
        ['File name', fileName],
        ['Document type', meta.document_type],
        ['Pages', String(meta.page_count)],
        ['Session', meta.session_id.slice(0, 8) + '…'],
      ].map(([label, value]) => (
        <div
          key={label}
          className="rounded-2xl bg-slate-950/60 p-3"
        >
          <p className="text-[10px] uppercase tracking-widest text-slate-500">
            {label}
          </p>
          <p className="text-slate-300">{value}</p>
        </div>
      ))}
    </div>
  </div>
)

/* ───────── Risk Alerts Panel ───────── */

const RiskAlertsPanel: React.FC<{ sessionId: string | null }> = ({
  sessionId,
}) => {
  const [data, setData] =
    useState<ClauseResponse | null>(null)

  useEffect(() => {
    if (!sessionId) return
    getClauses(sessionId).then(setData)
  }, [sessionId])

  const clauses = data?.clauses ?? []

  return (
    <div className="rounded-3xl border border-slate-800 bg-slate-900/60 backdrop-blur-xl p-6">
      <h2 className="text-base font-semibold text-white">
        Risk alerts
      </h2>

      <div className="mt-4 space-y-3 text-sm">
        {clauses.length === 0 && (
          <p className="text-slate-500">
            No high-risk clauses detected.
          </p>
        )}

        {clauses.map((c, i) => (
          <div
            key={i}
            className="rounded-xl border border-red-900 bg-red-950/40 p-4"
          >
            <div className="flex items-center gap-2 text-red-400 text-xs uppercase">
              <AlertTriangle size={14} />
              Risk detected
            </div>

            <p className="mt-2 text-slate-300">
              {c.excerpt}
            </p>
          </div>
        ))}
      </div>
    </div>
  )
}

/* ───────── Chat Window ───────── */

type Message = {
  role: 'user' | 'assistant'
  text: string
}

const ChatWindow: React.FC<{
  sessionId: string | null
}> = ({ sessionId }) => {
  const [messages, setMessages] =
    useState<Message[]>([])

  const [input, setInput] = useState('')
  const [streaming, setStreaming] = useState(false)

  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({
      behavior: 'smooth',
    })
  }, [messages])

  const send = async () => {
    if (!input.trim() || !sessionId) return

    const text = input
    setInput('')

    setMessages((prev) => [
      ...prev,
      { role: 'user', text },
      { role: 'assistant', text: '' },
    ])

    setStreaming(true)

    await chatStream(
      sessionId,
      text,
      (token) => {
        setMessages((prev) => {
          const next = [...prev]
          next[next.length - 1].text += token
          return next
        })
      },
      () => setStreaming(false),
    )
  }

  return (
    <div className="rounded-3xl border border-slate-800 bg-slate-900/60 backdrop-blur-xl p-6">
      <h2 className="text-base font-semibold text-white">
        Chat with document
      </h2>

      <div className="mt-4 max-h-[400px] space-y-3 overflow-y-auto rounded-2xl bg-slate-950/60 p-4">
        {messages.map((m, i) => {
          return (
            <div
              key={i}
              className={`flex ${
                m.role === 'user'
                  ? 'justify-end'
                  : 'justify-start'
              }`}
            >
              <span className="max-w-[80%] rounded-xl bg-slate-900 px-4 py-2 text-sm text-slate-200">
                {m.text}
              </span>
            </div>
          )
        })}

        <div ref={bottomRef} />
      </div>

      {sessionId && (
        <div className="mt-4 flex gap-3">
          <input
            value={input}
            onChange={(e) =>
              setInput(e.target.value)
            }
            className="flex-1 rounded-xl border border-slate-700 bg-slate-950 px-4 py-3 text-sm text-white"
            placeholder="Ask about your document…"
          />

          <button
            onClick={send}
            disabled={streaming}
            className="rounded-xl bg-gradient-to-r from-blue-500 to-cyan-400 px-5 py-3 text-white"
          >
            Send
          </button>
        </div>
      )}
    </div>
  )
}

/* ───────── Page Component ───────── */

const Analyze: React.FC = () => {
  const [uploadResponse, setUploadResponse] =
    useState<UploadDocumentResponse | null>(null)

  const [fileName, setFileName] =
    useState<string>('')

  const [uploading, setUploading] =
    useState(false)

  const handleFileSelect = async (file: File) => {
    setUploading(true)

    const form = new FormData()
    form.append('file', file)

    const res = await uploadDocument(form)

    setUploadResponse(res)
    setFileName(file.name)

    setUploading(false)
  }

  const handleClear = () => {
    setUploadResponse(null)
  }

  return (
    <main className="space-y-8">
      <div>
        <p className="text-xs uppercase tracking-[0.3em] text-blue-400">
          DOCUMENT ANALYZER
        </p>

        <h1 className="mt-2 text-4xl font-semibold text-white">
          Upload a document to begin analysis
        </h1>
      </div>

      <div className="grid gap-6 xl:grid-cols-[1.15fr_0.85fr]">
        <div className="space-y-6">
          <FileDropzone
            uploaded={uploadResponse}
            uploading={uploading}
            fileName={fileName}
            onFileSelect={handleFileSelect}
            onClear={handleClear}
          />

          {uploadResponse && (
            <DocumentInfoCard
              meta={uploadResponse}
              fileName={fileName}
            />
          )}
        </div>

        <div className="space-y-6">
          <ChatWindow
            sessionId={
              uploadResponse?.session_id ?? null
            }
          />

          <RiskAlertsPanel
            sessionId={
              uploadResponse?.session_id ?? null
            }
          />
        </div>
      </div>
    </main>
  )
}

export default Analyze