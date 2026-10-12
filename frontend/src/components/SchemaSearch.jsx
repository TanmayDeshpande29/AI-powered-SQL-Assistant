import { useState } from "react"
import { AlertCircle, AlertTriangle, Brain, CheckCircle2, Columns2, Loader2, RefreshCw, Search, Type } from "lucide-react"
import { api } from "../lib/api"
import { formatCost, formatTime } from "../lib/format"

// Phase 3: the schema's search index (Qdrant) and a playground to query it.
// Two retrieval methods, shown side by side so their behaviour can be compared:
//   dense  = meaning: bge-small embeddings, cosine similarity ("revenue" ~ "sales")
//   sparse = keywords: BM25 over stemmed words (exact names like "sku" win here)

const INDEX_BUSY = new Set(["pending", "indexing"])

const MODES = [
  { id: "dense", label: "Meaning", hint: "dense vectors · cosine similarity", icon: Brain },
  { id: "sparse", label: "Keywords", hint: "BM25 · stemmed exact words", icon: Type },
  { id: "compare", label: "Compare", hint: "both, side by side", icon: Columns2 },
]
const EXAMPLES = ["total revenue per customer", "which products are low on stock", "payment method"]

export function IndexStatusBar({ schema, onRebuild }) {
  const [starting, setStarting] = useState(false)
  const status = schema.index_status
  const stats = schema.index_stats
  const busy = INDEX_BUSY.has(status) || starting

  const rebuild = async () => {
    setStarting(true)
    try {
      await onRebuild()
    } finally {
      setStarting(false)
    }
  }

  let line
  if (busy) {
    line = (
      <span className="text-blue-300 inline-flex items-center gap-1.5">
        <Loader2 className="w-3.5 h-3.5 animate-spin" /> Building the search index…
      </span>
    )
  } else if (status === "ready") {
    line = (
      <span className="text-green-400 inline-flex items-center gap-1.5 flex-wrap">
        <CheckCircle2 className="w-3.5 h-3.5" />
        Search index ready · {stats?.tables ?? 0} tables · {stats?.dense_model} + BM25
        {schema.indexed_at && <span className="text-gray-500">· {formatTime(schema.indexed_at)}</span>}
      </span>
    )
  } else if (status === "failed") {
    line = (
      <span className="text-red-400 inline-flex items-start gap-1.5">
        <AlertCircle className="w-3.5 h-3.5 mt-0.5 shrink-0" /> Search index failed: {schema.index_error}
      </span>
    )
  } else {
    line = <span className="text-gray-400">Search index not built yet.</span>
  }

  return (
    <div className="mt-3 pt-3 border-t border-gray-700 text-xs space-y-1" data-testid="index-status">
      <div className="flex items-center gap-3 flex-wrap">
        <div className="flex-1 min-w-0">{line}</div>
        {schema.table_count > 0 && (
          <button
            onClick={rebuild}
            disabled={busy}
            title="Re-embed tables whose text changed; unchanged tables are skipped"
            className="inline-flex items-center gap-1 px-2.5 py-1 rounded-md bg-gray-700 hover:bg-gray-600 disabled:opacity-50 text-gray-200 transition-colors"
          >
            <RefreshCw className="w-3.5 h-3.5" />
            {status === "none" ? "Build index" : status === "failed" ? "Retry" : "Rebuild index"}
          </button>
        )}
      </div>
      {status === "ready" && stats && (
        <p className="text-gray-500">
          Last run: {stats.embedded} embedded, {stats.unchanged} unchanged, {stats.enriched} described by{" "}
          {stats.enrichment_model ?? "the LLM"}
          {stats.enrichment_cost_usd > 0 && ` (${formatCost(stats.enrichment_cost_usd)})`} in {stats.seconds} s
        </p>
      )}
      {status === "ready" && stats?.enrichment_error && (
        <p className="text-amber-300 inline-flex items-start gap-1.5">
          <AlertTriangle className="w-3.5 h-3.5 mt-0.5 shrink-0" />
          Descriptions skipped ({stats.enrichment_error}). Tables are searchable by name; rebuild later to add them.
        </p>
      )}
    </div>
  )
}

