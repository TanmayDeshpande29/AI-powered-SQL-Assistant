import { motion } from "framer-motion"
import { useEffect, useMemo, useRef, useState } from "react"
import { Link, useSearchParams } from "react-router"
import {
  AlertCircle,
  AlertTriangle,
  ArrowLeft,
  ArrowRight,
  BarChart3,
  ClipboardPaste,
  Code,
  CreditCard,
  Database,
  DollarSign,
  FileCode,
  FileText,
  Image as ImageIcon,
  KeyRound,
  Link2,
  Loader2,
  Menu,
  Plus,
  RefreshCw,
  Search,
  Settings,
  Sparkles,
  Table2,
  Trash2,
  Upload,
  User,
  X,
} from "lucide-react"
import { api } from "./lib/api"
import SchemaSearchPanel, { IndexStatusBar } from "./components/SchemaSearch"
import { SQL_DIALECTS } from "./lib/dialects"
import { formatBytes, formatCost, formatTime, plural } from "./lib/format"

// Database Setup = the user's schema workspace (Phase 2):
//   1. create a schema (a named container + its SQL dialect)
//   2. add its DDL: paste SQL, upload a .sql file, or a screenshot
//      -> the server answers 202 at once and processes the upload in the background
//      -> this page polls until every upload is "ready" or "failed"
//   3. browse the extracted tables, then use them in the Query Builder.

const BUSY = new Set(["pending", "processing"])
const INDEX_BUSY = new Set(["pending", "indexing"]) // the search index job (Phase 3)
const POLL_MS = 1500

const SOURCE_TABS = [
  {
    id: "paste",
    label: "Paste SQL",
    icon: ClipboardPaste,
    hint: "CREATE / ALTER TABLE statements, a pg_dump or mysqldump, or even SELECT queries (tables and joins are inferred from them).",
  },
  {
    id: "file",
    label: ".sql file",
    icon: FileCode,
    accept: ".sql,.ddl,.txt,text/plain",
    hint: "A .sql, .ddl or .txt file, e.g. a schema-only dump (data rows are skipped).",
  },
  {
    id: "image",
    label: "Screenshot",
    icon: ImageIcon,
    accept: "image/png,image/jpeg,image/webp",
    hint: "An ER diagram, a table designer or DDL on screen. A vision model transcribes it to SQL first.",
  },
]

const SOURCE_KINDS = {
  sql_text: { label: "Pasted SQL", icon: ClipboardPaste },
  sql_file: { label: "SQL file", icon: FileCode },
  image: { label: "Screenshot", icon: ImageIcon },
}

const STATUS_STYLES = {
  ready: "bg-green-500/15 text-green-400 border-green-500/30",
  pending: "bg-blue-500/15 text-blue-300 border-blue-500/30",
  processing: "bg-blue-500/15 text-blue-300 border-blue-500/30",
  failed: "bg-red-500/15 text-red-400 border-red-500/30",
  empty: "bg-gray-500/15 text-gray-400 border-gray-500/30",
}
const STATUS_LABELS = {
  ready: "Ready",
  pending: "Queued",
  processing: "Processing",
  failed: "Failed",
  empty: "No tables yet",
}

const inputClass =
  "w-full bg-gray-700 border border-gray-600 rounded-lg px-3 py-2 text-sm text-white placeholder-gray-400 focus:outline-none focus:border-cyan-500 transition-colors"

// SchemaDetail without its tables = the SchemaSummary shown in the list.
const summaryOf = (schema) => {
  const { tables: _tables, ...summary } = schema
  return summary
}
const byName = (a, b) => a.name.localeCompare(b.name)

function StatusBadge({ status }) {
  return (
    <span
      className={`inline-flex items-center gap-1 text-xs px-2 py-0.5 rounded-full border whitespace-nowrap ${
        STATUS_STYLES[status] ?? STATUS_STYLES.empty
      }`}
    >
      {BUSY.has(status) && <Loader2 className="w-3 h-3 animate-spin" />}
      {STATUS_LABELS[status] ?? status}
    </span>
  )
}

