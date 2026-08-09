
import { motion, AnimatePresence } from "framer-motion"
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
  Code,
  Bell,
  Key,
  Copy,
  RefreshCw,
  Eye,
  EyeOff,
  Check,
  AlertTriangle,
  Monitor,
  Sun,
  Moon,
} from "lucide-react"
import {Link} from "react-router";

// Reusable Components
const Card = ({ children, className = "" }) => (
  <div className={`bg-gray-800 rounded-2xl p-6 border border-gray-700 ${className}`}>{children}</div>
)

const SectionHeader = ({ icon, title, description }) => (
  <div className="flex items-center space-x-3 mb-6">
    <div className="p-2 bg-gradient-to-r from-cyan-500 to-blue-600 rounded-lg">{icon}</div>
    <div>
      <h2 className="text-xl font-semibold">{title}</h2>
      {description && <p className="text-sm text-gray-400">{description}</p>}
    </div>
  </div>
)

const Switch = ({ checked, onChange, disabled = false }) => (
  <button
    onClick={() => !disabled && onChange(!checked)}
    disabled={disabled}
    className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors focus:outline-none focus:ring-2 focus:ring-cyan-500 focus:ring-offset-2 focus:ring-offset-gray-800 ${
      checked ? "bg-cyan-600" : "bg-gray-600"
    } ${disabled ? "opacity-50 cursor-not-allowed" : "cursor-pointer"}`}
  >
    <span
      className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
        checked ? "translate-x-6" : "translate-x-1"
      }`}
    />
  </button>
)

const Select = ({ value, onChange, options, placeholder = "Select option..." }) => (
  <select
    value={value}
    onChange={(e) => onChange(e.target.value)}
    className="w-full bg-gray-700 border border-gray-600 rounded-lg px-4 py-3 text-white focus:outline-none focus:border-cyan-500 transition-colors appearance-none cursor-pointer"
  >
    <option value="" disabled>
      {placeholder}
    </option>
    {options.map((option) => (
      <option key={option.value} value={option.value}>
        {option.label}
      </option>
    ))}
  </select>
)

const Button = ({ children, variant = "primary", size = "md", onClick, disabled = false, className = "" }) => {
  const baseClasses = "font-semibold rounded-lg transition-all duration-300 flex items-center justify-center space-x-2"
  const sizeClasses = {
    sm: "px-3 py-2 text-sm",
    md: "px-4 py-3",
    lg: "px-6 py-3",
  }
  const variantClasses = {
    primary: "bg-gradient-to-r from-cyan-500 to-blue-600 hover:from-cyan-600 hover:to-blue-700 text-white",
    secondary: "bg-gray-700 hover:bg-gray-600 text-white",
    destructive: "bg-gradient-to-r from-red-500 to-red-600 hover:from-red-600 hover:to-red-700 text-white",
    outline: "border border-gray-600 hover:bg-gray-700 text-gray-300 hover:text-white",
  }

  return (
    <motion.button
      whileHover={{ scale: 1.02 }}
      whileTap={{ scale: 0.98 }}
      onClick={onClick}
      disabled={disabled}
      className={`${baseClasses} ${sizeClasses[size]} ${variantClasses[variant]} ${
        disabled ? "opacity-50 cursor-not-allowed" : ""
      } ${className}`}
    >
      {children}
    </motion.button>
  )
}

const SettingItem = ({ label, description, children, className = "" }) => (
  <div className={`flex items-center justify-between p-4 bg-gray-700/30 rounded-lg ${className}`}>
    <div className="flex-1">
      <h3 className="font-medium text-white">{label}</h3>
      {description && <p className="text-sm text-gray-400 mt-1">{description}</p>}
    </div>
    <div className="ml-4">{children}</div>
  </div>
)

