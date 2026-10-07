
import { motion, AnimatePresence } from "framer-motion"
import { useState, useRef ,useEffect} from "react"
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
  Camera,
  Shield,
  Download,
  Eye,
  Trash2,
  Edit3,
  Save,
  AlertTriangle,
  Check,
  Smartphone,
  Monitor,
  MapPin,
  Clock,
  Crown,
  Zap,
} from "lucide-react"
import { Link } from "react-router"
import { api } from "./lib/api"

const TOOL_LABELS = {
  generate: "Generate SQL",
  debug: "Debug SQL",
  explain: "Explain SQL",
  optimize: "Optimize SQL",
}

// Reusable Components
const Card = ({ children, className = "" }) => (
  <div className={`bg-gray-800 rounded-2xl p-6 border border-gray-700 ${className}`}>{children}</div>
)

const Button = ({ children, variant = "primary", size = "md", onClick, disabled = false, className = "" }) => {
  const baseClasses = "font-semibold rounded-lg transition-all duration-300 flex items-center justify-center space-x-2"
  const sizeClasses = {
    sm: "px-3 py-2 text-sm",
    md: "px-4 py-2",
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

const Input = ({ label, type = "text", value, onChange, placeholder, className = "" }) => (
  <div className={`space-y-2 ${className}`}>
    <label className="block text-sm font-medium text-gray-300">{label}</label>
    <input
      type={type}
      value={value}
      onChange={onChange}
      placeholder={placeholder}
      className="w-full bg-gray-700 border border-gray-600 rounded-lg px-4 py-3 text-white placeholder-gray-400 focus:outline-none focus:border-cyan-500 transition-colors"
    />
  </div>
)

const Toggle = ({ label, checked, onChange, description }) => (
  <div className="flex items-center justify-between">
    <div className="flex-1">
      <label className="text-sm font-medium text-gray-300">{label}</label>
      {description && <p className="text-xs text-gray-400 mt-1">{description}</p>}
    </div>
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

export default function AccountPage() {
  const [sidebarOpen, setSidebarOpen] = useState(true)
  const [showPasswordModal, setShowPasswordModal] = useState(false)
  const [showDeleteModal, setShowDeleteModal] = useState(false)
  const [isEditing, setIsEditing] = useState(false)
  const [isSaving, setIsSaving] = useState(false)

  const fileInputRef = useRef(null)

  // User data state
  const [userData, setUserData] = useState({
    name: "",
    email: "",
    bio: "Full-stack developer passionate about data and SQL optimization.",
    avatar: "/placeholder.svg?height=100&width=100",
    plan: "Pro",
    aiUpdates: true,
  })
  const [history, setHistory] = useState([])

  useEffect(() => {
    // The user is identified by the token, so no user id is needed in the URL.
    // Merge (not replace) so UI-only fields like plan/bio/avatar keep their values.
    api.me()
      .then((me) => setUserData((prev) => ({ ...prev, name: me.name, email: me.email })))
      .catch((err) => console.error("Failed to load profile:", err.message))
    api.listHistory({ limit: 10 })
      .then((page) => setHistory(page.items))
      .catch((err) => console.error("Failed to load history:", err.message))
  }, [])

  // Password change state
  const [passwordData, setPasswordData] = useState({
    current: "",
    new: "",
    confirm: "",
  })

  const sidebarItems = [
    { icon: <Database className="w-5 h-5" />, label: "Query Builder", active: false, to: "/querybuilder" },
    { icon: <Settings className="w-5 h-5" />, label: "Database Setup", active: false, to: "/database-setup" },
    { icon: <FileText className="w-5 h-5" />, label: "SQL Assistants", active: false, to: "/sql-assistants" },
    { icon: <BarChart3 className="w-5 h-5" />, label: "Dashboard", to: "/user-dashboard" },
    { icon: <User className="w-5 h-5" />, label: "Account", active: true, to: "/account" },
    { icon: <CreditCard className="w-5 h-5" />, label: "Pricing", to: "/dashboard/pricing" },
    { icon: <Settings className="w-5 h-5" />, label: "Settings", to: "/settings" },
    { icon: <DollarSign className="w-5 h-5" />, label: "Refer & Earn", to: "/dashboard/refer" },
    { icon: <FileText className="w-5 h-5" />, label: "Documentation", to: "/dashboard/docs" },
  ]

  const planFeatures = {
    Free: { icon: <User className="w-5 h-5" />, color: "from-gray-500 to-gray-600", queries: "100/month" },
    Pro: { icon: <Zap className="w-5 h-5" />, color: "from-cyan-500 to-blue-600", queries: "Unlimited" },
    Enterprise: { icon: <Crown className="w-5 h-5" />, color: "from-purple-500 to-violet-600", queries: "Unlimited" },
    
  }

  // Shape the API rows (QueryHistoryRead) into what the history list renders.
  const queryHistory = history.map((entry) => ({
    id: entry.id,
    name: entry.input_text.length > 60 ? `${entry.input_text.slice(0, 60)}…` : entry.input_text,
    date: new Date(entry.created_at).toLocaleDateString(),
    size: entry.dialect,
    type: TOOL_LABELS[entry.tool] ?? entry.tool,
  }))

  const deviceHistory = [
    {
      id: 1,
      device: "MacBook Pro",
      icon: <Monitor className="w-4 h-4" />,
      location: "New York, US",
      ip: "192.168.1.100",
      lastLogin: "2024-01-15 14:30",
      current: true,
    },
    {
      id: 2,
      device: "iPhone 15",
      icon: <Smartphone className="w-4 h-4" />,
      location: "New York, US",
      ip: "192.168.1.101",
      lastLogin: "2024-01-15 09:15",
      current: false,
    },
    {
      id: 3,
      device: "Windows Desktop",
      icon: <Monitor className="w-4 h-4" />,
      location: "Boston, US",
      ip: "10.0.0.50",
      lastLogin: "2024-01-14 16:45",
      current: false,
    },
  ]

  const handleAvatarUpload = (event) => {
    const file = event.target.files[0]
    if (file) {
      const reader = new FileReader()
      reader.onload = (e) => {
        setUserData((prev) => ({ ...prev, avatar: e.target.result }))
      }
      reader.readAsDataURL(file)
    }
  }

  const handleSaveProfile = async () => {
    setIsSaving(true)
    try {
      // Only the name is server-side for now; email changes need a verification flow.
      const me = await api.updateMe({ name: userData.name })
      setUserData((prev) => ({ ...prev, name: me.name, email: me.email }))
      setIsEditing(false)
    } catch (err) {
      alert(err.message)
    } finally {
      setIsSaving(false)
    }
  }

  const handlePasswordChange = async () => {
    if (passwordData.new !== passwordData.confirm) {
      alert("New passwords don't match!")
      return
    }
    try {
      await api.changePassword(passwordData.current, passwordData.new)
      setPasswordData({ current: "", new: "", confirm: "" })
      setShowPasswordModal(false)
      alert("Password updated.")
    } catch (err) {
      alert(err.message)
    }
  }

  const handleDeleteAccount = async () => {
    try {
      await api.deleteAccount()
      api.logout() // clears tokens and redirects to /login
    } catch (err) {
      alert(err.message)
    }
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

        {/* <nav>
            <SidebarItemList />
        </nav> */}

        {/* User Profile */}
        <div className="p-4 border-t border-gray-700">
          <div className="flex items-center space-x-3">
            <div className="w-8 h-8 bg-gradient-to-r from-purple-400 to-pink-500 rounded-full flex items-center justify-center">
              <span className="text-sm font-semibold">M</span>
            </div>
            <div className="flex-1">
              <p className="text-sm font-medium">mergist1</p>
              <p className="text-xs text-gray-400">{userData.plan} Plan</p>
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
            <h1 className="text-2xl font-bold">Account</h1>
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
        <div className="flex-1 p-6 max-w-6xl mx-auto w-full">
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* Left Column - Profile & Security */}
            <div className="lg:col-span-2 space-y-6">
              {/* User Profile Form */}
              <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.6 }}>
                <Card>
                  <div className="flex items-center justify-between mb-6">
                    <h2 className="text-xl font-semibold flex items-center space-x-2">
                      <User className="w-5 h-5 text-cyan-400" />
                      <span>Profile Information</span>
                    </h2>
                    <Button
                      variant={isEditing ? "primary" : "outline"}
                      size="sm"
                      onClick={() => (isEditing ? handleSaveProfile() : setIsEditing(true))}
                      disabled={isSaving}
                    >
                      {isSaving ? (
                        <>
                          <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                          <span>Saving...</span>
                        </>
                      ) : isEditing ? (
                        <>
                          <Save className="w-4 h-4" />
                          <span>Save</span>
                        </>
                      ) : (
                        <>
                          <Edit3 className="w-4 h-4" />
                          <span>Edit</span>
                        </>
                      )}
                    </Button>
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                    {/* Avatar Upload */}
                    <div className="md:col-span-2 flex items-center space-x-6">
                      <div className="relative">
                        <img
                          src={userData.avatar || "/placeholder.svg"}
                          alt="Profile Avatar"
                          className="w-20 h-20 rounded-full object-cover border-2 border-gray-600"
                        />
                        {isEditing && (
                          <button
                            onClick={() => fileInputRef.current?.click()}
                            className="absolute -bottom-2 -right-2 bg-cyan-600 hover:bg-cyan-700 p-2 rounded-full transition-colors"
                          >
                            <Camera className="w-4 h-4" />
                          </button>
                        )}
                        <input
                          ref={fileInputRef}
                          type="file"
                          accept="image/*"
                          onChange={handleAvatarUpload}
                          className="hidden"
                        />
                      </div>
                      <div>
                        <h3 className="text-lg font-semibold">{userData.name}</h3>
                        <p className="text-gray-400">{userData.email}</p>
                      </div>
                    </div>

                    {/* Form Fields */}
                    <Input
                      label="Full Name"
                      value={userData.name}
                      onChange={(e) => setUserData((prev) => ({ ...prev, name: e.target.value }))}
                      placeholder="Enter your full name"
                      className={!isEditing ? "opacity-60 pointer-events-none" : ""}
                    />

                    <Input
                      label="Email Address"
                      type="email"
                      value={userData.email}
                      onChange={(e) => setUserData((prev) => ({ ...prev, email: e.target.value }))}
                      placeholder="Enter your email"
                      className={!isEditing ? "opacity-60 pointer-events-none" : ""}
                    />

                    <div className="md:col-span-2">
                      <label className="block text-sm font-medium text-gray-300 mb-2">Bio</label>
                      <textarea
                        value={userData.bio}
                        onChange={(e) => setUserData((prev) => ({ ...prev, bio: e.target.value }))}
                        placeholder="Tell us about yourself..."
                        rows={3}
                        disabled={!isEditing}
                        className={`w-full bg-gray-700 border border-gray-600 rounded-lg px-4 py-3 text-white placeholder-gray-400 focus:outline-none focus:border-cyan-500 transition-colors resize-none ${
                          !isEditing ? "opacity-60 pointer-events-none" : ""
                        }`}
                      />
                    </div>
                  </div>
                </Card>
              </motion.div>

              {/* Security Section */}
              <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.6, delay: 0.1 }}
              >
                <Card>
                  <h2 className="text-xl font-semibold mb-6 flex items-center space-x-2">
                    <Shield className="w-5 h-5 text-green-400" />
                    <span>Security & Privacy</span>
                  </h2>

                  <div className="space-y-6">
                    {/* Password Change */}
                    <div className="flex items-center justify-between p-4 bg-gray-700/50 rounded-lg">
                      <div>
                        <h3 className="font-medium">Password</h3>
                        <p className="text-sm text-gray-400">Last changed 30 days ago</p>
                      </div>
                      <Button variant="outline" size="sm" onClick={() => setShowPasswordModal(true)}>
                        Change Password
                      </Button>
                    </div>

                    {/* AI Updates Toggle */}
                    <div className="p-4 bg-gray-700/50 rounded-lg">
                      <Toggle
                        label="AI Improvement Updates"
                        description="Receive notifications about new AI features and improvements"
                        checked={userData.aiUpdates}
                        onChange={(checked) => setUserData((prev) => ({ ...prev, aiUpdates: checked }))}
                      />
                    </div>

                    {/* Delete Account */}
                    <div className="p-4 bg-red-900/20 border border-red-500/30 rounded-lg">
                      <div className="flex items-center justify-between">
                        <div>
                          <h3 className="font-medium text-red-400">Danger Zone</h3>
                          <p className="text-sm text-gray-400">Permanently delete your account and all data</p>
                        </div>
                        <Button variant="destructive" size="sm" onClick={() => setShowDeleteModal(true)}>
                          <Trash2 className="w-4 h-4" />
                          <span>Delete Account</span>
                        </Button>
                      </div>
                    </div>
                  </div>
                </Card>
              </motion.div>

              {/* Query Export History */}
              <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.6, delay: 0.2 }}
              >
                <Card>
                  <h2 className="text-xl font-semibold mb-6 flex items-center space-x-2">
                    <FileText className="w-5 h-5 text-purple-400" />
                    <span>Query Export History</span>
                  </h2>

                  <div className="space-y-3">
                    {queryHistory.map((query) => (
                      <div
                        key={query.id}
                        className="flex items-center justify-between p-4 bg-gray-700/50 rounded-lg hover:bg-gray-700 transition-colors"
                      >
                        <div className="flex-1">
                          <h3 className="font-medium">{query.name}</h3>
                          <div className="flex items-center space-x-4 text-sm text-gray-400 mt-1">
                            <span>{query.date}</span>
                            <span>{query.size}</span>
                            <span className="px-2 py-1 bg-cyan-600/20 text-cyan-400 rounded">{query.type}</span>
                          </div>
                        </div>
                        <div className="flex items-center space-x-2">
                          <button className="p-2 text-gray-400 hover:text-white transition-colors hover:bg-gray-600 rounded">
                            <Eye className="w-4 h-4" />
                          </button>
                          <button className="p-2 text-gray-400 hover:text-white transition-colors hover:bg-gray-600 rounded">
                            <Download className="w-4 h-4" />
                          </button>
                        </div>
                      </div>
                    ))}
                  </div>
                </Card>
              </motion.div>
            </div>

            {/* Right Column - Plan & Devices */}
            <div className="space-y-6">
              {/* Account Tier */}
              <motion.div initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }} transition={{ duration: 0.6 }}>
                <Card>
                  <h2 className="text-xl font-semibold mb-6 flex items-center space-x-2">
                    <CreditCard className="w-5 h-5 text-yellow-400" />
                    <span>Current Plan</span>
                  </h2>

                  <div className="text-center">
                    <div
                      className={`w-16 h-16 mx-auto mb-4 rounded-full bg-gradient-to-r ${
                        planFeatures[userData.plan]?.color|| "from-gray-400 to-gray-600"
                      } flex items-center justify-center`}
                    >
                      {planFeatures[userData.plan]?.icon || null}
                    </div>
                    <h3 className="text-2xl font-bold mb-2">{userData.plan}</h3>
                    <p className="text-gray-400 mb-4">{planFeatures[userData.plan]?.queries || null}</p>

                    <div className="space-y-3 mb-6">
                      <div className="flex justify-between text-sm">
                        <span>Queries this month</span>
                        <span className="text-cyan-400">847 / ∞</span>
                      </div>
                      <div className="w-full bg-gray-700 rounded-full h-2">
                        <div className="bg-gradient-to-r from-cyan-500 to-blue-600 h-2 rounded-full w-3/4"></div>
                      </div>
                    </div>

                    <Button variant="outline" className="w-full bg-transparent">
                      <Crown className="w-4 h-4" />
                      <span>Upgrade Plan</span>
                    </Button>
                  </div>
                </Card>
              </motion.div>

              {/* Device Login History */}
              <motion.div
                initial={{ opacity: 0, x: 20 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ duration: 0.6, delay: 0.1 }}
              >
                <Card>
                  <h2 className="text-xl font-semibold mb-6 flex items-center space-x-2">
                    <Monitor className="w-5 h-5 text-blue-400" />
                    <span>Device History</span>
                  </h2>

                  <div className="space-y-3">
                    {deviceHistory.map((device) => (
                      <div
                        key={device.id}
                        className={`p-4 rounded-lg border ${
                          device.current ? "bg-cyan-900/20 border-cyan-500/30" : "bg-gray-700/50 border-gray-600/50"
                        }`}
                      >
                        <div className="flex items-center justify-between mb-2">
                          <div className="flex items-center space-x-3">
                            <div className="text-gray-400">{device.icon}</div>
                            <div>
                              <h3 className="font-medium flex items-center space-x-2">
                                <span>{device.device}</span>
                                {device.current && (
                                  <span className="text-xs bg-green-600 text-white px-2 py-1 rounded-full">
                                    Current
                                  </span>
                                )}
                              </h3>
                              <div className="flex items-center space-x-2 text-sm text-gray-400">
                                <MapPin className="w-3 h-3" />
                                <span>{device.location}</span>
                                <span>•</span>
                                <span>{device.ip}</span>
                              </div>
                            </div>
                          </div>
                        </div>
                        <div className="flex items-center text-xs text-gray-400">
                          <Clock className="w-3 h-3 mr-1" />
                          <span>Last login: {device.lastLogin}</span>
                        </div>
                      </div>
                    ))}
                  </div>
                </Card>
              </motion.div>
            </div>
          </div>
        </div>
      </div>

      {/* Change Password Modal */}
      <Modal isOpen={showPasswordModal} onClose={() => setShowPasswordModal(false)} title="Change Password">
        <div className="space-y-4">
          <Input
            label="Current Password"
            type="password"
            value={passwordData.current}
            onChange={(e) => setPasswordData((prev) => ({ ...prev, current: e.target.value }))}
            placeholder="Enter current password"
          />
          <Input
            label="New Password"
            type="password"
            value={passwordData.new}
            onChange={(e) => setPasswordData((prev) => ({ ...prev, new: e.target.value }))}
            placeholder="Enter new password"
          />
          <Input
            label="Confirm New Password"
            type="password"
            value={passwordData.confirm}
            onChange={(e) => setPasswordData((prev) => ({ ...prev, confirm: e.target.value }))}
            placeholder="Confirm new password"
          />
          <div className="flex space-x-3 pt-4">
            <Button variant="outline" onClick={() => setShowPasswordModal(false)} className="flex-1">
              Cancel
            </Button>
            <Button onClick={handlePasswordChange} className="flex-1">
              <Check className="w-4 h-4" />
              <span>Update Password</span>
            </Button>
          </div>
        </div>
      </Modal>

      {/* Delete Account Modal */}
      <Modal isOpen={showDeleteModal} onClose={() => setShowDeleteModal(false)} title="Delete Account">
        <div className="space-y-4">
          <div className="flex items-center space-x-3 p-4 bg-red-900/20 border border-red-500/30 rounded-lg">
            <AlertTriangle className="w-6 h-6 text-red-400 flex-shrink-0" />
            <div>
              <h4 className="font-medium text-red-400">This action cannot be undone</h4>
              <p className="text-sm text-gray-400 mt-1">
                All your data, queries, and account information will be permanently deleted.
              </p>
            </div>
          </div>
          <Input label="Type 'DELETE' to confirm" placeholder="DELETE" />
          <div className="flex space-x-3 pt-4">
            <Button variant="outline" onClick={() => setShowDeleteModal(false)} className="flex-1">
              Cancel
            </Button>
            <Button variant="destructive" onClick={handleDeleteAccount} className="flex-1">
              <Trash2 className="w-4 h-4" />
              <span>Delete Account</span>
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  )
}