function NewSchemaForm({ onCreated }) {
  const [name, setName] = useState("")
  const [dialect, setDialect] = useState("PostgreSQL")
  const [description, setDescription] = useState("")
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState("")

  const submit = async (e) => {
    e.preventDefault()
    setSaving(true)
    setError("")
    try {
      const schema = await api.createSchema({
        name: name.trim(),
        dialect,
        description: description.trim() || null,
      })
      setName("")
      setDescription("")
      onCreated(schema)
    } catch (err) {
      setError(err.message) // e.g. 409: "You already have a schema named ..."
    } finally {
      setSaving(false)
    }
  }

  return (
    <form onSubmit={submit} className="bg-gray-800 rounded-xl p-5 border border-gray-700 space-y-3">
      <h2 className="font-semibold flex items-center gap-2">
        <Plus className="w-4 h-4 text-cyan-400" />
        New schema
      </h2>
      <input
        value={name}
        onChange={(e) => setName(e.target.value)}
        placeholder="Name, e.g. Shop production"
        maxLength={100}
        className={inputClass}
        aria-label="Schema name"
      />
      <select
        value={dialect}
        onChange={(e) => setDialect(e.target.value)}
        className={inputClass}
        aria-label="SQL dialect"
      >
        {SQL_DIALECTS.map((d) => (
          <option key={d.value} value={d.value}>
            {d.icon} {d.label}
          </option>
        ))}
      </select>
      <input
        value={description}
        onChange={(e) => setDescription(e.target.value)}
        placeholder="Description (optional)"
        maxLength={2000}
        className={inputClass}
        aria-label="Description"
      />
      {error && <p className="text-sm text-red-400">{error}</p>}
      <button
        type="submit"
        disabled={saving || !name.trim()}
        className="w-full bg-gradient-to-r from-cyan-500 to-blue-600 hover:from-cyan-600 hover:to-blue-700 disabled:opacity-50 disabled:cursor-not-allowed px-4 py-2 rounded-lg font-semibold text-sm transition-all flex items-center justify-center gap-2"
      >
        {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Plus className="w-4 h-4" />}
        Create schema
      </button>
    </form>
  )
}

