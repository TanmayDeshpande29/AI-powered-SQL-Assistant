import { CheckCircle2, XCircle, AlertTriangle, Cpu, Timer, Coins, Brain, Database } from "lucide-react"
import { formatCost } from "../lib/format"

// Everything the backend tells us about one LLM answer (an LLMResponse):
// the model's explanation and assumptions, the SQL syntax check, the check against
// the uploaded schema, and the run's metrics.

const formatModel = (model) => model?.replace(/^openai\//, "") ?? "unknown model"

// Which tables the answer was grounded in (only when a schema was selected).
function SchemaGrounding({ result }) {
  if (!result.schema_id) return null
  const tables = result.schema_tables ?? []
  return (
    <p className="text-xs text-gray-400 flex items-start gap-1.5">
      <Database className="w-3.5 h-3.5 mt-0.5 shrink-0 text-cyan-400" />
      <span>
        Grounded in {tables.length} table{tables.length === 1 ? "" : "s"}: <span className="font-mono">{tables.join(", ")}</span>
        {result.schema_truncated && (
          <span className="text-amber-400"> (schema too large: some tables were left out; tick the ones you need)</span>
        )}
      </span>
    </p>
  )
}

// Names the SQL uses that don't exist in the uploaded schema = likely hallucinations.
function SchemaIssues({ validation }) {
  if (!validation?.schema_checked) return null
  if (!validation.schema_issues.length) {
    return (
      <span className="inline-flex items-center gap-1 text-xs px-2 py-1 rounded-full bg-green-500/15 text-green-400 border border-green-500/30">
        <CheckCircle2 className="w-3.5 h-3.5" />
        All tables and columns exist in the schema
      </span>
    )
  }
  return (
    <div className="text-xs px-3 py-2 rounded-lg bg-amber-500/10 text-amber-300 border border-amber-500/30">
      <p className="flex items-center gap-1 font-medium mb-1">
        <AlertTriangle className="w-3.5 h-3.5" />
        Not found in your schema:
      </p>
      <ul className="list-disc list-inside font-mono space-y-0.5">
        {validation.schema_issues.map((issue) => (
          <li key={issue}>{issue}</li>
        ))}
      </ul>
    </div>
  )
}

function ValidationBadge({ validation }) {
  if (!validation) return null
  if (validation.valid) {
    const dialect = validation.dialect ? ` ${validation.dialect}` : ""
    return (
      <span className="inline-flex items-center gap-1 text-xs px-2 py-1 rounded-full bg-green-500/15 text-green-400 border border-green-500/30">
        <CheckCircle2 className="w-3.5 h-3.5" />
        Valid{dialect} syntax · {validation.statement_types.join(", ")}
      </span>
    )
  }
  return (
    <span
      className="inline-flex items-center gap-1 text-xs px-2 py-1 rounded-full bg-red-500/15 text-red-400 border border-red-500/30"
      title={validation.errors.join("\n")}
    >
      <XCircle className="w-3.5 h-3.5" />
      Syntax problem: {validation.errors[0]}
    </span>
  )
}

export function LLMMetrics({ result }) {
  if (!result) return null
  const { usage } = result
  const cost = formatCost(result.cost_usd)
  return (
    <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-gray-400">
      <span className="inline-flex items-center gap-1" title={`Prompt ${result.prompt_version}`}>
        <Cpu className="w-3.5 h-3.5" />
        {formatModel(result.model)} · {result.reasoning_effort} effort
      </span>
      <span className="inline-flex items-center gap-1">
        <Timer className="w-3.5 h-3.5" />
        {(result.latency_ms / 1000).toFixed(1)} s
      </span>
      {usage && (
        <span
          className="inline-flex items-center gap-1"
          title={`${usage.input_tokens} input + ${usage.output_tokens} output tokens (of which ${usage.reasoning_tokens} hidden reasoning)`}
        >
          <Brain className="w-3.5 h-3.5" />
          {usage.total_tokens} tokens ({usage.reasoning_tokens} reasoning)
        </span>
      )}
      {cost && (
        <span className="inline-flex items-center gap-1" title="Estimated at the provider's list price">
          <Coins className="w-3.5 h-3.5" />
          {cost}
        </span>
      )}
      {result.fallback_used && (
        <span className="inline-flex items-center gap-1 text-amber-400" title="The main model was rate-limited">
          <AlertTriangle className="w-3.5 h-3.5" />
          answered by fallback model
        </span>
      )}
    </div>
  )
}

export default function LLMResultDetails({ result }) {
  if (!result) return null
  return (
    <div className="mt-4 space-y-3 border-t border-gray-700 pt-4">
      <div className="flex flex-wrap items-start gap-2">
        <ValidationBadge validation={result.validation} />
        <SchemaIssues validation={result.validation} />
      </div>
      <SchemaGrounding result={result} />
      {result.explanation && <p className="text-sm text-gray-300">{result.explanation}</p>}
      {result.assumptions?.length > 0 && (
        <div className="text-sm">
          <p className="text-gray-400 mb-1">Assumptions (check these against your schema):</p>
          <ul className="list-disc list-inside text-gray-300 space-y-0.5">
            {result.assumptions.map((assumption) => (
              <li key={assumption}>{assumption}</li>
            ))}
          </ul>
        </div>
      )}
      <LLMMetrics result={result} />
    </div>
  )
}