const Modal = ({ isOpen, onClose, title, children }) => (
  <AnimatePresence>
    {isOpen && (
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        className="fixed inset-0 bg-black/50 backdrop-blur-sm z-50 flex items-center justify-center p-4"
        onClick={onClose}
      >
        <motion.div
          initial={{ scale: 0.95, opacity: 0 }}
          animate={{ scale: 1, opacity: 1 }}
          exit={{ scale: 0.95, opacity: 0 }}
          onClick={(e) => e.stopPropagation()}
          className="bg-gray-800 rounded-2xl p-6 border border-gray-700 w-full max-w-md"
        >
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-lg font-semibold">{title}</h3>
            <button onClick={onClose} className="text-gray-400 hover:text-white transition-colors">
              <X className="w-5 h-5" />
            </button>
          </div>
          {children}
        </motion.div>
      </motion.div>
    )}
  </AnimatePresence>
)

export default function SettingsPage() {
  const [sidebarOpen, setSidebarOpen] = useState(true)
  const [showApiKeyModal, setShowApiKeyModal] = useState(false)
  const [showApiKey, setShowApiKey] = useState(false)
  const [isRegenerating, setIsRegenerating] = useState(false)
  const [copySuccess, setCopySuccess] = useState(false)

  // Settings state
  const [settings, setSettings] = useState({
    language: "en",
    theme: "dark",
    defaultDialect: "MySQL",
    emailNotifications: true,
    smsNotifications: false,
    inAppAlerts: true,
    apiKey: "sk-1234567890abcdef1234567890abcdef",
  })

  const sidebarItems = [
    { icon: <Database className="w-5 h-5" />, label: "Query Builder", active: false, to: "/querybuilder" },
    { icon: <Settings className="w-5 h-5" />, label: "Database Setup", active: false, to: "/database-setup" },
    { icon: <FileText className="w-5 h-5" />, label: "SQL Assistants", active: false, to: "/sql-assistants" },
    { icon: <BarChart3 className="w-5 h-5" />, label: "Dashboard", to: "/user-dashboard" },
    { icon: <User className="w-5 h-5" />, label: "Account", active: false, to: "/account" },
    { icon: <CreditCard className="w-5 h-5" />, label: "Pricing", to: "/dashboard/pricing" },
    { icon: <Settings className="w-5 h-5" />, label: "Settings", active: true, to: "/settings" },
    { icon: <DollarSign className="w-5 h-5" />, label: "Refer & Earn", to: "/dashboard/refer" },
    { icon: <FileText className="w-5 h-5" />, label: "Documentation", to: "/dashboard/docs" },
  ]

  const languageOptions = [
    { value: "en", label: "🇺🇸 English" },
    { value: "es", label: "🇪🇸 Español" },
    { value: "fr", label: "🇫🇷 Français" },
    { value: "de", label: "🇩🇪 Deutsch" },
    { value: "it", label: "🇮🇹 Italiano" },
    { value: "pt", label: "🇵🇹 Português" },
    { value: "ru", label: "🇷🇺 Русский" },
    { value: "zh", label: "🇨🇳 中文" },
    { value: "ja", label: "🇯🇵 日本語" },
    { value: "ko", label: "🇰🇷 한국어" },
  ]

  const themeOptions = [
    { value: "light", label: "☀️ Light", icon: <Sun className="w-4 h-4" /> },
    { value: "dark", label: "🌙 Dark", icon: <Moon className="w-4 h-4" /> },
    { value: "system", label: "💻 System", icon: <Monitor className="w-4 h-4" /> },
  ]

  const dialectOptions = [
    { value: "MySQL", label: "🐬 MySQL" },
    { value: "PostgreSQL", label: "🐘 PostgreSQL" },
    { value: "SQLite", label: "🪶 SQLite" },
    { value: "SQL Server", label: "🏢 SQL Server" },
    { value: "Oracle", label: "🔴 Oracle" },
    { value: "Trino", label: "⚡ Trino" },
    { value: "Spark SQL", label: "✨ Spark SQL" },
  ]

  const updateSetting = (key, value) => {
    setSettings((prev) => ({ ...prev, [key]: value }))
  }

  const maskApiKey = (key) => {
    if (!key) return ""
    return key.substring(0, 8) + "..." + key.substring(key.length - 8)
  }

  const copyApiKey = async () => {
    try {
      await navigator.clipboard.writeText(settings.apiKey)
      setCopySuccess(true)
      setTimeout(() => setCopySuccess(false), 2000)
    } catch (err) {
      console.error("Failed to copy API key:", err)
    }
  }

  const regenerateApiKey = async () => {
    setIsRegenerating(true)
    await new Promise((resolve) => setTimeout(resolve, 2000))

    // Generate new API key (mock)
    const newApiKey = "sk-" + Math.random().toString(36).substring(2, 15) + Math.random().toString(36).substring(2, 15)
    updateSetting("apiKey", newApiKey)

    setIsRegenerating(false)
    setShowApiKeyModal(false)
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
        <header className="bg-gray-800 border-b border-gray-700 px-6 py-4 flex items-center justify-between">
          <div className="flex items-center space-x-4">
            <button
              onClick={() => setSidebarOpen(!sidebarOpen)}
              className="text-gray-400 hover:text-white transition-colors lg:hidden"
            >
              {sidebarOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
            </button>
            <h1 className="text-2xl font-bold">Settings</h1>
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
        <div className="flex-1 p-6 max-w-4xl mx-auto w-full">
          <div className="space-y-8">
            {/* General Settings */}
            <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.6 }}>
              <Card>
                <SectionHeader
                  icon={<Settings className="w-5 h-5" />}
                  title="General Settings"
                  description="Configure your basic preferences and defaults"
                />

                <div className="space-y-4">
                  <SettingItem label="Language" description="Choose your preferred language for the interface">
                    <div className="w-48">
                      <Select
                        value={settings.language}
                        onChange={(value) => updateSetting("language", value)}
                        options={languageOptions}
                        placeholder="Select language"
                      />
                    </div>
                  </SettingItem>

                  <SettingItem label="Theme" description="Choose how SQLAssist looks to you">
                    <div className="w-48">
                      <Select
                        value={settings.theme}
                        onChange={(value) => updateSetting("theme", value)}
                        options={themeOptions}
                        placeholder="Select theme"
                      />
                    </div>
                  </SettingItem>

                  <SettingItem label="Default SQL Dialect" description="Set your preferred SQL dialect for new queries">
                    <div className="w-48">
                      <Select
                        value={settings.defaultDialect}
                        onChange={(value) => updateSetting("defaultDialect", value)}
                        options={dialectOptions}
                        placeholder="Select dialect"
                      />
                    </div>
                  </SettingItem>
                </div>
              </Card>
            </motion.div>

            {/* Notification Preferences */}
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.6, delay: 0.1 }}
            >
              <Card>
                <SectionHeader
                  icon={<Bell className="w-5 h-5" />}
                  title="Notification Preferences"
                  description="Control how and when you receive notifications"
                />

                <div className="space-y-4">
                  <SettingItem label="Email Notifications" description="Receive updates and alerts via email">
                    <Switch
                      checked={settings.emailNotifications}
                      onChange={(checked) => updateSetting("emailNotifications", checked)}
                    />
                  </SettingItem>

                  <SettingItem label="SMS Notifications" description="Get important alerts via text message">
                    <Switch
                      checked={settings.smsNotifications}
                      onChange={(checked) => updateSetting("smsNotifications", checked)}
                    />
                  </SettingItem>

                  <SettingItem label="In-app Alerts" description="Show notifications within the application">
                    <Switch
                      checked={settings.inAppAlerts}
                      onChange={(checked) => updateSetting("inAppAlerts", checked)}
                    />
                  </SettingItem>
                </div>
              </Card>
            </motion.div>

            {/* API & Developer Settings */}
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.6, delay: 0.2 }}
            >
              <Card>
                <SectionHeader
                  icon={<Key className="w-5 h-5" />}
                  title="API & Developer"
                  description="Manage your API access and developer tools"
                />

                <div className="space-y-4">
                  <SettingItem
                    label="API Key"
                    description="Your secret key for API access"
                    className="flex-col items-start space-y-4"
                  >
                    <div className="w-full flex items-center space-x-3">
                      <div className="flex-1 bg-gray-700 border border-gray-600 rounded-lg px-4 py-3 font-mono text-sm">
                        {showApiKey ? settings.apiKey : maskApiKey(settings.apiKey)}
                      </div>
                      <button
                        onClick={() => setShowApiKey(!showApiKey)}
                        className="p-3 text-gray-400 hover:text-white transition-colors hover:bg-gray-700 rounded-lg"
                        title={showApiKey ? "Hide API key" : "Show API key"}
                      >
                        {showApiKey ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                      </button>
                      <button
                        onClick={copyApiKey}
                        className="p-3 text-gray-400 hover:text-white transition-colors hover:bg-gray-700 rounded-lg"
                        title="Copy API key"
                      >
                        {copySuccess ? <Check className="w-4 h-4 text-green-400" /> : <Copy className="w-4 h-4" />}
                      </button>
                    </div>
                    <div className="flex space-x-3">
                      <Button variant="outline" size="sm" onClick={() => setShowApiKeyModal(true)}>
                        <RefreshCw className="w-4 h-4" />
                        <span>Regenerate Key</span>
                      </Button>
                      <Button variant="secondary" size="sm">
                        <Code className="w-4 h-4" />
                        <span>View Documentation</span>
                      </Button>
                    </div>
                  </SettingItem>
                </div>

                {/* API Usage Stats */}
                <div className="mt-6 p-4 bg-gray-700/30 rounded-lg">
                  <h4 className="font-medium mb-3">API Usage This Month</h4>
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-sm">
                    <div>
                      <p className="text-gray-400">Requests</p>
                      <p className="text-xl font-semibold text-cyan-400">2,847</p>
                    </div>
                    <div>
                      <p className="text-gray-400">Rate Limit</p>
                      <p className="text-xl font-semibold text-green-400">1000/hour</p>
                    </div>
                    <div>
                      <p className="text-gray-400">Last Used</p>
                      <p className="text-xl font-semibold text-gray-300">2 hours ago</p>
                    </div>
                  </div>
                </div>
              </Card>
            </motion.div>
          </div>
        </div>
      </div>

      {/* API Key Regeneration Modal */}
      <Modal isOpen={showApiKeyModal} onClose={() => setShowApiKeyModal(false)} title="Regenerate API Key">
        <div className="space-y-4">
          <div className="flex items-center space-x-3 p-4 bg-yellow-900/20 border border-yellow-500/30 rounded-lg">
            <AlertTriangle className="w-6 h-6 text-yellow-400 flex-shrink-0" />
            <div>
              <h4 className="font-medium text-yellow-400">Warning</h4>
              <p className="text-sm text-gray-300 mt-1">
                Regenerating your API key will invalidate the current key. Any applications using the old key will stop
                working.
              </p>
            </div>
          </div>

          <div className="bg-gray-700/50 rounded-lg p-4">
            <h4 className="font-medium mb-2">Current API Key</h4>
            <p className="font-mono text-sm text-gray-300 break-all">{maskApiKey(settings.apiKey)}</p>
          </div>

          <div className="flex space-x-3 pt-4">
            <Button
              variant="outline"
              onClick={() => setShowApiKeyModal(false)}
              className="flex-1"
              disabled={isRegenerating}
            >
              Cancel
            </Button>
            <Button variant="destructive" onClick={regenerateApiKey} className="flex-1" disabled={isRegenerating}>
              {isRegenerating ? (
                <>
                  <RefreshCw className="w-4 h-4 animate-spin" />
                  <span>Regenerating...</span>
                </>
              ) : (
                <>
                  <RefreshCw className="w-4 h-4" />
                  <span>Regenerate Key</span>
                </>
              )}
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  )
}