function SchemaList({ schemas, selectedId, onSelect, loading, error }) {
  return (
    <div className="bg-gray-800 rounded-xl p-3 border border-gray-700">
      <h2 className="px-2 py-1 mb-1 text-sm font-medium text-gray-300">Your schemas</h2>
      {loading ? (
        <p className="px-2 py-4 text-sm text-gray-400 flex items-center gap-2">
          <Loader2 className="w-4 h-4 animate-spin" /> Loading…
        </p>
      ) : error ? (
        <p className="px-2 py-4 text-sm text-red-400">{error}</p>
      ) : schemas.length === 0 ? (
        <p className="px-2 py-4 text-sm text-gray-400">No schemas yet. Create one above, then add its SQL.</p>
      ) : (
        <ul className="space-y-1">
          {schemas.map((s) => (
            <li key={s.id}>
              <button
                onClick={() => onSelect(s.id)}
                className={`w-full text-left px-3 py-2.5 rounded-lg transition-colors ${
                  s.id === selectedId ? "bg-blue-600/25 border border-blue-500/50" : "hover:bg-gray-700 border border-transparent"
                }`}
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="text-sm font-medium truncate">{s.name}</span>
                  <StatusBadge status={s.status} />
                </div>
                <p className="text-xs text-gray-400 mt-0.5">
                  {s.dialect} · {plural(s.table_count, "table")} · {plural(s.column_count, "column")}
                </p>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

function AddSourcePanel({ schemaId, onUploaded }) {
  const [tab, setTab] = useState("paste")
  const [sql, setSql] = useState("")
  const [file, setFile] = useState(null)
  const [dragging, setDragging] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState("")
  const fileInputRef = useRef(null)
  const current = SOURCE_TABS.find((t) => t.id === tab)

  // Thumbnail of the chosen screenshot (an object URL must be released when replaced).
  const preview = useMemo(() => (file?.type.startsWith("image/") ? URL.createObjectURL(file) : null), [file])
  useEffect(() => () => preview && URL.revokeObjectURL(preview), [preview])

  // Screenshots usually sit on the clipboard: on the Screenshot tab, Ctrl+V picks one up.
  useEffect(() => {
    if (tab !== "image") return
    const onPaste = (e) => {
      const item = [...(e.clipboardData?.items ?? [])].find((i) => i.type.startsWith("image/"))
      if (!item) return
      e.preventDefault()
      setFile(item.getAsFile())
      setError("")
    }
    document.addEventListener("paste", onPaste)
    return () => document.removeEventListener("paste", onPaste)
  }, [tab])

  const switchTab = (id) => {
    setTab(id)
    setFile(null)
    setError("")
  }

  const onDrop = (e) => {
    e.preventDefault()
    setDragging(false)
    const dropped = e.dataTransfer.files?.[0]
    if (dropped) {
      setFile(dropped)
      setError("")
    }
  }

  const submit = async () => {
    setSubmitting(true)
    setError("")
    try {
      const source =
        tab === "paste" ? await api.addSchemaSql(schemaId, sql) : await api.uploadSchemaFile(schemaId, file)
      setSql("")
      setFile(null)
      if (fileInputRef.current) fileInputRef.current.value = ""
      onUploaded(source)
    } catch (err) {
      setError(err.message) // 413 too large, 415 unsupported type, 422 empty...
    } finally {
      setSubmitting(false)
    }
  }

  const canSubmit = tab === "paste" ? sql.trim().length > 0 : file !== null

  return (
    <section className="bg-gray-800 rounded-xl p-6 border border-gray-700">
      <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
        <Upload className="w-5 h-5 text-green-400" />
        Add schema SQL
      </h3>

      <div className="flex gap-1 p-1 bg-gray-900 rounded-lg mb-4" role="tablist">
        {SOURCE_TABS.map((t) => {
          const Icon = t.icon
          return (
            <button
              key={t.id}
              role="tab"
              aria-selected={tab === t.id}
              onClick={() => switchTab(t.id)}
              className={`flex-1 flex items-center justify-center gap-2 px-2 py-2 rounded-md text-sm whitespace-nowrap transition-colors ${
                tab === t.id ? "bg-gray-700 text-cyan-300" : "text-gray-400 hover:text-gray-200"
              }`}
            >
              <Icon className="w-4 h-4" />
              {t.label}
            </button>
          )
        })}
      </div>

      <p className="text-xs text-gray-400 mb-3">{current.hint}</p>

      {tab === "paste" ? (
        <textarea
          value={sql}
          onChange={(e) => setSql(e.target.value)}
          spellCheck={false}
          placeholder={"CREATE TABLE customers (\n  id INT PRIMARY KEY,\n  email VARCHAR(255) NOT NULL UNIQUE\n);"}
          className={`${inputClass} h-48 font-mono resize-y`}
          aria-label="Schema SQL"
        />
      ) : (
        <div
          role="button"
          tabIndex={0}
          onClick={() => fileInputRef.current?.click()}
          onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && fileInputRef.current?.click()}
          onDragOver={(e) => {
            e.preventDefault()
            setDragging(true)
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={onDrop}
          className={`border-2 border-dashed rounded-lg p-6 text-center cursor-pointer transition-colors ${
            dragging ? "border-cyan-400 bg-cyan-400/5" : "border-gray-600 hover:border-cyan-500"
          }`}
        >
          {preview ? (
            <img src={preview} alt="Selected screenshot" className="max-h-40 mx-auto rounded border border-gray-600 mb-3" />
          ) : (
            <Upload className="w-10 h-10 text-gray-400 mx-auto mb-3" />
          )}
          <p className="text-sm font-medium">{file ? file.name : "Drop a file here or click to choose"}</p>
          <p className="text-xs text-gray-400 mt-1">
            {file
              ? formatBytes(file.size)
              : tab === "image"
                ? "PNG, JPEG or WebP. You can also paste a screenshot with Ctrl+V."
                : ".sql, .ddl or .txt"}
          </p>
          <input
            key={tab}
            ref={fileInputRef}
            type="file"
            accept={current.accept}
            onChange={(e) => {
              setFile(e.target.files?.[0] ?? null)
              setError("")
            }}
            className="hidden"
            data-testid="schema-file-input"
          />
        </div>
      )}

      {error && (
        <p className="mt-3 text-sm text-red-400 flex items-start gap-2">
          <AlertCircle className="w-4 h-4 mt-0.5 shrink-0" />
          <span className="whitespace-pre-line">{error}</span>
        </p>
      )}

      <div className="flex justify-end mt-4">
        <button
          onClick={submit}
          disabled={!canSubmit || submitting}
          className="bg-gradient-to-r from-green-600 to-emerald-600 hover:from-green-700 hover:to-emerald-700 disabled:opacity-50 disabled:cursor-not-allowed px-5 py-2 rounded-lg font-semibold text-sm transition-all flex items-center gap-2"
        >
          {submitting ? <Loader2 className="w-4 h-4 animate-spin" /> : <Sparkles className="w-4 h-4" />}
          {tab === "image" ? "Read screenshot" : "Extract tables"}
        </button>
      </div>
    </section>
  )
}

function statsLine(stats) {
  const parts = []
  if (stats.tables) parts.push(plural(stats.tables, "table"))
  if (stats.altered_tables) parts.push(`${plural(stats.altered_tables, "table")} altered`)
  if (stats.inferred_tables) parts.push(`${plural(stats.inferred_tables, "table")} inferred from queries`)
  parts.push(plural(stats.columns ?? 0, "column"), plural(stats.foreign_keys ?? 0, "foreign key"))
  if (stats.tables_created != null) parts.push(`${stats.tables_created} new · ${stats.tables_updated} updated`)
  return parts.join(" · ")
}

function SourceRow({ source }) {
  const kind = SOURCE_KINDS[source.kind] ?? SOURCE_KINDS.sql_text
  const Icon = kind.icon
  const { stats } = source
  const vision = stats?.vision
  return (
    <li className="p-3 bg-gray-900/60 rounded-lg border border-gray-700 space-y-2">
      <div className="flex items-center gap-3">
        <Icon className="w-4 h-4 text-gray-400 shrink-0" />
        <div className="flex-1 min-w-0">
          <p className="text-sm font-medium truncate">{source.filename ?? kind.label}</p>
          <p className="text-xs text-gray-500">
            {kind.label} · {formatTime(source.created_at)}
          </p>
        </div>
        <StatusBadge status={source.status} />
      </div>

      {source.status === "ready" && stats && <p className="text-xs text-gray-300">{statsLine(stats)}</p>}
      {vision && (
        <p className="text-xs text-gray-500">
          Vision: {source.model} · {(vision.latency_ms / 1000).toFixed(1)} s
          {vision.cost_usd != null && ` · ${formatCost(vision.cost_usd)}`}
        </p>
      )}
      {source.error && (
        <p className="text-xs text-red-400 flex items-start gap-1.5">
          <AlertCircle className="w-3.5 h-3.5 mt-0.5 shrink-0" />
          {source.error}
        </p>
      )}
      {source.warnings?.length > 0 && (
        <details className="text-xs">
          <summary className="cursor-pointer text-amber-300 inline-flex items-center gap-1.5">
            <AlertTriangle className="w-3.5 h-3.5" />
            {plural(source.warnings.length, "warning")}
          </summary>
          <ul className="mt-1 ml-5 list-disc text-amber-200/80 space-y-0.5">
            {source.warnings.map((w, i) => (
              <li key={i}>{w}</li>
            ))}
          </ul>
        </details>
      )}
      {source.transcription && (
        <details className="text-xs">
          <summary className="cursor-pointer text-gray-400">What the vision model read</summary>
          <pre className="mt-2 p-3 bg-gray-950 rounded border border-gray-700 text-green-400 overflow-x-auto max-h-64">
            {source.transcription}
          </pre>
        </details>
      )}
    </li>
  )
}

function SourceList({ sources }) {
  return (
    <section className="bg-gray-800 rounded-xl p-6 border border-gray-700">
      <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
        <FileText className="w-5 h-5 text-cyan-400" />
        Uploads
        {sources.length > 0 && <span className="text-xs text-gray-400 font-normal">({sources.length})</span>}
      </h3>
      {sources.length === 0 ? (
        <p className="text-sm text-gray-400">Nothing uploaded yet.</p>
      ) : (
        <ul className="space-y-2 max-h-[28rem] overflow-y-auto pr-1">
          {sources.map((s) => (
            <SourceRow key={s.id} source={s} />
          ))}
        </ul>
      )}
    </section>
  )
}

function Flag({ children, title }) {
  return (
    <span title={title} className="px-1 py-px rounded bg-gray-700 text-gray-300 text-[10px] leading-4">
      {children}
    </span>
  )
}

function TableCard({ table, tablesById, onDelete }) {
  return (
    <article className="bg-gray-900/60 border border-gray-700 rounded-lg overflow-hidden" data-testid="table-card">
      <header className="flex items-start gap-2 px-4 py-3 border-b border-gray-700">
        <Table2 className="w-4 h-4 text-cyan-400 mt-0.5 shrink-0" />
        <div className="flex-1 min-w-0">
          <h4 className="font-mono text-sm font-semibold truncate">
            {table.db_schema && <span className="text-gray-500">{table.db_schema}.</span>}
            {table.name}
          </h4>
          {table.comment && <p className="text-xs text-gray-400 mt-0.5">{table.comment}</p>}
          {table.description && (
            <p className="text-xs text-gray-300 mt-1" title="Written by the LLM for the search index">
              {table.description}
            </p>
          )}
          {table.synonyms.length > 0 && (
            <div className="flex flex-wrap gap-1 mt-1.5" title="Synonyms indexed for search">
              {table.synonyms.map((word) => (
                <span key={word} className="text-[10px] px-1.5 py-px rounded-full bg-cyan-500/10 text-cyan-300 border border-cyan-500/20">
                  {word}
                </span>
              ))}
            </div>
          )}
        </div>
        {table.inferred && (
          <span
            className="text-[10px] uppercase tracking-wide px-1.5 py-0.5 rounded bg-amber-500/15 text-amber-300 border border-amber-500/30"
            title="Only seen in queries: its columns are guesses. Upload its CREATE TABLE to replace them."
          >
            inferred
          </span>
        )}
        <button
          onClick={onDelete}
          title="Remove this table"
          aria-label={`Remove table ${table.name}`}
          className="text-gray-500 hover:text-red-400 p-1 -m-1 rounded transition-colors"
        >
          <Trash2 className="w-4 h-4" />
        </button>
      </header>

      <ul className="divide-y divide-gray-800 text-xs font-mono">
        {table.columns.map((c) => (
          <li key={c.name} className="flex items-center gap-2 px-4 py-1.5" title={c.comment ?? undefined}>
            <span className="w-4 shrink-0">
              {c.is_primary_key && <KeyRound className="w-3.5 h-3.5 text-yellow-400" aria-label="primary key" />}
            </span>
            <span className={c.inferred ? "italic text-gray-400" : "text-gray-100"}>{c.name}</span>
            <span className="text-cyan-300/80 truncate">{c.data_type ?? "?"}</span>
            <span className="ml-auto flex gap-1 shrink-0">
              {!c.nullable && !c.is_primary_key && <Flag>NOT NULL</Flag>}
              {c.is_unique && !c.is_primary_key && <Flag>UNIQUE</Flag>}
              {c.default && <Flag title={`DEFAULT ${c.default}`}>DEFAULT</Flag>}
              {c.comment && <Flag title={c.comment}>NOTE</Flag>}
            </span>
          </li>
        ))}
      </ul>

      {table.relationships.length > 0 && (
        <ul className="px-4 py-2 border-t border-gray-700 space-y-1 text-xs">
          {table.relationships.map((r) => {
            const target = r.to_table_id ? tablesById.get(r.to_table_id) : null
            return (
              <li
                key={`${r.columns.join(",")}->${r.to_table}(${r.to_columns.join(",")})`}
                className="flex items-center gap-1.5 font-mono flex-wrap"
              >
                <Link2 className="w-3.5 h-3.5 text-purple-400 shrink-0" />
                <span>{r.columns.join(", ")}</span>
                <ArrowRight className="w-3 h-3 text-gray-500" />
                <span
                  className={target ? "text-purple-300" : "text-amber-300"}
                  title={target ? undefined : "This table hasn't been uploaded (yet)"}
                >
                  {target?.name ?? r.to_table}({r.to_columns.join(", ")})
                </span>
                {r.inferred && <span className="text-gray-500 italic font-sans">guessed from a join</span>}
              </li>
            )
          })}
        </ul>
      )}
    </article>
  )
}

function TableExplorer({ tables, onDeleteTable }) {
  const [query, setQuery] = useState("")
  const tablesById = useMemo(() => new Map(tables.map((t) => [t.id, t])), [tables])
  const q = query.trim().toLowerCase()
  const shown = q
    ? tables.filter((t) => t.name.toLowerCase().includes(q) || t.columns.some((c) => c.name.toLowerCase().includes(q)))
    : tables

  return (
    <section className="bg-gray-800 rounded-xl p-6 border border-gray-700">
      <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
        <h3 className="text-lg font-semibold flex items-center gap-2">
          <Table2 className="w-5 h-5 text-purple-400" />
          Tables
          {tables.length > 0 && <span className="text-xs text-gray-400 font-normal">({tables.length})</span>}
        </h3>
        {tables.length > 0 && (
          <div className="relative w-full sm:w-64">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search tables or columns…"
              className={`${inputClass} pl-9`}
              aria-label="Search tables"
            />
          </div>
        )}
      </div>
      {tables.length === 0 ? (
        <p className="text-sm text-gray-400">No tables yet. Add this database's SQL above.</p>
      ) : shown.length === 0 ? (
        <p className="text-sm text-gray-400">No table or column matches “{query}”.</p>
      ) : (
        <div className="grid grid-cols-1 2xl:grid-cols-2 gap-4">
          {shown.map((t) => (
            <TableCard key={t.id} table={t} tablesById={tablesById} onDelete={() => onDeleteTable(t)} />
          ))}
        </div>
      )}
    </section>
  )
}

function GettingStarted() {
  const steps = [
    ["Create a schema", "Give it a name and pick the SQL dialect your database speaks."],
    ["Add its SQL", "Paste DDL, upload a .sql dump, or a screenshot of an ER diagram."],
    ["Ask questions", "In the Query Builder, pick the schema and the tables to ground the answer."],
  ]
  return (
    <div className="bg-gray-800 rounded-xl p-8 border border-gray-700">
      <h2 className="text-xl font-semibold mb-2 flex items-center gap-2">
        <Database className="w-5 h-5 text-cyan-400" />
        Teach SQLAssist your database
      </h2>
      <p className="text-sm text-gray-400 mb-6">
        Without a schema the AI has to guess table and column names. With one, it uses the real ones and every
        answer is checked against them.
      </p>
      <ol className="grid gap-4 md:grid-cols-3">
        {steps.map(([title, text], i) => (
          <li key={title} className="p-4 bg-gray-900/60 rounded-lg border border-gray-700">
            <span className="w-6 h-6 rounded-full bg-cyan-600 text-xs font-bold inline-flex items-center justify-center mb-2">
              {i + 1}
            </span>
            <p className="font-medium text-sm">{title}</p>
            <p className="text-xs text-gray-400 mt-1">{text}</p>
          </li>
        ))}
      </ol>
    </div>
  )
}

export default function DatabaseSetupPage() {
  const [sidebarOpen, setSidebarOpen] = useState(true)
  const [params, setParams] = useSearchParams()
  const [schemas, setSchemas] = useState([])
  const [listState, setListState] = useState({ loading: true, error: "" })
  const [detail, setDetail] = useState(null) // SchemaDetail of the selected schema
  const [sources, setSources] = useState([]) // its uploads, newest first
  const [detailError, setDetailError] = useState("")
  const [notice, setNotice] = useState("")
  const [reloadKey, setReloadKey] = useState(0) // bump = refetch the selected schema
  const [loads, setLoads] = useState(0) // finished fetches (success or not): drives polling

  // The selection lives in the URL (?schema=<id>), so links and reloads keep it.
  const paramId = params.get("schema")
  const selectedId = schemas.some((s) => s.id === paramId) ? paramId : (schemas[0]?.id ?? null)
  const shown = detail?.id === selectedId ? detail : null
  // Poll while an upload is being processed OR the search index is being (re)built.
  const busy = sources.some((s) => BUSY.has(s.status)) || INDEX_BUSY.has(detail?.index_status)
  const reload = () => setReloadKey((k) => k + 1)

  const sidebarItems = [
    { icon: <Database className="w-5 h-5" />, label: "Query Builder", to: "/querybuilder" },
    { icon: <Settings className="w-5 h-5" />, label: "Database Setup", active: true, to: "/database-setup" },
    { icon: <Code className="w-5 h-5" />, label: "SQL Assistants", to: "/sql-assistants" },
    { icon: <BarChart3 className="w-5 h-5" />, label: "Dashboard", to: "/user-dashboard" },
    { icon: <User className="w-5 h-5" />, label: "Account", to: "/account" },
    { icon: <CreditCard className="w-5 h-5" />, label: "Pricing", to: "/dashboard/pricing" },
    { icon: <Settings className="w-5 h-5" />, label: "Settings", to: "/settings" },
    { icon: <DollarSign className="w-5 h-5" />, label: "Refer & Earn", to: "/dashboard/refer" },
    { icon: <FileText className="w-5 h-5" />, label: "Documentation", to: "/dashboard/docs" },
  ]

  // 1) The user's schemas, once.
  useEffect(() => {
    let ignore = false // a late answer must not overwrite state after unmount
    api
      .listSchemas()
      .then((list) => {
        if (ignore) return
        setSchemas(list)
        setListState({ loading: false, error: "" })
      })
      .catch((err) => !ignore && setListState({ loading: false, error: err.message }))
    return () => {
      ignore = true
    }
  }, [])

  // 2) The selected schema's tables + uploads. Runs again on reload() and on every poll.
  useEffect(() => {
    if (!selectedId) return
    let ignore = false // the user may switch schemas before this answer arrives
    Promise.all([api.getSchema(selectedId), api.listSchemaSources(selectedId)])
      .then(([schema, uploads]) => {
        if (ignore) return
        setDetail(schema)
        setSources(uploads)
        setDetailError("")
        // keep the list's status and counts in sync with what we just loaded
        setSchemas((list) => list.map((s) => (s.id === schema.id ? { ...s, ...summaryOf(schema) } : s)))
      })
      .catch((err) => !ignore && setDetailError(err.message))
      .finally(() => !ignore && setLoads((n) => n + 1))
    return () => {
      ignore = true
    }
  }, [selectedId, reloadKey])

  // 3) Polling: while an upload is queued or processing, refetch every POLL_MS.
  //    Each finished fetch bumps `loads`, which schedules the next tick (a failed fetch
  //    too, so a network blip doesn't stop it); it stops once nothing is busy.
  useEffect(() => {
    if (!busy) return
    const timer = setTimeout(() => setReloadKey((k) => k + 1), POLL_MS)
    return () => clearTimeout(timer)
  }, [busy, loads])

  const selectSchema = (id) => {
    setNotice("")
    setDetailError("")
    setParams({ schema: id })
  }

  const handleCreated = (schema) => {
    setSchemas((list) => [...list, schema].sort(byName))
    selectSchema(schema.id)
  }

  const handleUploaded = (source) => {
    // Same content uploaded twice -> the server returns the existing source (idempotent).
    const existing = sources.some((s) => s.id === source.id)
    setNotice(
      existing && source.status === "ready"
        ? "This exact SQL was already uploaded to this schema, so nothing changed."
        : "",
    )
    reload()
  }

  const handleDeleteSchema = async () => {
    if (!window.confirm(`Delete "${shown.name}" with all its tables and uploads? This cannot be undone.`)) return
    try {
      await api.deleteSchema(shown.id)
      setSchemas((list) => list.filter((s) => s.id !== shown.id))
      setDetail(null)
      setSources([])
      setParams({})
    } catch (err) {
      setDetailError(err.message)
    }
  }

  const handleRebuildIndex = async () => {
    try {
      await api.reindexSchema(shown.id) // 202: the job runs in the background
      reload() // shows "pending", then polling follows the job
    } catch (err) {
      setDetailError(err.message)
    }
  }

  const handleDeleteTable = async (table) => {
    if (!window.confirm(`Remove table "${table.name}" from this schema?`)) return
    try {
      await api.deleteSchemaTable(shown.id, table.id)
      reload()
    } catch (err) {
      setDetailError(err.message)
    }
  }

  return (
    <div className="min-h-screen bg-gray-900 text-white flex">
      {/* Sidebar */}
      <motion.div
        initial={{ x: -300 }}
        animate={{ x: sidebarOpen ? 0 : -250 }}
        transition={{ duration: 0.3 }}
        className="w-64 bg-gray-800 border-r border-gray-700 flex flex-col relative z-20 shrink-0"
      >
        {/* Logo */}
        <div className="p-6 border-b border-gray-700">
          <div className="flex items-center space-x-3">
            <div className="w-8 h-8 bg-gradient-to-r from-cyan-400 to-blue-500 rounded-lg flex items-center justify-center">
              <Database className="w-5 h-5 text-white" />
            </div>
            <span className="text-xl font-bold bg-gradient-to-r from-cyan-400 to-blue-500 bg-clip-text text-transparent">
              SQLAssist
            </span>
          </div>
        </div>

        {/* Navigation */}
        <nav className="flex-1 p-4">
          <ul className="space-y-2">
            {sidebarItems.map((item) => (
              <li key={item.label}>
                <Link
                  to={item.to}
                  className={`flex items-center space-x-3 px-4 py-3 rounded-lg transition-colors ${
                    item.active ? "bg-blue-600 text-white" : "text-gray-300 hover:bg-gray-700 hover:text-white"
                  }`}
                >
                  {item.icon}
                  <span>{item.label}</span>
                </Link>
              </li>
            ))}
          </ul>
        </nav>

        {/* User Profile */}
        <div className="p-4 border-t border-gray-700">
          <div className="flex items-center space-x-3">
            <div className="w-8 h-8 bg-gradient-to-r from-purple-400 to-pink-500 rounded-full flex items-center justify-center">
              <span className="text-sm font-semibold">M</span>
            </div>
            <div className="flex-1">
              <p className="text-sm font-medium">mergist1</p>
              <p className="text-xs text-gray-400">Free Plan</p>
            </div>
          </div>
        </div>
      </motion.div>

      {/* Main Content */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Header */}
        <header className="bg-gray-800 border-b border-gray-700 px-6 py-4 flex items-center justify-between">
          <div className="flex items-center space-x-4">
            <button
              onClick={() => setSidebarOpen(!sidebarOpen)}
              className="text-gray-400 hover:text-white transition-colors lg:hidden"
            >
              {sidebarOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
            </button>
            <h1 className="text-2xl font-bold">Database Setup</h1>
          </div>
          <Link
            to="/"
            className="inline-flex items-center space-x-2 text-cyan-400 hover:text-cyan-300 transition-colors"
          >
            <ArrowLeft className="w-4 h-4" />
            <span>Back to Home</span>
          </Link>
        </header>

        {/* Content */}
        <div className="flex-1 p-6 grid grid-cols-1 lg:grid-cols-[20rem_minmax(0,1fr)] gap-6 items-start">
          {/* Left: create + list */}
          <div className="space-y-6">
            <NewSchemaForm onCreated={handleCreated} />
            <SchemaList
              schemas={schemas}
              selectedId={selectedId}
              onSelect={selectSchema}
              loading={listState.loading}
              error={listState.error}
            />
          </div>

          {/* Right: the selected schema */}
          <div className="space-y-6 min-w-0">
            {!listState.loading && schemas.length === 0 ? (
              <GettingStarted />
            ) : detailError && !shown ? (
              <div className="bg-gray-800 rounded-xl p-6 border border-red-500/40 text-sm text-red-400 flex items-center gap-3">
                <AlertCircle className="w-5 h-5 shrink-0" />
                <span className="flex-1">{detailError}</span>
                <button onClick={reload} className="text-cyan-400 hover:text-cyan-300 inline-flex items-center gap-1">
                  <RefreshCw className="w-4 h-4" /> Retry
                </button>
              </div>
            ) : !shown ? (
              <div className="py-16 text-center text-gray-400 flex items-center justify-center gap-2">
                <Loader2 className="w-5 h-5 animate-spin" /> Loading schema…
              </div>
            ) : (
              <>
                {/* Schema header */}
                <div className="bg-gray-800 rounded-xl p-6 border border-gray-700 flex flex-wrap items-start gap-4">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-3 flex-wrap">
                      <h2 className="text-xl font-semibold truncate">{shown.name}</h2>
                      <span className="text-xs bg-purple-600 text-white px-2 py-1 rounded-full">{shown.dialect}</span>
                      <StatusBadge status={shown.status} />
                    </div>
                    {shown.description && <p className="text-sm text-gray-400 mt-1">{shown.description}</p>}
                    <p className="text-xs text-gray-500 mt-2">
                      {plural(shown.table_count, "table")} · {plural(shown.column_count, "column")} · updated{" "}
                      {formatTime(shown.updated_at)}
                    </p>
                    <IndexStatusBar schema={shown} onRebuild={handleRebuildIndex} />
                  </div>
                  <div className="flex items-center gap-2">
                    {shown.table_count > 0 ? (
                      <Link
                        to={`/querybuilder?schema=${shown.id}`}
                        className="bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-700 hover:to-purple-700 px-4 py-2 rounded-lg font-medium text-sm transition-all inline-flex items-center gap-2"
                      >
                        <Sparkles className="w-4 h-4" />
                        Use in Query Builder
                      </Link>
                    ) : (
                      <span
                        className="bg-gray-700 text-gray-400 px-4 py-2 rounded-lg text-sm cursor-not-allowed"
                        title="Add SQL with at least one table first"
                      >
                        Use in Query Builder
                      </span>
                    )}
                    <button
                      onClick={handleDeleteSchema}
                      title="Delete this schema"
                      aria-label="Delete schema"
                      className="p-2 text-red-400 hover:text-red-300 hover:bg-red-400/10 rounded-lg transition-colors"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                </div>

                {(notice || detailError) && (
                  <p
                    className={`text-sm px-4 py-3 rounded-lg border ${
                      detailError
                        ? "text-red-400 border-red-500/40 bg-red-500/5"
                        : "text-cyan-300 border-cyan-500/30 bg-cyan-500/5"
                    }`}
                  >
                    {detailError || notice}
                  </p>
                )}

                <div className="grid grid-cols-1 xl:grid-cols-2 gap-6 items-start">
                  <AddSourcePanel key={shown.id} schemaId={shown.id} onUploaded={handleUploaded} />
                  <SourceList sources={sources} />
                </div>

                {shown.table_count > 0 && (
                  <SchemaSearchPanel key={`search-${shown.id}`} schemaId={shown.id} indexStatus={shown.index_status} />
                )}

                <TableExplorer key={`tables-${shown.id}`} tables={shown.tables} onDeleteTable={handleDeleteTable} />
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