function ResultList({ title, response }) {
  const max = Math.max(...response.results.map((r) => r.score), 0) || 1
  return (
    <div className="min-w-0" data-testid={`results-${response.mode}`}>
      <div className="flex items-baseline justify-between gap-2 mb-2">
        <h4 className="text-sm font-medium">{title}</h4>
        <span className="text-[11px] text-gray-500 truncate">
          {response.model} · {response.embed_ms + response.search_ms} ms
        </span>
      </div>
      {response.results.length === 0 ? (
        <p className="text-xs text-gray-400">No table contains these words.</p>
      ) : (
        <ol className="space-y-2">
          {response.results.map((hit) => (
            <li key={hit.table_id} className="p-2.5 bg-gray-900/60 rounded-lg border border-gray-700">
              <div className="flex items-center gap-2 text-sm">
                <span className="text-xs text-gray-500 w-4">{hit.rank}</span>
                <span className="font-mono font-medium truncate">
                  {hit.db_schema && <span className="text-gray-500">{hit.db_schema}.</span>}
                  {hit.name}
                </span>
                <span className="ml-auto font-mono text-xs text-cyan-300">{hit.score.toFixed(3)}</span>
              </div>
              {/* bar relative to the best hit of THIS list: dense and BM25 scores aren't comparable */}
              <div className="mt-1.5 h-1.5 bg-gray-700 rounded-full overflow-hidden">
                <div className="h-full bg-cyan-500" style={{ width: `${(hit.score / max) * 100}%` }} />
              </div>
              {hit.description && <p className="text-xs text-gray-400 mt-1.5">{hit.description}</p>}
              <details className="mt-1 text-xs">
                <summary className="cursor-pointer text-gray-500">what was indexed</summary>
                <pre className="mt-1 p-2 bg-gray-950 rounded border border-gray-700 whitespace-pre-wrap text-green-400">
                  {hit.document}
                </pre>
              </details>
            </li>
          ))}
        </ol>
      )}
    </div>
  )
}

export default function SchemaSearchPanel({ schemaId, indexStatus }) {
  const [query, setQuery] = useState("")
  const [mode, setMode] = useState("compare")
  const [results, setResults] = useState(null) // { dense?: SearchResponse, sparse?: SearchResponse }
  const [searching, setSearching] = useState(false)
  const [error, setError] = useState("")
  const ready = indexStatus === "ready"

  const run = async (text = query, chosen = mode) => {
    const q = text.trim()
    if (q.length < 2) return
    setSearching(true)
    setError("")
    try {
      const modes = chosen === "compare" ? ["dense", "sparse"] : [chosen]
      // Both searches at once: total wait = the slower one, not the sum.
      const responses = await Promise.all(modes.map((m) => api.searchSchema(schemaId, { q, mode: m })))
      setResults(Object.fromEntries(modes.map((m, i) => [m, responses[i]])))
    } catch (err) {
      setError(err.message)
    } finally {
      setSearching(false)
    }
  }

  return (
    <section className="bg-gray-800 rounded-xl p-6 border border-gray-700">
      <h3 className="text-lg font-semibold mb-1 flex items-center gap-2">
        <Search className="w-5 h-5 text-cyan-400" />
        Search playground
      </h3>
      <p className="text-xs text-gray-400 mb-4">
        Ask in plain words and see which tables the search index finds. This is the retrieval step that will pick
        the tables for the AI (next phase).
      </p>

      <form
        onSubmit={(e) => {
          e.preventDefault()
          run()
        }}
        className="flex flex-wrap gap-2"
      >
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="e.g. total revenue per customer"
          disabled={!ready}
          maxLength={500}
          aria-label="Search the schema"
          className="flex-1 min-w-[12rem] bg-gray-700 border border-gray-600 rounded-lg px-3 py-2 text-sm text-white placeholder-gray-400 focus:outline-none focus:border-cyan-500 disabled:opacity-50"
        />
        <button
          type="submit"
          disabled={!ready || searching || query.trim().length < 2}
          className="bg-cyan-600 hover:bg-cyan-500 disabled:opacity-50 disabled:cursor-not-allowed px-4 py-2 rounded-lg text-sm font-medium inline-flex items-center gap-2"
        >
          {searching ? <Loader2 className="w-4 h-4 animate-spin" /> : <Search className="w-4 h-4" />}
          Search
        </button>
      </form>

      <div className="flex flex-wrap items-center gap-2 mt-3">
        <div className="flex gap-1 p-1 bg-gray-900 rounded-lg" role="radiogroup" aria-label="Search method">
          {MODES.map((m) => {
            const Icon = m.icon
            return (
              <button
                key={m.id}
                role="radio"
                aria-checked={mode === m.id}
                title={m.hint}
                onClick={() => {
                  setMode(m.id)
                  if (results) run(query, m.id)
                }}
                className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs transition-colors ${
                  mode === m.id ? "bg-gray-700 text-cyan-300" : "text-gray-400 hover:text-gray-200"
                }`}
              >
                <Icon className="w-3.5 h-3.5" />
                {m.label}
              </button>
            )
          })}
        </div>
        {ready &&
          EXAMPLES.map((example) => (
            <button
              key={example}
              onClick={() => {
                setQuery(example)
                run(example)
              }}
              className="text-xs px-2 py-1 rounded-md bg-gray-700/60 text-gray-300 hover:bg-gray-700"
            >
              {example}
            </button>
          ))}
      </div>

      {!ready && <p className="text-xs text-gray-500 mt-3">Available once the search index is ready.</p>}
      {error && <p className="text-sm text-red-400 mt-3">{error}</p>}

      {results && (
        <div className={`grid gap-4 mt-4 ${Object.keys(results).length > 1 ? "md:grid-cols-2" : ""}`}>
          {results.dense && <ResultList title="By meaning (dense)" response={results.dense} />}
          {results.sparse && <ResultList title="By keywords (BM25)" response={results.sparse} />}
        </div>
      )}
    </section>
  )
}
