import { motion, AnimatePresence } from "framer-motion"
import { useState, useRef } from "react"
import {
  Database,
  Plus,
  Trash2,
  Upload,
  Download,
  Save,
  Edit3,
  GripVertical,
  X,
  FileText,
  Code,
  Sparkles,
  AlertCircle,
  Settings,
  User,
  CreditCard,
  BarChart3,
  DollarSign,
  Menu,
  ArrowLeft,
} from "lucide-react";
import { BrowserRouter,Routes,Route,Link,useNavigate, Outlet } from "react-router";

export default function DatabaseSetupPage() {
  const [activeTab, setActiveTab] = useState("generator")
  const [nlInput, setNlInput] = useState(
    "Create a users table with id, name, email, password, and created_at timestamp",
  )
  const [generatedSQL, setGeneratedSQL] = useState("")
  const [isGenerating, setIsGenerating] = useState(false)
  const [sidebarOpen, setSidebarOpen] = useState(true)
  const [uploadedFile, setUploadedFile] = useState(null)
  const [parseError, setParseError] = useState("")
  const [draggedColumn, setDraggedColumn] = useState(null)

  const fileInputRef = useRef(null)

  const [schema, setSchema] = useState([
    {
      id: 1,
      name: "id",
      type: "INT",
      primaryKey: true,
      notNull: true,
      autoIncrement: true,
    },
    {
      id: 2,
      name: "name",
      type: "VARCHAR(255)",
      primaryKey: false,
      notNull: true,
      autoIncrement: false,
    },
    {
      id: 3,
      name: "email",
      type: "VARCHAR(255)",
      primaryKey: false,
      notNull: true,
      autoIncrement: false,
    },
  ])

  const dataTypes = [
    "INT",
    "BIGINT",
    "SMALLINT",
    "TINYINT",
    "VARCHAR(255)",
    "VARCHAR(100)",
    "VARCHAR(50)",
    "TEXT",
    "LONGTEXT",
    "MEDIUMTEXT",
    "DECIMAL(10,2)",
    "FLOAT",
    "DOUBLE",
    "DATE",
    "DATETIME",
    "TIMESTAMP",
    "BOOLEAN",
    "JSON",
    "BLOB",
  ]

  const sidebarItems = [
    { icon: <Database className="w-5 h-5" />, label: "Query Builder", active: false, to: "/querybuilder" },
    { icon: <Settings className="w-5 h-5" />, label: "Database Setup", active: true, to: "/database-setup" },
    { icon: <Code className="w-5 h-5" />, label: "SQL Assistants", to: "/sql-assistants" },
    { icon: <BarChart3 className="w-5 h-5" />, label: "Dashboard", to: "/user-dashboard" },
    { icon: <User className="w-5 h-5" />, label: "Account", to: "/account" },
    { icon: <CreditCard className="w-5 h-5" />, label: "Pricing", to: "/dashboard/pricing" },
    { icon: <Settings className="w-5 h-5" />, label: "Settings", to: "/settings" },
    { icon: <DollarSign className="w-5 h-5" />, label: "Refer & Earn", to: "/dashboard/refer" },
    { icon: <FileText className="w-5 h-5" />, label: "Documentation", to: "/dashboard/docs" },
  ]

  const tabs = [
    { id: "generator", label: "NL to Schema", icon: <Sparkles className="w-4 h-4" /> },
    { id: "editor", label: "Schema Editor", icon: <Edit3 className="w-4 h-4" /> },
    { id: "import", label: "Import Schema", icon: <Upload className="w-4 h-4" /> },
  ]

  const generateSchemaFromNL = async () => {
    setIsGenerating(true)
    await new Promise((resolve) => setTimeout(resolve, 2000))

    const sampleSQL = `CREATE TABLE users (
  id INT PRIMARY KEY AUTO_INCREMENT,
  name VARCHAR(255) NOT NULL,
  email VARCHAR(255) NOT NULL UNIQUE,
  password VARCHAR(255) NOT NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);`

    setGeneratedSQL(sampleSQL)

    // Update schema state
    const newSchema = [
      { id: 1, name: "id", type: "INT", primaryKey: true, notNull: true, autoIncrement: true },
      { id: 2, name: "name", type: "VARCHAR(255)", primaryKey: false, notNull: true, autoIncrement: false },
      { id: 3, name: "email", type: "VARCHAR(255)", primaryKey: false, notNull: true, autoIncrement: false },
      { id: 4, name: "password", type: "VARCHAR(255)", primaryKey: false, notNull: true, autoIncrement: false },
      { id: 5, name: "created_at", type: "TIMESTAMP", primaryKey: false, notNull: false, autoIncrement: false },
    ]
    setSchema(newSchema)
    setIsGenerating(false)
    setActiveTab("editor")
  }

  const generateSQLFromSchema = () => {
    const tableName = "users" // Could be made dynamic
    let sql = `CREATE TABLE ${tableName} (\n`

    schema.forEach((column, index) => {
      let columnDef = `  ${column.name} ${column.type}`

      if (column.primaryKey) columnDef += " PRIMARY KEY"
      if (column.autoIncrement) columnDef += " AUTO_INCREMENT"
      if (column.notNull && !column.primaryKey) columnDef += " NOT NULL"

      if (index < schema.length - 1) columnDef += ","
      sql += columnDef + "\n"
    })

    sql += ");"
    return sql
  }

  const addColumn = () => {
    const newColumn = {
      id: Date.now(),
      name: "new_column",
      type: "VARCHAR(255)",
      primaryKey: false,
      notNull: false,
      autoIncrement: false,
    }
    setSchema([...schema, newColumn])
  }

  const deleteColumn = (id) => {
    setSchema(schema.filter((col) => col.id !== id))
  }

  const updateColumn = (id, field, value) => {
    setSchema(schema.map((col) => (col.id === id ? { ...col, [field]: value } : col)))
  }

  const handleFileUpload = (event) => {
    const file = event.target.files[0]
    if (file) {
      setUploadedFile(file)
      setParseError("")

      const reader = new FileReader()
      reader.onload = (e) => {
        try {
          if (file.name.endsWith(".json")) {
            const jsonData = JSON.parse(e.target.result)
            // Parse JSON schema
            if (jsonData.columns) {
              setSchema(jsonData.columns)
            }
          } else if (file.name.endsWith(".sql")) {
            // Basic SQL parsing (simplified)
            setParseError("SQL file parsing coming soon!")
          }
        } catch (error) {
          setParseError("Error parsing file: " + error.message)
        }
      }
      reader.readAsText(file)
    }
  }

  const downloadSampleJSON = () => {
    const sampleSchema = {
      tableName: "users",
      columns: [
        { id: 1, name: "id", type: "INT", primaryKey: true, notNull: true, autoIncrement: true },
        { id: 2, name: "name", type: "VARCHAR(255)", primaryKey: false, notNull: true, autoIncrement: false },
        { id: 3, name: "email", type: "VARCHAR(255)", primaryKey: false, notNull: true, autoIncrement: false },
      ],
    }

    const blob = new Blob([JSON.stringify(sampleSchema, null, 2)], { type: "application/json" })
    const url = URL.createObjectURL(blob)
    const a = document.createElement("a")
    a.to = url
    a.download = "sample-schema.json"
    a.click()
    URL.revokeObjectURL(url)
  }

  const handleDragStart = (e, columnId) => {
    setDraggedColumn(columnId)
  }

  const handleDragOver = (e) => {
    e.preventDefault()
  }

  const handleDrop = (e, targetId) => {
    e.preventDefault()
    if (draggedColumn && draggedColumn !== targetId) {
      const draggedIndex = schema.findIndex((col) => col.id === draggedColumn)
      const targetIndex = schema.findIndex((col) => col.id === targetId)

      const newSchema = [...schema]
      const draggedItem = newSchema.splice(draggedIndex, 1)[0]
      newSchema.splice(targetIndex, 0, draggedItem)

      setSchema(newSchema)
    }
    setDraggedColumn(null)
  }

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

        {/* Tabs */}
        <div className="bg-gray-800 border-b border-gray-700 px-6">
          <div className="flex space-x-8">
            {tabs.map((tab) => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`flex items-center space-x-2 py-4 px-2 border-b-2 transition-colors ${
                  activeTab === tab.id
                    ? "border-cyan-500 text-cyan-400"
                    : "border-transparent text-gray-400 hover:text-gray-300"
                }`}
              >
                {tab.icon}
                <span>{tab.label}</span>
              </button>
            ))}
          </div>
        </div>

        {/* Content */}
        <div className="flex-1 p-6">
          <AnimatePresence mode="wait">
            {/* Natural Language Generator Tab */}
            {activeTab === "generator" && (
              <motion.div
                key="generator"
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -20 }}
                transition={{ duration: 0.3 }}
                className="max-w-4xl mx-auto space-y-6"
              >
                <div className="bg-gray-800 rounded-xl p-6 border border-gray-700">
                  <h2 className="text-xl font-semibold mb-4 flex items-center space-x-2">
                    <Sparkles className="w-5 h-5 text-cyan-400" />
                    <span>Natural Language to Schema Generator</span>
                  </h2>

                  <label className="block text-sm font-medium text-gray-300 mb-3">
                    Describe your table schema in natural language:
                  </label>

                  <textarea
                    value={nlInput}
                    onChange={(e) => setNlInput(e.target.value)}
                    placeholder="Example: Create a users table with id, name, email, password, and created_at timestamp"
                    className="w-full h-32 bg-gray-700 border border-gray-600 rounded-lg px-4 py-3 text-white placeholder-gray-400 focus:outline-none focus:border-cyan-500 transition-colors resize-none"
                  />

                  <div className="flex justify-end mt-4">
                    <motion.button
                      whileHover={{ scale: 1.02 }}
                      whileTap={{ scale: 0.98 }}
                      onClick={generateSchemaFromNL}
                      disabled={isGenerating || !nlInput.trim()}
                      className="bg-gradient-to-r from-cyan-500 to-blue-600 hover:from-cyan-600 hover:to-blue-700 disabled:opacity-50 disabled:cursor-not-allowed px-6 py-3 rounded-lg font-semibold transition-all duration-300 flex items-center space-x-2"
                    >
                      {isGenerating ? (
                        <>
                          <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin"></div>
                          <span>Generating...</span>
                        </>
                      ) : (
                        <>
                          <Sparkles className="w-4 h-4" />
                          <span>Generate Schema</span>
                        </>
                      )}
                    </motion.button>
                  </div>
                </div>

                {/* Generated SQL Preview */}
                {generatedSQL && (
                  <motion.div
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.3, delay: 0.1 }}
                    className="bg-gray-800 rounded-xl p-6 border border-gray-700"
                  >
                    <h3 className="text-lg font-semibold mb-4 flex items-center space-x-2">
                      <Code className="w-5 h-5 text-green-400" />
                      <span>Generated SQL</span>
                    </h3>

                    <div className="bg-gray-900 border border-gray-600 rounded-lg p-4 font-mono text-sm">
                      <pre className="text-green-400 whitespace-pre-wrap">
                        <code>{generatedSQL}</code>
                      </pre>
                    </div>

                    <div className="flex justify-end mt-4">
                      <button
                        onClick={() => setActiveTab("editor")}
                        className="bg-purple-600 hover:bg-purple-700 px-4 py-2 rounded-lg font-medium transition-colors flex items-center space-x-2"
                      >
                        <Edit3 className="w-4 h-4" />
                        <span>Edit Schema</span>
                      </button>
                    </div>
                  </motion.div>
                )}
              </motion.div>
            )}

            {/* Schema Editor Tab */}
            {activeTab === "editor" && (
              <motion.div
                key="editor"
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -20 }}
                transition={{ duration: 0.3 }}
                className="max-w-6xl mx-auto grid grid-cols-1 lg:grid-cols-3 gap-6"
              >
                {/* Schema Editor */}
                <div className="lg:col-span-2 bg-gray-800 rounded-xl p-6 border border-gray-700">
                  <h2 className="text-xl font-semibold mb-4 flex items-center space-x-2">
                    <Edit3 className="w-5 h-5 text-purple-400" />
                    <span>Schema Editor</span>
                  </h2>

                  <div className="overflow-x-auto">
                    <table className="w-full">
                      <thead>
                        <tr className="border-b border-gray-600">
                          <th className="text-left py-3 px-2 text-sm font-medium text-gray-300">Order</th>
                          <th className="text-left py-3 px-2 text-sm font-medium text-gray-300">Column Name</th>
                          <th className="text-left py-3 px-2 text-sm font-medium text-gray-300">Data Type</th>
                          <th className="text-left py-3 px-2 text-sm font-medium text-gray-300">Constraints</th>
                          <th className="text-left py-3 px-2 text-sm font-medium text-gray-300">Actions</th>
                        </tr>
                      </thead>
                      <tbody>
                        {schema.map((column, index) => (
                          <tr
                            key={column.id}
                            draggable
                            onDragStart={(e) => handleDragStart(e, column.id)}
                            onDragOver={handleDragOver}
                            onDrop={(e) => handleDrop(e, column.id)}
                            className={`border-b border-gray-700 hover:bg-gray-700/50 transition-colors ${
                              draggedColumn === column.id ? "opacity-50" : ""
                            }`}
                          >
                            <td className="py-3 px-2">
                              <GripVertical className="w-4 h-4 text-gray-400 cursor-move" />
                            </td>
                            <td className="py-3 px-2">
                              <input
                                type="text"
                                value={column.name}
                                onChange={(e) => updateColumn(column.id, "name", e.target.value)}
                                className="bg-gray-700 border border-gray-600 rounded px-3 py-1 text-sm w-full focus:outline-none focus:border-cyan-500"
                              />
                            </td>
                            <td className="py-3 px-2">
                              <select
                                value={column.type}
                                onChange={(e) => updateColumn(column.id, "type", e.target.value)}
                                className="bg-gray-700 border border-gray-600 rounded px-3 py-1 text-sm w-full focus:outline-none focus:border-cyan-500"
                              >
                                {dataTypes.map((type) => (
                                  <option key={type} value={type}>
                                    {type}
                                  </option>
                                ))}
                              </select>
                            </td>
                            <td className="py-3 px-2">
                              <div className="flex flex-col space-y-1">
                                <label className="flex items-center space-x-2 text-xs">
                                  <input
                                    type="checkbox"
                                    checked={column.primaryKey}
                                    onChange={(e) => updateColumn(column.id, "primaryKey", e.target.checked)}
                                    className="w-3 h-3 text-cyan-500 bg-gray-700 border-gray-600 rounded focus:ring-cyan-500"
                                  />
                                  <span>Primary Key</span>
                                </label>
                                <label className="flex items-center space-x-2 text-xs">
                                  <input
                                    type="checkbox"
                                    checked={column.notNull}
                                    onChange={(e) => updateColumn(column.id, "notNull", e.target.checked)}
                                    className="w-3 h-3 text-cyan-500 bg-gray-700 border-gray-600 rounded focus:ring-cyan-500"
                                  />
                                  <span>Not Null</span>
                                </label>
                                <label className="flex items-center space-x-2 text-xs">
                                  <input
                                    type="checkbox"
                                    checked={column.autoIncrement}
                                    onChange={(e) => updateColumn(column.id, "autoIncrement", e.target.checked)}
                                    className="w-3 h-3 text-cyan-500 bg-gray-700 border-gray-600 rounded focus:ring-cyan-500"
                                  />
                                  <span>Auto Increment</span>
                                </label>
                              </div>
                            </td>
                            <td className="py-3 px-2">
                              <button
                                onClick={() => deleteColumn(column.id)}
                                className="text-red-400 hover:text-red-300 p-1 hover:bg-red-400/10 rounded transition-colors"
                              >
                                <Trash2 className="w-4 h-4" />
                              </button>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>

                  <div className="flex justify-between mt-6">
                    <button
                      onClick={addColumn}
                      className="bg-gray-700 hover:bg-gray-600 px-4 py-2 rounded-lg font-medium transition-colors flex items-center space-x-2"
                    >
                      <Plus className="w-4 h-4" />
                      <span>Add New Column</span>
                    </button>

                    <button className="bg-gradient-to-r from-green-600 to-emerald-600 hover:from-green-700 hover:to-emerald-700 px-6 py-2 rounded-lg font-semibold transition-all duration-300 flex items-center space-x-2">
                      <Save className="w-4 h-4" />
                      <span>Save Schema</span>
                    </button>
                  </div>
                </div>

                {/* Live SQL Preview */}
                <div className="bg-gray-800 rounded-xl p-6 border border-gray-700">
                  <h3 className="text-lg font-semibold mb-4 flex items-center space-x-2">
                    <Code className="w-5 h-5 text-cyan-400" />
                    <span>Live SQL Preview</span>
                  </h3>

                  <div className="bg-gray-900 border border-gray-600 rounded-lg p-4 font-mono text-sm min-h-[300px]">
                    <pre className="text-cyan-400 whitespace-pre-wrap">
                      <code>{generateSQLFromSchema()}</code>
                    </pre>
                  </div>
                </div>
              </motion.div>
            )}

            {/* Import Schema Tab */}
            {activeTab === "import" && (
              <motion.div
                key="import"
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -20 }}
                transition={{ duration: 0.3 }}
                className="max-w-4xl mx-auto space-y-6"
              >
                <div className="bg-gray-800 rounded-xl p-6 border border-gray-700">
                  <h2 className="text-xl font-semibold mb-4 flex items-center space-x-2">
                    <Upload className="w-5 h-5 text-green-400" />
                    <span>Import Schema</span>
                  </h2>

                  <div
                    onClick={() => fileInputRef.current?.click()}
                    className="border-2 border-dashed border-gray-600 hover:border-cyan-500 rounded-lg p-8 text-center cursor-pointer transition-colors"
                  >
                    <Upload className="w-12 h-12 text-gray-400 mx-auto mb-4" />
                    <p className="text-lg font-medium mb-2">
                      {uploadedFile ? uploadedFile.name : "Upload Schema File"}
                    </p>
                    <p className="text-gray-400 text-sm">Supports .json and .sql files</p>

                    <input
                      ref={fileInputRef}
                      type="file"
                      accept=".json,.sql"
                      onChange={handleFileUpload}
                      className="hidden"
                    />
                  </div>

                  {parseError && (
                    <div className="mt-4 p-4 bg-red-900/20 border border-red-500 rounded-lg flex items-center space-x-2">
                      <AlertCircle className="w-5 h-5 text-red-400" />
                      <span className="text-red-400">{parseError}</span>
                    </div>
                  )}

                  <div className="flex justify-between mt-6">
                    <button
                      onClick={downloadSampleJSON}
                      className="bg-gray-700 hover:bg-gray-600 px-4 py-2 rounded-lg font-medium transition-colors flex items-center space-x-2"
                    >
                      <Download className="w-4 h-4" />
                      <span>Download Sample JSON</span>
                    </button>

                    {uploadedFile && !parseError && (
                      <button
                        onClick={() => setActiveTab("editor")}
                        className="bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-700 hover:to-purple-700 px-6 py-2 rounded-lg font-semibold transition-all duration-300 flex items-center space-x-2"
                      >
                        <Edit3 className="w-4 h-4" />
                        <span>Edit Imported Schema</span>
                      </button>
                    )}
                  </div>
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </div>
    </div>
  )
}
