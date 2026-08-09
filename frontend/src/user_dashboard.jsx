import { motion } from "framer-motion"
import { useState } from "react"
import {
  Database,
  Settings,
  User,
  CreditCard,
  FileText,
  BarChart3,
  DollarSign,
  Menu,
  X,
  ArrowLeft,
  Download,
  TrendingUp,
  Clock,
  CheckCircle,
  XCircle,
  Activity,
  Zap,
  Eye,
  Play,
  Sun,
  Moon,
} from "lucide-react"
import {Link} from "react-router";

// Reusable Components
const Card = ({ children, className = "" }) => (
  <div className={`bg-gray-800 rounded-2xl p-6 border border-gray-700 shadow-lg ${className}`}>{children}</div>
)

const KPICard = ({ title, value, change, changeType, icon, color = "cyan" }) => {
  const colorClasses = {
    cyan: "from-cyan-500 to-blue-600",
    green: "from-green-500 to-emerald-600",
    purple: "from-purple-500 to-violet-600",
    orange: "from-orange-500 to-red-600",
  }

  return (
    <Card className="relative overflow-hidden">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm text-gray-400 mb-1">{title}</p>
          <p className="text-2xl font-bold text-white">{value}</p>
          {change && (
            <div
              className={`flex items-center space-x-1 text-sm mt-2 ${
                changeType === "positive" ? "text-green-400" : "text-red-400"
              }`}
            >
              <TrendingUp className={`w-4 h-4 ${changeType === "negative" ? "rotate-180" : ""}`} />
              <span>{change}</span>
            </div>
          )}
        </div>
        <div className={`p-3 rounded-xl bg-gradient-to-r ${colorClasses[color]} opacity-80`}>{icon}</div>
      </div>
    </Card>
  )
}

const ProgressBar = ({ percentage, color = "cyan" }) => {
  const colorClasses = {
    cyan: "bg-cyan-500",
    green: "bg-green-500",
    red: "bg-red-500",
    purple: "bg-purple-500",
  }

  return (
    <div className="w-full bg-gray-700 rounded-full h-2">
      <div
        className={`h-2 rounded-full transition-all duration-500 ${colorClasses[color]}`}
        style={{ width: `${percentage}%` }}
      />
    </div>
  )
}

const StatusBadge = ({ status }) => {
  const statusConfig = {
    success: { color: "bg-green-500/20 text-green-400 border-green-500/30", icon: <CheckCircle className="w-3 h-3" /> },
    error: { color: "bg-red-500/20 text-red-400 border-red-500/30", icon: <XCircle className="w-3 h-3" /> },
    running: {
      color: "bg-blue-500/20 text-blue-400 border-blue-500/30",
      icon: <Activity className="w-3 h-3 animate-pulse" />,
    },
  }

  const config = statusConfig[status] || statusConfig.success

  return (
    <span className={`inline-flex items-center space-x-1 px-2 py-1 rounded-full text-xs border ${config.color}`}>
      {config.icon}
      <span className="capitalize">{status}</span>
    </span>
  )
}

const Switch = ({ checked, onChange }) => (
  <button
    onClick={() => onChange(!checked)}
    className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
      checked ? "bg-cyan-600" : "bg-gray-600"
    }`}
  >
    <span
      className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
        checked ? "translate-x-6" : "translate-x-1"
      }`}
    />
  </button>
)

