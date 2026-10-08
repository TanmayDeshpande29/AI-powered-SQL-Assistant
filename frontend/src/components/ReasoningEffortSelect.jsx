// Speed <-> quality switch for reasoning models (gpt-oss "reasoning effort").
// null = let the server pick the default for this task.
const OPTIONS = [
  { value: null, label: "Auto", hint: "Server default for this task" },
  { value: "low", label: "Fast", hint: "Least thinking: fastest and cheapest" },
  { value: "medium", label: "Balanced", hint: "Moderate thinking" },
  { value: "high", label: "Thorough", hint: "Most thinking: slowest, best for tricky queries" },
]

export default function ReasoningEffortSelect({ value, onChange, disabled = false }) {
  return (
    <div className="flex items-center gap-2" role="radiogroup" aria-label="Reasoning effort">
      <span className="text-xs text-gray-400">Thinking:</span>
      <div className="flex rounded-lg border border-gray-600 overflow-hidden">
        {OPTIONS.map((option) => {
          const active = option.value === value
          return (
            <button
              key={option.label}
              type="button"
              role="radio"
              aria-checked={active}
              title={option.hint}
              disabled={disabled}
              onClick={() => onChange(option.value)}
              className={`px-2.5 py-1 text-xs transition-colors ${
                active ? "bg-cyan-600 text-white" : "bg-gray-800 text-gray-300 hover:bg-gray-700"
              } disabled:opacity-50`}
            >
              {option.label}
            </button>
          )
        })}
      </div>
    </div>
  )
}
