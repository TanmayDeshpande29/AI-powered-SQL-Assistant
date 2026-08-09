
import { motion } from "framer-motion"
import { useState } from "react"
import {
  Database,
  Search,
  ChevronDown,
  Play,
  Copy,
  Edit,
  Save,
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
  Sparkles,
  ArrowLeft,
  Plus,
  Check,
} from "lucide-react"
import { BrowserRouter,Routes,Route,Link,Outlet } from "react-router";

export default function QueryBuilderMainPage() {
  const [selectedTool, setSelectedTool] = useState("Generate SQL")
  const [selectedDatabase, setSelectedDatabase] = useState("")
  const [selectedDialect, setSelectedDialect] = useState("MySQL")
  const [queryInput, setQueryInput] = useState("Show the number of users who signed up in the last week, group by date")
  const [generatedSQL, setGeneratedSQL] = useState("")
  const [selectedTables, setSelectedTables] = useState([])
  const [searchTables, setSearchTables] = useState("")
  const [rememberHistory, setRememberHistory] = useState(false)
  const [sidebarOpen, setSidebarOpen] = useState(true)
  const [isGenerating, setIsGenerating] = useState(false)
  const [showExamples, setShowExamples] = useState(false)

  const tools = ["Generate SQL", "Explain SQL", "Optimize SQL", "Fix SQL", "Format SQL", "SQL to Natural Language"]

  const sqlDialects = [
    { value: "MySQL", label: "MySQL", icon: "🐬" },
    { value: "Trino SQL", label: "Trino SQL", icon: "⚡" },
    { value: "Spark SQL", label: "Spark SQL", icon: "✨" },
  ]

  const databases = [
    "E-commerce Database",
    "Analytics Database",
    "User Management DB",
    "Inventory System",
    "Sales Database",
    "Customer Database",
  ]

  const sampleTables = {
    "E-commerce Database": [
      { name: "users", columns: ["id", "name", "email", "created_at", "last_login"] },
      { name: "orders", columns: ["id", "user_id", "total", "order_date", "status"] },
      { name: "products", columns: ["id", "name", "price", "category_id", "stock"] },
      { name: "categories", columns: ["id", "name", "description", "parent_id"] },
      { name: "order_items", columns: ["id", "order_id", "product_id", "quantity", "price"] },
    ],
    "Analytics Database": [
      { name: "events", columns: ["id", "user_id", "event_type", "timestamp", "properties"] },
      { name: "sessions", columns: ["id", "user_id", "start_time", "end_time", "page_views"] },
      { name: "conversions", columns: ["id", "user_id", "conversion_type", "value", "date"] },
    ],
  }

  const sidebarItems = [
    { icon: <Database className="w-5 h-5" />, label: "Query Builder", active: true, to: "/querybuilder" },
    { icon: <Settings className="w-5 h-5" />, label: "Database Setup", to: "/database-setup" },
    { icon: <Code className="w-5 h-5" />, label: "SQL Assistants", to: "/sql-assistants" },
    { icon: <BarChart3 className="w-5 h-5" />, label: "Dashboard", to: "/user-dashboard" },
    { icon: <User className="w-5 h-5" />, label: "Account", to: "/account" },
    { icon: <CreditCard className="w-5 h-5" />, label: "Pricing", to: "/dashboard/pricing" },
    { icon: <Settings className="w-5 h-5" />, label: "Settings", to: "/settings" },
    { icon: <DollarSign className="w-5 h-5" />, label: "Refer & Earn", to: "/dashboard/refer" },
    { icon: <FileText className="w-5 h-5" />, label: "Documentation", to: "/dashboard/docs" },
  ]


  const handleGenerateSQL = async () => {
    setIsGenerating(true);
  const url = "http://localhost:8000/generate-sql";
  const payload = {
    query: queryInput,
    dialect: selectedDialect
  };

  try {
    const res = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });

    const data = await res.json();

    if (data.sql) {
      //console.log("Generated SQL:", data.sql);
      setGeneratedSQL(data.sql); // <-- This sets the query in your state
    } else {
      console.error("Groq API error:", data.error);
      setGeneratedSQL("No SQL generated"); // Fallback
    }
  } catch (err) {
    console.error("Request failed:", err);
    setGeneratedSQL("Error connecting to backend");
  }
  finally {
    setIsGenerating(false);
  }
};

  const handleCopySQL = () => {
    navigator.clipboard.writeText(generatedSQL)
  }

  const currentTables = selectedDatabase ? sampleTables[selectedDatabase] || [] : []

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
            <h1 className="text-2xl font-bold">Query Builder</h1>
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
        <div className="flex-1 p-6 grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Left Panel - Configuration */}
          <div className="space-y-6">
            {/* Tool Selection */}
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.6 }}
              className="bg-gray-800 rounded-xl p-6 border border-gray-700"
            >
              <label className="block text-sm font-medium text-gray-300 mb-3">Select a Tool:</label>
              <select
                value={selectedTool}
                onChange={(e) => setSelectedTool(e.target.value)}
                className="w-full bg-gray-700 border border-gray-600 rounded-lg px-4 py-3 text-white focus:outline-none focus:border-cyan-500 transition-colors appearance-none"
              >
                {tools.map((tool) => (
                  <option key={tool} value={tool}>
                    {tool}
                  </option>
                ))}
              </select>
            </motion.div>

            {/* SQL Dialect Selection */}
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.6, delay: 0.05 }}
              className="bg-gray-800 rounded-xl p-6 border border-gray-700"
            >
              <label className="block text-sm font-medium text-gray-300 mb-3">SQL Dialect:</label>
              <select
                value={selectedDialect}
                onChange={(e) => setSelectedDialect(e.target.value)}
                className="w-full bg-gray-700 border border-gray-600 rounded-lg px-4 py-3 text-white focus:outline-none focus:border-cyan-500 transition-colors appearance-none"
              >
                {sqlDialects.map((dialect) => (
                  <option key={dialect.value} value={dialect.value}>
                    {dialect.icon} {dialect.label}
                  </option>
                ))}
              </select>
            </motion.div>

            {/* Database Selection */}
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.6, delay: 0.1 }}
              className="bg-gray-800 rounded-xl p-6 border border-gray-700"
            >
              <label className="block text-sm font-medium text-gray-300 mb-3">Select a Database:</label>
              <select
                value={selectedDatabase}
                onChange={(e) => {
                  setSelectedDatabase(e.target.value)
                  setSelectedTables([])
                }}
                className="w-full bg-gray-700 border border-gray-600 rounded-lg px-4 py-3 text-white focus:outline-none focus:border-cyan-500 transition-colors appearance-none"
              >
                <option value="">Select a Database</option>
                {databases.map((db) => (
                  <option key={db} value={db}>
                    {db}
                  </option>
                ))}
              </select>
            </motion.div>

            {/* Tables Selection */}
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.6, delay: 0.15 }}
              className="bg-gray-800 rounded-xl p-6 border border-gray-700"
            >
              <div className="flex items-center space-x-2 mb-4">
                <Database className="w-5 h-5 text-cyan-400" />
                <h3 className="font-medium">Select Tables</h3>
              </div>

              {selectedDatabase ? (
                <>
                  <div className="relative mb-4">
                    <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4 text-gray-400" />
                    <input
                      type="text"
                      placeholder="Search tables..."
                      value={searchTables}
                      onChange={(e) => setSearchTables(e.target.value)}
                      className="w-full bg-gray-700 border border-gray-600 rounded-lg pl-10 pr-4 py-2 text-white placeholder-gray-400 focus:outline-none focus:border-cyan-500 transition-colors"
                    />
                  </div>

                  <div className="space-y-2 max-h-48 overflow-y-auto">
                    {currentTables
                      .filter((table) => table.name.toLowerCase().includes(searchTables.toLowerCase()))
                      .map((table) => (
                        <div
                          key={table.name}
                          className="flex items-center space-x-3 p-3 hover:bg-gray-700 rounded-lg cursor-pointer transition-colors"
                          onClick={() => {
                            if (selectedTables.includes(table.name)) {
                              setSelectedTables(selectedTables.filter((t) => t !== table.name))
                            } else {
                              setSelectedTables([...selectedTables, table.name])
                            }
                          }}
                        >
                          <div className="w-4 h-4 border border-gray-500 rounded flex items-center justify-center">
                            {selectedTables.includes(table.name) && <Check className="w-3 h-3 text-cyan-400" />}
                          </div>
                          <div className="flex-1">
                            <span className="text-sm font-medium">{table.name}</span>
                            <p className="text-xs text-gray-400">{table.columns.length} columns</p>
                          </div>
                        </div>
                      ))}
                  </div>
                </>
              ) : (
                <div className="text-center py-8 text-gray-400">
                  <p className="text-sm mb-2">Select a database above. If no database exists,</p>
                  <button className="text-cyan-400 hover:text-cyan-300 text-sm inline-flex items-center space-x-1">
                    <Plus className="w-4 h-4" />
                    <span>add one here</span>
                  </button>
                </div>
              )}
            </motion.div>

            {/* Selected Tables */}
            {selectedTables.length > 0 && (
              <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.6, delay: 0.2 }}
                className="bg-gray-800 rounded-xl p-6 border border-gray-700"
              >
                <div className="flex items-center space-x-2 mb-4">
                  <ChevronDown className="w-4 h-4 text-gray-400" />
                  <h3 className="font-medium">Selected Tables</h3>
                  <span className="text-xs bg-cyan-600 text-white px-2 py-1 rounded-full">{selectedTables.length}</span>
                </div>
                <div className="space-y-2">
                  {selectedTables.map((tableName) => (
                    <div key={tableName} className="flex items-center justify-between p-2 bg-gray-700 rounded-lg">
                      <span className="text-sm">{tableName}</span>
                      <button
                        onClick={() => setSelectedTables(selectedTables.filter((t) => t !== tableName))}
                        className="text-red-400 hover:text-red-300 text-xs px-2 py-1 hover:bg-red-400/10 rounded transition-colors"
                      >
                        Remove
                      </button>
                    </div>
                  ))}
                </div>
              </motion.div>
            )}
          </div>

          {/* Right Panel - Query Builder */}
          <div className="lg:col-span-2 space-y-6">
            {/* Query Input */}
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.6, delay: 0.1 }}
              className="bg-gray-800 rounded-xl p-6 border border-gray-700"
            >
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-xl font-semibold flex items-center space-x-2">
                  <span>{selectedTool}</span>
                  <span className="text-sm bg-purple-600 text-white px-2 py-1 rounded-full">{selectedDialect}</span>
                </h2>
                <button
                  onClick={() => setShowExamples(!showExamples)}
                  className="text-cyan-400 hover:text-cyan-300 text-sm flex items-center space-x-1 transition-colors"
                >
                  <Sparkles className="w-4 h-4" />
                  <span>Examples</span>
                </button>
              </div>

              <label className="block text-sm font-medium text-gray-300 mb-3">
                Describe your query in natural language:
              </label>

              <textarea
                value={queryInput}
                onChange={(e) => setQueryInput(e.target.value)}
                placeholder="Example: Show the number of users who signed up in the last week, group by date"
                className="w-full h-32 bg-gray-700 border border-gray-600 rounded-lg px-4 py-3 text-white placeholder-gray-400 focus:outline-none focus:border-cyan-500 transition-colors resize-none"
              />

              <div className="flex items-center justify-between mt-4">
                <div className="flex items-center space-x-4">
                  <label className="flex items-center space-x-2 text-sm text-gray-300">
                    <input
                      type="checkbox"
                      checked={rememberHistory}
                      onChange={(e) => setRememberHistory(e.target.checked)}
                      className="w-4 h-4 text-cyan-500 bg-gray-700 border-gray-600 rounded focus:ring-cyan-500"
                    />
                    <span>Remember conversation history</span>
                  </label>
                  <button className="text-gray-400 hover:text-gray-300 text-sm px-3 py-1 bg-gray-700 rounded hover:bg-gray-600 transition-colors">
                    Clear Context
                  </button>
                </div>
              </div>
            </motion.div>

            {/* Examples Panel */}
            {showExamples && (
              <motion.div
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: "auto" }}
                exit={{ opacity: 0, height: 0 }}
                transition={{ duration: 0.3 }}
                className="bg-gray-800 rounded-xl p-6 border border-gray-700"
              >
                <h3 className="font-medium mb-4">Example Queries</h3>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  {examples.map((example, index) => (
                    <button
                      key={index}
                      onClick={() => {
                        setQueryInput(example)
                        setShowExamples(false)
                      }}
                      className="text-left p-3 bg-gray-700 hover:bg-gray-600 rounded-lg text-sm transition-colors"
                    >
                      {example}
                    </button>
                  ))}
                </div>
              </motion.div>
            )}

            {/* Generated SQL */}
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.6, delay: 0.2 }}
              className="bg-gray-800 rounded-xl p-6 border border-gray-700"
            >
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center space-x-2">
                  <Code className="w-5 h-5 text-cyan-400" />
                  <h3 className="font-medium">Generated SQL</h3>
                </div>
                <div className="flex items-center space-x-2">
                  <motion.button
                    whileHover={{ scale: 1.02 }}
                    whileTap={{ scale: 0.98 }}
                    onClick={handleGenerateSQL}
                    disabled={isGenerating || !queryInput.trim()}
                    className="bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-700 hover:to-purple-700 disabled:opacity-50 disabled:cursor-not-allowed px-4 py-2 rounded-lg font-medium text-sm transition-all duration-300 flex items-center space-x-2"
                  >
                    {isGenerating ? (
                      <>
                        <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin"></div>
                        <span>Generating...</span>
                      </>
                    ) : (
                      <>
                        <Sparkles className="w-4 h-4" />
                        <span>Generate SQL</span>
                      </>
                    )}
                  </motion.button>
                  <button
                    onClick={handleCopySQL}
                    disabled={!generatedSQL}
                    className="p-2 text-gray-400 hover:text-white disabled:opacity-50 disabled:cursor-not-allowed transition-colors hover:bg-gray-700 rounded"
                    title="Copy"
                  >
                    <Copy className="w-4 h-4" />
                  </button>
                  <button
                    disabled={!generatedSQL}
                    className="p-2 text-green-400 hover:text-green-300 disabled:opacity-50 disabled:cursor-not-allowed transition-colors hover:bg-green-400/10 rounded"
                    title="Run"
                  >
                    <Play className="w-4 h-4" />
                  </button>
                  <button
                    disabled={!generatedSQL}
                    className="p-2 text-gray-400 hover:text-white disabled:opacity-50 disabled:cursor-not-allowed transition-colors hover:bg-gray-700 rounded"
                    title="Edit"
                  >
                    <Edit className="w-4 h-4" />
                  </button>
                  <button
                    disabled={!generatedSQL}
                    className="p-2 text-gray-400 hover:text-white disabled:opacity-50 disabled:cursor-not-allowed transition-colors hover:bg-gray-700 rounded"
                    title="Save"
                  >
                    <Save className="w-4 h-4" />
                  </button>
                  <button
                    className="p-2 text-gray-400 hover:text-white transition-colors hover:bg-gray-700 rounded"
                    title="Load"
                  >
                    <Download className="w-4 h-4" />
                  </button>
                </div>
              </div>

              <div className="bg-gray-900 border border-gray-600 rounded-lg p-4 font-mono text-sm min-h-[200px] relative">
                {generatedSQL ? (
                  <pre className="text-cyan-400 whitespace-pre-wrap">
                    <code>{generatedSQL}</code>
                  </pre>
                ) : (
                  <div className="text-gray-500 flex items-center justify-center h-full">-- No SQL generated yet</div>
                )}
              </div>
            </motion.div>
          </div>
        </div>
      </div>
    </div>
  )
}