export default function DashboardOverview() {
  const [sidebarOpen, setSidebarOpen] = useState(true)
  const [darkMode, setDarkMode] = useState(true)
  const [timeRange, setTimeRange] = useState("7d")

  const sidebarItems = [
    { icon: <Database className="w-5 h-5" />, label: "Query Builder", active: false, to: "/querybuilder" },
    { icon: <Settings className="w-5 h-5" />, label: "Database Setup", active: false, to: "/database-setup" },
    { icon: <FileText className="w-5 h-5" />, label: "SQL Assistants", active: false, to: "/sql-assistants" },
    { icon: <BarChart3 className="w-5 h-5" />, label: "Dashboard", active: true, to: "/user-dashboard" },
    { icon: <User className="w-5 h-5" />, label: "Account", active: false, to: "/account" },
    { icon: <CreditCard className="w-5 h-5" />, label: "Pricing", to: "/dashboard/pricing" },
    { icon: <Settings className="w-5 h-5" />, label: "Settings", active: false, to: "/settings" },
    { icon: <DollarSign className="w-5 h-5" />, label: "Refer & Earn", to: "/dashboard/refer" },
    { icon: <FileText className="w-5 h-5" />, label: "Documentation", to: "/dashboard/docs" },
  ]

  // Mock data
  const kpiData = {
    totalQueries: { value: "2,847", change: "+12.5%", changeType: "positive" },
    successRate: { value: "94.2%", change: "+2.1%", changeType: "positive" },
    avgExecutionTime: { value: "1.2s", change: "-0.3s", changeType: "positive" },
    timeSaved: { value: "127h", change: "+23h", changeType: "positive" },
  }

  const dialectUsage = [
    { name: "MySQL", value: 45, color: "#3B82F6" },
    { name: "PostgreSQL", value: 28, color: "#10B981" },
    { name: "SQLite", value: 15, color: "#F59E0B" },
    { name: "SQL Server", value: 8, color: "#8B5CF6" },
    { name: "Oracle", value: 4, color: "#EF4444" },
  ]

  const recentActivity = [
    {
      id: 1,
      name: "Customer Analysis Query",
      executionTime: "0.8s",
      status: "success",
      date: "2024-01-15 14:30",
      dialect: "MySQL",
    },
    {
      id: 2,
      name: "Sales Report Optimization",
      executionTime: "2.1s",
      status: "success",
      date: "2024-01-15 13:45",
      dialect: "PostgreSQL",
    },
    {
      id: 3,
      name: "User Registration Debug",
      executionTime: "0.5s",
      status: "error",
      date: "2024-01-15 12:20",
      dialect: "MySQL",
    },
    {
      id: 4,
      name: "Product Inventory Query",
      executionTime: "1.3s",
      status: "success",
      date: "2024-01-15 11:15",
      dialect: "SQLite",
    },
    {
      id: 5,
      name: "Monthly Revenue Analysis",
      executionTime: "3.2s",
      status: "running",
      date: "2024-01-15 10:30",
      dialect: "SQL Server",
    },
  ]

  const databaseSchemas = [
    { name: "E-commerce DB", tables: 12, queries: 847, status: "active", lastUsed: "2 hours ago" },
    { name: "Analytics DB", tables: 8, queries: 523, status: "active", lastUsed: "5 hours ago" },
    { name: "User Management", tables: 6, queries: 234, status: "inactive", lastUsed: "2 days ago" },
    { name: "Inventory System", tables: 15, queries: 156, status: "active", lastUsed: "1 day ago" },
  ]

  const chartData = {
    queries: [120, 150, 180, 200, 170, 190, 220],
    success: [95, 92, 96, 94, 97, 93, 95],
    errors: [5, 8, 4, 6, 3, 7, 5],
    labels: ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
  }

  const downloadAnalytics = () => {
    // Mock PDF download
    console.log("Downloading analytics as PDF...")
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
              <p className="text-xs text-gray-400">Pro Plan</p>
            </div>
          </div>
        </div>
      </motion.div>

      {/* Main Content */}
      <div className="flex-1 flex flex-col">
        {/* Header */}
        <header className="bg-gray-800 border-b border-gray-700 px-6 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-4">
              <button
                onClick={() => setSidebarOpen(!sidebarOpen)}
                className="text-gray-400 hover:text-white transition-colors lg:hidden"
              >
                {sidebarOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
              </button>
              <h1 className="text-2xl font-bold">Dashboard</h1>
            </div>

            <div className="flex items-center space-x-4">
              {/* Theme Toggle */}
              <div className="flex items-center space-x-2">
                <Sun className="w-4 h-4 text-gray-400" />
                <Switch checked={darkMode} onChange={setDarkMode} />
                <Moon className="w-4 h-4 text-gray-400" />
              </div>

              {/* Time Range Selector */}
              <select
                value={timeRange}
                onChange={(e) => setTimeRange(e.target.value)}
                className="bg-gray-700 border border-gray-600 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-cyan-500"
              >
                <option value="7d">Last 7 days</option>
                <option value="30d">Last 30 days</option>
                <option value="90d">Last 90 days</option>
              </select>

              {/* Download Button */}
              <motion.button
                whileHover={{ scale: 1.02 }}
                whileTap={{ scale: 0.98 }}
                onClick={downloadAnalytics}
                className="bg-gradient-to-r from-cyan-500 to-blue-600 hover:from-cyan-600 hover:to-blue-700 px-4 py-2 rounded-lg font-medium transition-all duration-300 flex items-center space-x-2"
              >
                <Download className="w-4 h-4" />
                <span>Export PDF</span>
              </motion.button>

              <Link
                to="/"
                className="inline-flex items-center space-x-2 text-cyan-400 hover:text-cyan-300 transition-colors"
              >
                <ArrowLeft className="w-4 h-4" />
                <span>Back to Home</span>
              </Link>
            </div>
          </div>
        </header>

        {/* Content */}
        <div className="flex-1 p-6 overflow-auto">
          <div className="max-w-7xl mx-auto space-y-6">
            {/* KPI Cards */}
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.6 }}
              className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6"
            >
              <KPICard
                title="Total Queries"
                value={kpiData.totalQueries.value}
                change={kpiData.totalQueries.change}
                changeType={kpiData.totalQueries.changeType}
                icon={<Database className="w-6 h-6" />}
                color="cyan"
              />
              <KPICard
                title="Success Rate"
                value={kpiData.successRate.value}
                change={kpiData.successRate.change}
                changeType={kpiData.successRate.changeType}
                icon={<CheckCircle className="w-6 h-6" />}
                color="green"
              />
              <KPICard
                title="Avg Execution Time"
                value={kpiData.avgExecutionTime.value}
                change={kpiData.avgExecutionTime.change}
                changeType={kpiData.avgExecutionTime.changeType}
                icon={<Clock className="w-6 h-6" />}
                color="purple"
              />
              <KPICard
                title="Time Saved"
                value={kpiData.timeSaved.value}
                change={kpiData.timeSaved.change}
                changeType={kpiData.timeSaved.changeType}
                icon={<Zap className="w-6 h-6" />}
                color="orange"
              />
            </motion.div>

            {/* Charts Row */}
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
              {/* Query Trends Chart */}
              <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.6, delay: 0.1 }}
                className="lg:col-span-2"
              >
                <Card>
                  <div className="flex items-center justify-between mb-6">
                    <h3 className="text-lg font-semibold">Query Trends</h3>
                    <div className="flex items-center space-x-4 text-sm">
                      <div className="flex items-center space-x-2">
                        <div className="w-3 h-3 bg-cyan-500 rounded-full"></div>
                        <span className="text-gray-400">Queries</span>
                      </div>
                      <div className="flex items-center space-x-2">
                        <div className="w-3 h-3 bg-green-500 rounded-full"></div>
                        <span className="text-gray-400">Success Rate</span>
                      </div>
                      <div className="flex items-center space-x-2">
                        <div className="w-3 h-3 bg-red-500 rounded-full"></div>
                        <span className="text-gray-400">Errors</span>
                      </div>
                    </div>
                  </div>

                  {/* Simple Bar Chart */}
                  <div className="space-y-4">
                    {chartData.labels.map((label, index) => (
                      <div key={label} className="flex items-center space-x-4">
                        <div className="w-12 text-sm text-gray-400">{label}</div>
                        <div className="flex-1 flex items-center space-x-2">
                          <div className="flex-1 bg-gray-700 rounded-full h-6 relative overflow-hidden">
                            <div
                              className="h-full bg-gradient-to-r from-cyan-500 to-blue-600 rounded-full transition-all duration-500"
                              style={{ width: `${(chartData.queries[index] / 250) * 100}%` }}
                            />
                            <div className="absolute inset-0 flex items-center justify-center text-xs font-medium">
                              {chartData.queries[index]}
                            </div>
                          </div>
                          <div className="w-16 text-sm text-gray-400 text-right">{chartData.success[index]}%</div>
                        </div>
                      </div>
                    ))}
                  </div>
                </Card>
              </motion.div>

              {/* SQL Dialect Usage Pie Chart */}
              <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.6, delay: 0.2 }}
              >
                <Card>
                  <h3 className="text-lg font-semibold mb-6">SQL Dialect Usage</h3>

                  {/* Simple Pie Chart Representation */}
                  <div className="space-y-4">
                    {dialectUsage.map((dialect, index) => (
                      <div key={dialect.name} className="flex items-center justify-between">
                        <div className="flex items-center space-x-3">
                          <div className="w-4 h-4 rounded-full" style={{ backgroundColor: dialect.color }} />
                          <span className="text-sm">{dialect.name}</span>
                        </div>
                        <div className="flex items-center space-x-2">
                          <div className="w-20">
                            <ProgressBar percentage={dialect.value} color="cyan" />
                          </div>
                          <span className="text-sm text-gray-400 w-10 text-right">{dialect.value}%</span>
                        </div>
                      </div>
                    ))}
                  </div>
                </Card>
              </motion.div>
            </div>

            {/* Database Schemas and Recent Activity */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              {/* Active Database Schemas */}
              <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.6, delay: 0.3 }}
              >
                <Card>
                  <h3 className="text-lg font-semibold mb-6">Database Schemas</h3>
                  <div className="space-y-4">
                    {databaseSchemas.map((schema, index) => (
                      <div key={index} className="flex items-center justify-between p-4 bg-gray-700/30 rounded-lg">
                        <div className="flex-1">
                          <div className="flex items-center space-x-2 mb-1">
                            <h4 className="font-medium">{schema.name}</h4>
                            <span
                              className={`px-2 py-1 rounded-full text-xs ${
                                schema.status === "active"
                                  ? "bg-green-500/20 text-green-400"
                                  : "bg-gray-500/20 text-gray-400"
                              }`}
                            >
                              {schema.status}
                            </span>
                          </div>
                          <div className="flex items-center space-x-4 text-sm text-gray-400">
                            <span>{schema.tables} tables</span>
                            <span>{schema.queries} queries</span>
                            <span>Last used {schema.lastUsed}</span>
                          </div>
                        </div>
                        <button className="p-2 text-gray-400 hover:text-white transition-colors hover:bg-gray-600 rounded">
                          <Eye className="w-4 h-4" />
                        </button>
                      </div>
                    ))}
                  </div>
                </Card>
              </motion.div>

              {/* Recent Activity */}
              <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.6, delay: 0.4 }}
              >
                <Card>
                  <h3 className="text-lg font-semibold mb-6">Recent Activity</h3>
                  <div className="space-y-3">
                    {recentActivity.map((activity) => (
                      <div
                        key={activity.id}
                        className="flex items-center justify-between p-3 bg-gray-700/30 rounded-lg hover:bg-gray-700/50 transition-colors"
                      >
                        <div className="flex-1">
                          <h4 className="font-medium text-sm mb-1">{activity.name}</h4>
                          <div className="flex items-center space-x-3 text-xs text-gray-400">
                            <span>{activity.executionTime}</span>
                            <span>{activity.dialect}</span>
                            <span>{activity.date}</span>
                          </div>
                        </div>
                        <div className="flex items-center space-x-2">
                          <StatusBadge status={activity.status} />
                          <button className="p-1 text-gray-400 hover:text-white transition-colors">
                            <Play className="w-3 h-3" />
                          </button>
                        </div>
                      </div>
                    ))}
                  </div>
                </Card>
              </motion.div>
            </div>

            {/* Weekly/Monthly Summary */}
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.6, delay: 0.5 }}
            >
              <Card>
                <h3 className="text-lg font-semibold mb-6">Query Execution Summary</h3>
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
                  <div className="text-center">
                    <div className="text-3xl font-bold text-cyan-400 mb-2">847</div>
                    <div className="text-sm text-gray-400">This Week</div>
                    <div className="text-xs text-green-400 mt-1">+12.5% from last week</div>
                  </div>
                  <div className="text-center">
                    <div className="text-3xl font-bold text-purple-400 mb-2">3,241</div>
                    <div className="text-sm text-gray-400">This Month</div>
                    <div className="text-xs text-green-400 mt-1">+8.3% from last month</div>
                  </div>
                  <div className="text-center">
                    <div className="text-3xl font-bold text-green-400 mb-2">94.2%</div>
                    <div className="text-sm text-gray-400">Success Rate</div>
                    <div className="text-xs text-green-400 mt-1">+2.1% improvement</div>
                  </div>
                  <div className="text-center">
                    <div className="text-3xl font-bold text-orange-400 mb-2">127h</div>
                    <div className="text-sm text-gray-400">Time Saved</div>
                    <div className="text-xs text-green-400 mt-1">+23h this month</div>
                  </div>
                </div>
              </Card>
            </motion.div>
          </div>
        </div>
      </div>
    </div>
  )
}
