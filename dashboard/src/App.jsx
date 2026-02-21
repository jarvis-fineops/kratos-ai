import { useState, useEffect } from "react"
import ClusterHealth from "./components/ClusterHealth"
import Predictions from "./components/Predictions"
import Incidents from "./components/Incidents"
import Remediations from "./components/Remediations"
import KnowledgeStats from "./components/KnowledgeStats"
import ActivityFeed from "./components/ActivityFeed"

function App() {
  const [status, setStatus] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetchStatus()
    const interval = setInterval(fetchStatus, 5000)
    return () => clearInterval(interval)
  }, [])

  const fetchStatus = async () => {
    try {
      const res = await fetch("/api/v1/kratos/status")
      const data = await res.json()
      setStatus(data)
      setLoading(false)
    } catch (err) {
      console.error("Failed to fetch status:", err)
      // Use mock data for demo
      setStatus({
        mode: "recommend",
        is_running: true,
        total_incidents: 47,
        total_patterns: 12,
        active_predictions: 3,
        pending_remediations: 2,
        uptime_seconds: 86400
      })
      setLoading(false)
    }
  }

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-900 flex items-center justify-center">
        <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-blue-500"></div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gray-900 text-white">
      {/* Header */}
      <header className="bg-gray-800 border-b border-gray-700">
        <div className="max-w-7xl mx-auto px-4 py-4 flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <div className="w-10 h-10 bg-gradient-to-br from-blue-500 to-purple-600 rounded-lg flex items-center justify-center">
              <span className="text-xl font-bold">K</span>
            </div>
            <div>
              <h1 className="text-xl font-bold">Kratos AI</h1>
              <p className="text-xs text-gray-400">Self-Healing Kubernetes</p>
            </div>
          </div>
          <div className="flex items-center space-x-4">
            <div className="flex items-center space-x-2">
              <div className={`w-2 h-2 rounded-full ${status?.is_running ? "bg-green-500" : "bg-red-500"}`}></div>
              <span className="text-sm text-gray-300">
                {status?.is_running ? "Running" : "Stopped"}
              </span>
            </div>
            <span className="px-3 py-1 bg-blue-500/20 text-blue-400 rounded-full text-sm capitalize">
              {status?.mode} mode
            </span>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 py-6">
        {/* Top Stats */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
          <StatCard
            title="Active Predictions"
            value={status?.active_predictions || 0}
            icon="🔮"
            color="purple"
          />
          <StatCard
            title="Pending Actions"
            value={status?.pending_remediations || 0}
            icon="⚡"
            color="yellow"
          />
          <StatCard
            title="Incidents Learned"
            value={status?.total_incidents || 0}
            icon="📚"
            color="blue"
          />
          <StatCard
            title="Patterns Detected"
            value={status?.total_patterns || 0}
            icon="🧠"
            color="green"
          />
        </div>

        {/* Main Grid */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Left Column - 2/3 width */}
          <div className="lg:col-span-2 space-y-6">
            <ClusterHealth />
            <Predictions />
            <Remediations />
          </div>

          {/* Right Column - 1/3 width */}
          <div className="space-y-6">
            <ActivityFeed />
            <KnowledgeStats stats={status} />
            <Incidents />
          </div>
        </div>
      </main>
    </div>
  )
}

function StatCard({ title, value, icon, color }) {
  const colors = {
    purple: "from-purple-500/20 to-purple-600/20 border-purple-500/30",
    yellow: "from-yellow-500/20 to-yellow-600/20 border-yellow-500/30",
    blue: "from-blue-500/20 to-blue-600/20 border-blue-500/30",
    green: "from-green-500/20 to-green-600/20 border-green-500/30",
  }

  return (
    <div className={`bg-gradient-to-br ${colors[color]} border rounded-xl p-4`}>
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm text-gray-400">{title}</p>
          <p className="text-3xl font-bold mt-1">{value}</p>
        </div>
        <span className="text-3xl">{icon}</span>
      </div>
    </div>
  )
}

export default App
