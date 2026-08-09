import React from "react";
import { motion } from "framer-motion"
import { Database, ArrowLeft } from "lucide-react"
import { Link } from "react-router";

export default function ContactPage() {
  return (
    <div className="min-h-screen bg-gray-900 text-white">
      <div className="max-w-4xl mx-auto px-6 py-12">
        <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} className="mb-8">
          <Link
            to="/"
            className="inline-flex items-center space-x-2 text-cyan-400 hover:text-cyan-300 transition-colors mb-6"
          >
            <ArrowLeft className="w-4 h-4" />
            <span>Back to Home</span>
          </Link>

          <h1 className="text-4xl font-bold mb-4">Contact Us</h1>
          <p className="text-gray-300 text-lg">Get in touch with our team</p>
        </motion.div>

        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2 }}
          className="bg-gray-800 rounded-2xl p-8"
        >
          <div className="text-center py-20">
            <Database className="w-16 h-16 text-cyan-400 mx-auto mb-4" />
            <h2 className="text-2xl font-semibold mb-2">Contact Form</h2>
            <p className="text-gray-400">Contact form coming soon.</p>
          </div>
        </motion.div>
      </div>
    </div>
  )
}
