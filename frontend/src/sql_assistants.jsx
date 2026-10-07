
import { motion, AnimatePresence } from "framer-motion"
import { useState, useRef } from "react"
import {
  Database,
  Play,
  Mic,
  MicOff,
  Copy,
  Download,
  Settings,
  User,
  CreditCard,
  FileText,
  BarChart3,
  DollarSign,
  Menu,
  X,
  Code,
  ArrowLeft,
  Bug,
  HelpCircle,
  Zap,
  MessageSquare,
  Volume2,
  VolumeX,
  RefreshCw,
} from "lucide-react"
import { Link } from "react-router";
import { api } from "./lib/api";

export default function SQLAssistantsPage() {
  // const [activeMode, setActiveMode] = useState("natural-language")
  const [activeMode, setActiveMode] = useState("debug-sql")
  const [sidebarOpen, setSidebarOpen] = useState(true)
  const [selectedDialect, setSelectedDialect] = useState("MySQL")
  const [isListening, setIsListening] = useState(false)
  const [isProcessing, setIsProcessing] = useState(false)
  const [isSpeaking, setIsSpeaking] = useState(false)

  // Input states for each mode
  const [inputs, setInputs] = useState({
     "debug-sql": "",
    "explain-sql": "",
    "optimize-sql": "",
  })
  
  const [outputs, setOutputs] = useState({
    "debug-sql": "",
    "explain-sql": "",
    "optimize-sql": "",
  })

  const speechRecognitionRef = useRef(null)

  const sqlDialects = [
    { value: "MySQL", label: "MySQL", icon: "🐬" },
    { value: "PostgreSQL", label: "PostgreSQL", icon: "🐘" },
    { value: "SQLite", label: "SQLite", icon: "🪶" },
    { value: "SQL Server", label: "SQL Server", icon: "🏢" },
    { value: "Oracle", label: "Oracle", icon: "🔴" },
    { value: "Trino", label: "Trino", icon: "⚡" },
    { value: "Spark SQL", label: "Spark SQL", icon: "✨" },
  ]

  const assistantModes = [
    {
      id: "debug-sql",
      title: "Debug SQL",
      icon: <Bug className="w-5 h-5" />,
      description: "Find and fix issues in your SQL queries",
      color: "from-red-500 to-pink-600",
      placeholder: "Paste your SQL query that needs debugging...",
    },
    {
      id: "explain-sql",
      title: "Explain SQL",
      icon: <HelpCircle className="w-5 h-5" />,
      description: "Get detailed explanations of SQL queries",
      color: "from-green-500 to-emerald-600",
      placeholder: "Paste your SQL query to get a detailed explanation...",
    },
    {
      id: "optimize-sql",
      title: "Optimize SQL",
      icon: <Zap className="w-5 h-5" />,
      description: "Improve query performance and efficiency",
      color: "from-purple-500 to-violet-600",
      placeholder: "Paste your SQL query to optimize for better performance...",
    },
  ]

  const sidebarItems = [
    { icon: <Database className="w-5 h-5" />, label: "Query Builder", active: false, to: "/querybuilder" },
    { icon: <Settings className="w-5 h-5" />, label: "Database Setup", active: false, to: "/database-setup" },
    { icon: <Code className="w-5 h-5" />, label: "SQL Assistants", active: true, to: "/sql-assistants" },
    { icon: <BarChart3 className="w-5 h-5" />, label: "Dashboard", to: "/user-dashboard" },
    { icon: <User className="w-5 h-5" />, label: "Account", to: "/account" },
    { icon: <CreditCard className="w-5 h-5" />, label: "Pricing", to: "/dashboard/pricing" },
    { icon: <Settings className="w-5 h-5" />, label: "Settings", to: "/settings" },
    { icon: <DollarSign className="w-5 h-5" />, label: "Refer & Earn", to: "/dashboard/refer" },
    { icon: <FileText className="w-5 h-5" />, label: "Documentation", to: "/dashboard/docs" },
  ]

  const updateInput = (mode, value) => {
    setInputs((prev) => ({ ...prev, [mode]: value }))
  }

  const handleRun = async (mode) => {
    setIsProcessing(true);
    try {
      // UI modes are "debug-sql" / "explain-sql" / "optimize-sql"; the API expects "debug" etc.
      // History is saved by the backend in the same request (no second call to fail).
      const data = await api.assistSql({
        mode: mode.replace("-sql", ""),
        sql: inputs[mode],
        dialect: selectedDialect,
      })
      setOutputs((prev) => ({ ...prev, [mode]: data.output }));
    } catch (err) {
      setOutputs((prev) => ({ ...prev, [mode]: `Error: ${err.message}` }));
    } finally {
      setIsProcessing(false);
    }
  }


  const handleVoiceInput = () => {
    if (!("webkitSpeechRecognition" in window) && !("SpeechRecognition" in window)) {
      alert("Speech recognition not supported in this browser")
      return
    }

    if (isListening) {
      speechRecognitionRef.current?.stop()
      setIsListening(false)
      return
    }

    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition
    const recognition = new SpeechRecognition()

    recognition.continuous = false
    recognition.interimResults = false
    recognition.lang = "en-US"

    recognition.onstart = () => {
      setIsListening(true)
    }

    recognition.onresult = (event) => {
      const transcript = event.results[0][0].transcript
      updateInput(activeMode, transcript)
      setIsListening(false)
    }

    recognition.onerror = () => {
      setIsListening(false)
    }

    recognition.onend = () => {
      setIsListening(false)
    }

    speechRecognitionRef.current = recognition
    recognition.start()
  }

  const handleTextToSpeech = (text) => {
    if (!("speechSynthesis" in window)) {
      alert("Text-to-speech not supported in this browser")
      return
    }

    if (isSpeaking) {
      window.speechSynthesis.cancel()
      setIsSpeaking(false)
      return
    }

    const utterance = new SpeechSynthesisUtterance(text)
    utterance.rate = 0.8
    utterance.pitch = 1
    utterance.volume = 1

    utterance.onstart = () => setIsSpeaking(true)
    utterance.onend = () => setIsSpeaking(false)
    utterance.onerror = () => setIsSpeaking(false)

    window.speechSynthesis.speak(utterance)
  }

  const copyToClipboard = (text) => {
    navigator.clipboard.writeText(text)
  }

  const currentMode = assistantModes.find((mode) => mode.id === activeMode)

  return (
    <div className="min-h-screen bg-gray-900 text-white flex">
      {/* Sidebar */}
      <motion.div
        initial={{ x: -300 }}
        animate={{ x: sidebarOpen ? 0 : -250 }}
        transition={{ duration: 0.3 }}
        className="w-64 bg-gray-800 border-r border-gray-700 flex flex-col relative z-20"
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
            {sidebarItems.map((item, index) => (
              <li key={index}>
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
      <div className="flex-1 flex flex-col">
        {/* Header */}
        <header className="bg-gray-800 border-b border-gray-700 px-6 py-4 flex items-center justify-between">
          <div className="flex items-center space-x-4">
            <button
              onClick={() => setSidebarOpen(!sidebarOpen)}
              className="text-gray-400 hover:text-white transition-colors lg:hidden"
            >
              {sidebarOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
            </button>
            <h1 className="text-2xl font-bold">SQL Assistants</h1>
          </div>
          <Link
            to="/"
            className="inline-flex items-center space-x-2 text-cyan-400 hover:text-cyan-300 transition-colors"
          >
            <ArrowLeft className="w-4 h-4" />
            <span>Back to Home</span>
          </Link>
        </header>

        {/* Mode Tabs */}
        <div className="bg-gray-800 border-b border-gray-700 px-6 py-4">
          <div className="flex flex-wrap gap-2">
            {assistantModes.map((mode) => (
              <motion.button
                key={mode.id}
                onClick={() => setActiveMode(mode.id)}
                whileHover={{ scale: 1.02 }}
                whileTap={{ scale: 0.98 }}
                className={`flex items-center space-x-2 px-4 py-2 rounded-lg font-medium transition-all duration-300 ${
                  activeMode === mode.id
                    ? `bg-gradient-to-r ${mode.color} text-white shadow-lg`
                    : "bg-gray-700 text-gray-300 hover:bg-gray-600 hover:text-white"
                }`}
              >
                {mode.icon}
                <span className="hidden sm:inline">{mode.title}</span>
              </motion.button>
            ))}
          </div>
        </div>

        {/* Content */}
        <div className="flex-1 p-6">
          <div className="max-w-6xl mx-auto grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Input Panel */}
            <motion.div
              key={`input-${activeMode}`}
              initial={{ opacity: 0, x: -20 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ duration: 0.3 }}
              className="bg-gray-800 rounded-xl p-6 border border-gray-700"
            >
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center space-x-3">
                  <div className={`p-2 rounded-lg bg-gradient-to-r ${currentMode?.color}`}>{currentMode?.icon}</div>
                  <div>
                    <h2 className="text-xl font-semibold">{currentMode?.title}</h2>
                    <p className="text-sm text-gray-400">{currentMode?.description}</p>
                  </div>
                </div>

                {/* SQL Dialect Selector */}
                <select
                  value={selectedDialect}
                  onChange={(e) => setSelectedDialect(e.target.value)}
                  className="bg-gray-700 border border-gray-600 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-cyan-500 transition-colors"
                >
                  {sqlDialects.map((dialect) => (
                    <option key={dialect.value} value={dialect.value}>
                      {dialect.icon} {dialect.label}
                    </option>
                  ))}
                </select>
              </div>

              {/* Input Area */}
              <div className="relative mb-4">
                <textarea
                  value={inputs[activeMode]}
                  onChange={(e) => updateInput(activeMode, e.target.value)}
                  placeholder={currentMode?.placeholder}
                  className="w-full h-48 bg-gray-700 border border-gray-600 rounded-lg px-4 py-3 text-white placeholder-gray-400 focus:outline-none focus:border-cyan-500 transition-colors resize-none"
                />

                {/* Voice Input Button (only for natural language mode) */}
                {activeMode === "natural-language" && (
                  <button
                    onClick={handleVoiceInput}
                    className={`absolute bottom-3 right-3 p-2 rounded-lg transition-colors ${
                      isListening
                        ? "bg-red-600 hover:bg-red-700 text-white"
                        : "bg-gray-600 hover:bg-gray-500 text-gray-300"
                    }`}
                    title={isListening ? "Stop listening" : "Start voice input"}
                  >
                    {isListening ? <MicOff className="w-4 h-4" /> : <Mic className="w-4 h-4" />}
                  </button>
                )}
              </div>

              {/* Action Buttons */}
              <div className="flex items-center justify-between">
                <div className="flex items-center space-x-2">
                  <span className="text-sm text-gray-400">Dialect:</span>
                  <span className={`text-sm px-2 py-1 rounded bg-gradient-to-r ${currentMode?.color} text-white`}>
                    {selectedDialect}
                  </span>
                </div>

                <motion.button
                  whileHover={{ scale: 1.02 }}
                  whileTap={{ scale: 0.98 }}
                  onClick={() => handleRun(activeMode)}
                  disabled={isProcessing || !inputs[activeMode].trim()}
                  className={`bg-gradient-to-r ${currentMode?.color} hover:opacity-90 disabled:opacity-50 disabled:cursor-not-allowed px-6 py-3 rounded-lg font-semibold transition-all duration-300 flex items-center space-x-2`}
                >
                  {isProcessing ? (
                    <>
                      <RefreshCw className="w-4 h-4 animate-spin" />
                      <span>Processing...</span>
                    </>
                  ) : (
                    <>
                      <Play className="w-4 h-4" />
                      <span>Run</span>
                    </>
                  )}
                </motion.button>
              </div>
            </motion.div>

            {/* Output Panel */}
            <motion.div
              key={`output-${activeMode}`}
              initial={{ opacity: 0, x: 20 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ duration: 0.3 }}
              className="bg-gray-800 rounded-xl p-6 border border-gray-700"
            >
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-lg font-semibold flex items-center space-x-2">
                  <Code className="w-5 h-5 text-cyan-400" />
                  <span>Output</span>
                </h3>

                {outputs[activeMode] && (
                  <div className="flex items-center space-x-2">
                    <button
                      onClick={() => handleTextToSpeech(outputs[activeMode])}
                      className="p-2 text-gray-400 hover:text-white transition-colors hover:bg-gray-700 rounded"
                      title={isSpeaking ? "Stop speaking" : "Read aloud"}
                    >
                      {isSpeaking ? <VolumeX className="w-4 h-4" /> : <Volume2 className="w-4 h-4" />}
                    </button>
                    <button
                      onClick={() => copyToClipboard(outputs[activeMode])}
                      className="p-2 text-gray-400 hover:text-white transition-colors hover:bg-gray-700 rounded"
                      title="Copy to clipboard"
                    >
                      <Copy className="w-4 h-4" />
                    </button>
                    <button
                      className="p-2 text-gray-400 hover:text-white transition-colors hover:bg-gray-700 rounded"
                      title="Download"
                    >
                      <Download className="w-4 h-4" />
                    </button>
                  </div>
                )}
              </div>

              <div className="bg-gray-900 border border-gray-600 rounded-lg p-4 min-h-[300px] font-mono text-sm">
                {outputs[activeMode] ? (
                  <AnimatePresence>
                    <motion.div
                      initial={{ opacity: 0, y: 10 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{ duration: 0.3 }}
                      className="whitespace-pre-wrap"
                    >
                      {activeMode === "natural-language" ? (
                        <pre className="text-cyan-400">
                          <code>{outputs[activeMode]}</code>
                        </pre>
                      ) : (
                        <div className="text-gray-300 space-y-2">
                          {outputs[activeMode].split("\n").map((line, index) => (
                            <div key={index} className={getLineStyle(line)}>
                              {line}
                            </div>
                          ))}
                        </div>
                      )}
                    </motion.div>
                  </AnimatePresence>
                ) : (
                  <div className="flex items-center justify-center h-full text-gray-500">
                    <div className="text-center">
                      <div
                        className={`w-16 h-16 mx-auto mb-4 rounded-full bg-gradient-to-r ${currentMode?.color} opacity-20 flex items-center justify-center`}
                      >
                        {currentMode?.icon}
                      </div>
                      <p>Run your query to see the output here</p>
                    </div>
                  </div>
                )}
              </div>
            </motion.div>
          </div>
        </div>
      </div>
    </div>
  )
}

// Helper function to style different types of output lines
function getLineStyle(line) {
  if (line.includes("✅") || line.includes("**Issues Found:**")) {
    return "text-green-400 font-semibold"
  }
  if (line.includes("⚡") || line.includes("**Optimization Analysis:**")) {
    return "text-yellow-400 font-semibold"
  }
  if (line.includes("📋") || line.includes("**Query Explanation:**")) {
    return "text-blue-400 font-semibold"
  }
  if (line.includes("**") && line.includes(":**")) {
    return "text-white font-semibold"
  }
  if (line.includes("```sql")) {
    return "text-cyan-400"
  }
  if (line.includes("CREATE INDEX") || line.includes("SELECT") || line.includes("FROM")) {
    return "text-cyan-300"
  }
  if (line.includes("- ") || line.includes("1. ") || line.includes("2. ")) {
    return "text-gray-300"
  }
  return "text-gray-300"
}
