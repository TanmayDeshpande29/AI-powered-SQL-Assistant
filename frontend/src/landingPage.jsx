import { motion } from "framer-motion";
import {
  Database,
  Zap,
  Code,
  Search,
  BarChart3,
  Shield,
  Star,
  Users,
  Globe,
  ChevronRight,
  Play,
  Sparkles,
} 
from "lucide-react";
import { BrowserRouter,Routes,Route,Link,useNavigate } from "react-router";
import { useState } from "react";


export default function LandingPage() {
  const [inputText, setInputText] = useState("");
  const navigateTo = useNavigate();

  const features = [
    {
      icon: <Database className="w-8 h-8" />,
      title: "Text to SQL",
      description: "Convert natural language to complex SQL queries instantly",
    },
    {
      icon: <Code className="w-8 h-8" />,
      title: "Explain SQL",
      description: "Get detailed explanations of any SQL query in plain English",
    },
    {
      icon: <Zap className="w-8 h-8" />,
      title: "Optimize SQL",
      description: "Automatically optimize your queries for better performance",
    },
    {
      icon: <Search className="w-8 h-8" />,
      title: "Query Validator",
      description: "Validate and debug SQL queries with intelligent suggestions",
    },
    {
      icon: <BarChart3 className="w-8 h-8" />,
      title: "Data Insights",
      description: "Generate insights and visualizations from your data",
    },
    {
      icon: <Shield className="w-8 h-8" />,
      title: "Security Check",
      description: "Ensure your queries are secure and injection-free",
    },
  ]

  return (

    <div className="min-h-screen bg-gray-900 text-white overflow-hidden">
      {/* Animated Background */}
      <div className="fixed inset-0 overflow-hidden pointer-events-none">
        <div className="absolute -top-40 -right-40 w-80 h-80 bg-cyan-500/20 rounded-full blur-3xl animate-pulse"></div>
        <div className="absolute -bottom-40 -left-40 w-80 h-80 bg-purple-500/20 rounded-full blur-3xl animate-pulse delay-1000"></div>
        <div className="absolute top-1/2 left-1/2 transform -translate-x-1/2 -translate-y-1/2 w-96 h-96 bg-blue-500/10 rounded-full blur-3xl animate-pulse delay-500"></div>
      </div>

      {/* Header Navigation */}
      <motion.header
        initial={{ y: -100, opacity: 0 }}
        animate={{ y: 0, opacity: 1 }}
        transition={{ duration: 0.8 }}
        className="relative z-50 px-6 py-4 backdrop-blur-sm bg-gray-900/80 border-b border-gray-800"
      >
        <div className="max-w-7xl mx-auto flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <div className="w-8 h-8 bg-gradient-to-r from-cyan-400 to-blue-500 rounded-lg flex items-center justify-center">
              <Database className="w-5 h-5 text-white" />
            </div>
            <span className="text-xl font-bold bg-gradient-to-r from-cyan-400 to-blue-500 bg-clip-text text-transparent">
              SQLAssist
            </span>
          </div>

          <nav className="hidden md:flex items-center space-x-8">
            {/* <Link to="/" className="text-gray-300 hover:text-cyan-400 transition-colors">
            
            </Link> */}
            <Link to="/platform" className="text-gray-300 hover:text-cyan-400 transition-colors">
              Platform
            </Link>
            <Link to="/solutions" className="text-gray-300 hover:text-cyan-400 transition-colors">
              Solutions
            </Link>
            <Link to="/pricing" className="text-gray-300 hover:text-cyan-400 transition-colors">
              Pricing
            </Link>
            <Link to="/contact" className="text-gray-300 hover:text-cyan-400 transition-colors">
              Contact
            </Link>
            <Link to="/blog" className="text-gray-300 hover:text-cyan-400 transition-colors">
              Blog
            </Link>
          </nav>

           
          <motion.button
           
            onClick={() => navigateTo("/login")}
            whileHover={{ scale: 1.05 }}
            whileTap={{ scale: 0.95 }}
            className="bg-gradient-to-r from-cyan-500 to-blue-600 hover:from-cyan-600 hover:to-blue-700 px-6 py-2 rounded-lg font-semibold transition-all duration-300 shadow-lg hover:shadow-cyan-500/25"
          >
            Login for Free
            
          </motion.button>
        </div>
      </motion.header>

      {/* Hero Section */}
      <section className="relative z-10 px-6 py-20 md:py-32">
       

        <div className="max-w-7xl mx-auto text-center">
          <motion.div
            initial={{ y: 50, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            transition={{ duration: 0.8, delay: 0.2 }}
            className="mb-8"
          >
            <h1 className="text-4xl md:text-6xl lg:text-7xl font-bold mb-6 leading-tight">
              Generate Complex SQL in{" "}
              <span className="bg-gradient-to-r from-cyan-400 via-blue-500 to-purple-600 bg-clip-text text-transparent">
                10 Seconds
              </span>
              <br />— No Coding Required
            </h1>
            <p className="text-xl md:text-2xl text-gray-300 mb-8 max-w-3xl mx-auto">
              Instant SQL generation from natural language descriptions. Transform your ideas into powerful database
              queries effortlessly.
            </p>
          </motion.div>

          <motion.div
            initial={{ y: 50, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            transition={{ duration: 0.8, delay: 0.4 }}
            className="mb-12"
          >
            <motion.button
              whileHover={{ scale: 1.05 }}
              whileTap={{ scale: 0.95 }}
              className="bg-gradient-to-r from-cyan-500 to-blue-600 hover:from-cyan-600 hover:to-blue-700 px-8 py-4 rounded-xl text-lg font-semibold transition-all duration-300 shadow-2xl hover:shadow-cyan-500/25 inline-flex items-center space-x-2"
            >
              <Sparkles className="w-5 h-5" />
              <span>Generate Your First Query Now</span>
              <ChevronRight className="w-5 h-5" />
            </motion.button>
          </motion.div>

          {/* Trust Indicators */}
          <motion.div
            initial={{ y: 50, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            transition={{ duration: 0.8, delay: 0.6 }}
            className="flex flex-col md:flex-row items-center justify-center space-y-4 md:space-y-0 md:space-x-12 text-gray-400"
          >
            <div className="flex items-center space-x-2">
              <div className="flex">
                {[...Array(5)].map((_, i) => (
                  <Star key={i} className="w-5 h-5 text-yellow-400 fill-current" />
                ))}
              </div>
              <span>4.9/5 rating</span>
            </div>
            <div className="flex items-center space-x-2">
              <Users className="w-5 h-5 text-cyan-400" />
              <span>50,000+ developers</span>
            </div>
            <div className="flex items-center space-x-2">
              <Globe className="w-5 h-5 text-purple-400" />
              <span>120+ countries</span>
            </div>
          </motion.div>
        </div>
      </section>

      {/* Feature Cards Grid */}
      <section className="relative z-10 px-6 py-20">
        <div className="max-w-7xl mx-auto">
          <motion.div
            initial={{ y: 50, opacity: 0 }}
            whileInView={{ y: 0, opacity: 1 }}
            transition={{ duration: 0.8 }}
            viewport={{ once: true }}
            className="text-center mb-16"
          >
            <h2 className="text-3xl md:text-5xl font-bold mb-6">
              Powerful AI Features for{" "}
              <span className="bg-gradient-to-r from-cyan-400 to-purple-500 bg-clip-text text-transparent">
                Every Developer
              </span>
            </h2>
            <p className="text-xl text-gray-300 max-w-3xl mx-auto">
              From beginners to experts, our AI-powered tools help you work with SQL more efficiently than ever before.
            </p>
          </motion.div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
            {features.map((feature, index) => (
              <motion.div
                key={index}
                initial={{ y: 50, opacity: 0 }}
                whileInView={{ y: 0, opacity: 1 }}
                transition={{ duration: 0.6, delay: index * 0.1 }}
                viewport={{ once: true }}
                whileHover={{ y: -10, scale: 1.02 }}
                className="bg-gray-800/50 backdrop-blur-sm border border-gray-700 rounded-2xl p-8 hover:border-cyan-500/50 transition-all duration-300 group"
              >
                <div className="text-cyan-400 mb-4 group-hover:scale-110 transition-transform duration-300">
                  {feature.icon}
                </div>
                <h3 className="text-xl font-semibold mb-3 group-hover:text-cyan-400 transition-colors">
                  {feature.title}
                </h3>
                <p className="text-gray-300 leading-relaxed">{feature.description}</p>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* Query Builder Preview */}
      {/* <section className="relative z-10 px-6 py-20">
        <div className="max-w-5xl mx-auto">
          <motion.div
            initial={{ y: 50, opacity: 0 }}
            whileInView={{ y: 0, opacity: 1 }}
            transition={{ duration: 0.8 }}
            viewport={{ once: true }}
            className="text-center mb-16"
          >
            <h2 className="text-3xl md:text-5xl font-bold mb-6">
              See the Magic in{" "}
              <span className="bg-gradient-to-r from-cyan-400 to-purple-500 bg-clip-text text-transparent">Action</span>
            </h2>
            <p className="text-xl text-gray-300">Try our AI-powered SQL generator right now</p>
          </motion.div>

          <motion.div
            initial={{ y: 50, opacity: 0 }}
            whileInView={{ y: 0, opacity: 1 }}
            transition={{ duration: 0.8, delay: 0.2 }}
            viewport={{ once: true }}
            className="bg-gray-800/50 backdrop-blur-sm border border-gray-700 rounded-3xl p-8 md:p-12"
          >
            <div className="mb-8">
              <label className="block text-sm font-medium text-gray-300 mb-3">Choose Tool</label>
              <select className="w-full bg-gray-700 border border-gray-600 rounded-xl px-4 py-3 text-white focus:outline-none focus:border-cyan-500 transition-colors">
                <option>Generate SQL</option>
                <option>Explain SQL</option>
                <option>Optimize SQL</option>
              </select>
            </div>

            <div className="mb-8">
              <label className="block text-sm font-medium text-gray-300 mb-3">
                Describe what you want in natural language
              </label>
              <textarea
                value={inputText}
                onChange={(e) => setInputText(e.target.value)}
                placeholder="e.g., Show me all customers who made purchases in the last 30 days with their total spending"
                className="w-full h-32 bg-gray-700 border border-gray-600 rounded-xl px-4 py-3 text-white placeholder-gray-400 focus:outline-none focus:border-cyan-500 transition-colors resize-none"
              />
            </div>

            <div className="mb-8">
              <label className="block text-sm font-medium text-gray-300 mb-3">Generated SQL</label>
              <div className="bg-gray-900 border border-gray-600 rounded-xl p-4 font-mono text-sm">
                <div className="text-cyan-400">
                  {inputText ? (
                    <>
                      <span className="text-purple-400">SELECT</span> c.customer_id, c.name,
                      <span className="text-yellow-400">SUM</span>(o.total_amount){" "}
                      <span className="text-purple-400">AS</span> total_spending
                      <br />
                      <span className="text-purple-400">FROM</span> customers c<br />
                      <span className="text-purple-400">JOIN</span> orders o <span className="text-purple-400">ON</span>{" "}
                      c.customer_id = o.customer_id
                      <br />
                      <span className="text-purple-400">WHERE</span> o.order_date {">"}{" "}
                      <span className="text-green-400">CURRENT_DATE - INTERVAL 30 DAY</span>
                      <br />
                      <span className="text-purple-400">GROUP BY</span> c.customer_id, c.name
                      <br />
                      <span className="text-purple-400">ORDER BY</span> total_spending{" "}
                      <span className="text-purple-400">DESC</span>;
                    </>
                  ) : (
                    <span className="text-gray-500">Your SQL query will appear here...</span>
                  )}
                </div>
              </div>
            </div>

            <motion.button
              whileHover={{ scale: 1.02 }}
              whileTap={{ scale: 0.98 }}
              className="w-full bg-gradient-to-r from-cyan-500 to-blue-600 hover:from-cyan-600 hover:to-blue-700 py-4 rounded-xl font-semibold text-lg transition-all duration-300 shadow-lg hover:shadow-cyan-500/25 flex items-center justify-center space-x-2"
            >
              <Play className="w-5 h-5" />
              <span>Translate Now</span>
            </motion.button>
          </motion.div>
        </div>
      </section> */}

      {/* Footer */}
      <footer className="relative z-10 px-6 py-12 border-t border-gray-800">
        <div className="max-w-7xl mx-auto">
          <div className="flex flex-col md:flex-row items-center justify-between">
            <div className="flex items-center space-x-2 mb-4 md:mb-0">
              <div className="w-8 h-8 bg-gradient-to-r from-cyan-400 to-blue-500 rounded-lg flex items-center justify-center">
                <Database className="w-5 h-5 text-white" />
              </div>
              <span className="text-xl font-bold bg-gradient-to-r from-cyan-400 to-blue-500 bg-clip-text text-transparent">
                SQLAssist
              </span>
            </div>

            <div className="flex items-center space-x-6 text-gray-400">
              <Link to="/privacy" className="hover:text-cyan-400 transition-colors">
                Privacy
              </Link>
              <Link to="/terms" className="hover:text-cyan-400 transition-colors">
                Terms
              </Link>
              <Link to="/support" className="hover:text-cyan-400 transition-colors">
                Support
              </Link>
            </div>
          </div>

          <div className="mt-8 pt-8 border-t border-gray-800 text-center text-gray-400">
            <p>&copy; {new Date().getFullYear()} SQLAssist. All rights reserved.</p>
          </div>
        </div>
      </footer>

     
    </div>
  )
}
