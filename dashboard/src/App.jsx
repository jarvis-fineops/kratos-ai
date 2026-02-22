import { useState, useEffect } from "react"
import ClusterHealth from "./components/ClusterHealth"
import Predictions from "./components/Predictions"
import Incidents from "./components/Incidents"
import Remediations from "./components/Remediations"
import KnowledgeStats from "./components/KnowledgeStats"
import ActivityFeed from "./components/ActivityFeed"

function App() {
  const [status, setStatus] = useState(null)
  const [clusterHealth, setClusterHealth] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetchAllData()
    const interval = setInterval(fetchAllData, 5000)
    return () => clearInterval(interval)
  }, [])

  const fetchAllData = async () => {
    try {
      const [statusRes, healthRes] = await Promise.all([
        fetch("/api/v1/kratos/status"),
        fetch("/api/v1/kratos/cluster/health")
      ])
      
      const statusData = await statusRes.json()
      const healthData = await healthRes.json()
      
      setStatus({
        ...statusData,
        is_running: true  // API is responding, so Kratos is running
      })
      setClusterHealth(healthData)
      setLoading(false)
    } catch (err) {
      console.error("Failed to fetch data:", err)
      setStatus({
        mode: "recommend",
        is_running: false,
        total_incidents: 0,
        total_patterns: 0,
        active_predictions: 0,
        pending_remediations: 0,
        uptime_seconds: 0
      })
      setLoading(false)
    }
  }

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-900 flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-blue-500 mx-auto"></div>
          <p className="mt-4 text-gray-400">Connecting to Kratos...</p>
        </div>
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
              <div className={`w-2 h-2 rounded-full ${status?.is_running ? "bg-green-500 animate-pulse" : "bg-red-500"}`}></div>
              <span className="text-sm text-gray-300">
                {status?.is_running ? "Connected" : "Disconnected"}
              </span>
            </div>
            <span className="px-3 py-1 bg-blue-500/20 text-blue-400 rounded-full text-sm capitalize">
              {status?.mode || "recommend"} mode
            </span>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 py-6">
        {/* Top Stats */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
          <StatCard 
            title="Cluster Nodes" 
            value={`${clusterHealth?.ready_nodes || 0}/${clusterHealth?.total_nodes || 0}`}
            icon="🖥️"
            color="blue"
          />
          <StatCard 
            title="Running Pods" 
            value={`${clusterHealth?.running_pods || 0}/${clusterHealth?.total_pods || 0}`}
            icon="📦"
            color="green"
          />
          <StatCard 
            title="Incidents Learned" 
            value={status?.total_incidents || 0}
            icon="📚"
            color="purple"
          />
          <StatCard 
            title="Namespaces" 
            value={clusterHealth?.namespaces?.length || 0}
            icon="🏷️"
            color="orange"
          />
        </div>

        {/* Main Grid */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Left Column */}
          <div className="lg:col-span-2 space-y-6">
            <ClusterHealth />
            <Predictions />
            <Remediations />
          </div>

          {/* Right Column */}
          <div className="space-y-6">
            <ActivityFeed />
            <KnowledgeStats />
            <Incidents />
          </div>
        </div>
      </main>
    </div>
  )
}

function StatCard({ title, value, icon, color }) {
  const colors = {
    blue: "from-blue-500/20 to-blue-600/10 border-blue-500/30",
    green: "from-green-500/20 to-green-600/10 border-green-500/30",
    purple: "from-purple-500/20 to-purple-600/10 border-purple-500/30",
    orange: "from-orange-500/20 to-orange-600/10 border-orange-500/30",
    red: "from-red-500/20 to-red-600/10 border-red-500/30"
  }

  return (
    <div className={`bg-gradient-to-br ${colors[color]} rounded-xl border p-4`}>
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm text-gray-400">{title}</p>
          <p className="text-2xl font-bold mt-1">{value}</p>
        </div>
        <span className="text-3xl opacity-50">{icon}</span>
      </div>
    </div>
  )
}

export default App
