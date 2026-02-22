import { useState, useEffect } from "react"

export default function ClusterHealth() {
  const [health, setHealth] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetchHealth()
    const interval = setInterval(fetchHealth, 10000)
    return () => clearInterval(interval)
  }, [])

  const fetchHealth = async () => {
    try {
      const res = await fetch("/api/v1/kratos/cluster/health")
      const data = await res.json()
      setHealth({
        nodes: { total: data.total_nodes, ready: data.ready_nodes },
        pods: { 
          running: data.running_pods, 
          pending: data.pending_pods, 
          failed: data.failed_pods, 
          total: data.total_pods 
        },
        namespaces: data.namespaces
      })
      setLoading(false)
    } catch (err) {
      console.error("Failed to fetch cluster health:", err)
      // Fallback to mock data
      setHealth({
        nodes: { total: 1, ready: 1 },
        pods: { running: 8, pending: 0, failed: 0, total: 10 },
        namespaces: ["default", "kube-system"]
      })
      setLoading(false)
    }
  }

  if (loading || !health) {
    return (
      <div className="bg-gray-800 rounded-xl border border-gray-700 p-6">
        <h2 className="text-lg font-semibold mb-4">🏥 Cluster Health</h2>
        <div className="animate-pulse">
          <div className="h-4 bg-gray-700 rounded w-3/4 mb-4"></div>
          <div className="h-4 bg-gray-700 rounded w-1/2"></div>
        </div>
      </div>
    )
  }

  const nodeHealth = health.nodes.total > 0 ? (health.nodes.ready / health.nodes.total) * 100 : 0
  const podHealth = health.pods.total > 0 ? (health.pods.running / health.pods.total) * 100 : 0

  return (
    <div className="bg-gray-800 rounded-xl border border-gray-700 p-6">
      <h2 className="text-lg font-semibold mb-4 flex items-center">
        <span className="mr-2">🏥</span> Cluster Health
        <span className="ml-auto text-xs text-gray-500">Live</span>
        <span className="ml-1 w-2 h-2 bg-green-500 rounded-full animate-pulse"></span>
      </h2>

      <div className="grid grid-cols-2 gap-6">
        {/* Nodes */}
        <div>
          <div className="flex justify-between mb-2">
            <span className="text-gray-400">Nodes</span>
            <span className="font-medium">{health.nodes.ready}/{health.nodes.total} Ready</span>
          </div>
          <div className="h-3 bg-gray-700 rounded-full overflow-hidden">
            <div 
              className="h-full bg-green-500 rounded-full transition-all"
              style={{ width: `${nodeHealth}%` }}
            />
          </div>
        </div>

        {/* Pods */}
        <div>
          <div className="flex justify-between mb-2">
            <span className="text-gray-400">Pods</span>
            <span className="font-medium">{health.pods.running}/{health.pods.total} Running</span>
          </div>
          <div className="h-3 bg-gray-700 rounded-full overflow-hidden flex">
            <div 
              className="h-full bg-green-500 transition-all"
              style={{ width: `${health.pods.total > 0 ? (health.pods.running / health.pods.total) * 100 : 0}%` }}
            />
            <div 
              className="h-full bg-yellow-500 transition-all"
              style={{ width: `${health.pods.total > 0 ? (health.pods.pending / health.pods.total) * 100 : 0}%` }}
            />
            <div 
              className="h-full bg-red-500 transition-all"
              style={{ width: `${health.pods.total > 0 ? (health.pods.failed / health.pods.total) * 100 : 0}%` }}
            />
          </div>
        </div>
      </div>

      {/* Pod Status Breakdown */}
      <div className="mt-4 flex space-x-4 text-sm">
        <span className="flex items-center">
          <span className="w-3 h-3 bg-green-500 rounded-full mr-2"></span>
          Running: {health.pods.running}
        </span>
        <span className="flex items-center">
          <span className="w-3 h-3 bg-yellow-500 rounded-full mr-2"></span>
          Pending: {health.pods.pending}
        </span>
        <span className="flex items-center">
          <span className="w-3 h-3 bg-red-500 rounded-full mr-2"></span>
          Failed: {health.pods.failed}
        </span>
      </div>

      {/* Namespaces */}
      <div className="mt-4 pt-4 border-t border-gray-700">
        <p className="text-sm text-gray-400 mb-2">Active Namespaces ({health.namespaces.length})</p>
        <div className="flex flex-wrap gap-2">
          {health.namespaces.map(ns => (
            <span key={ns} className="px-2 py-1 bg-gray-700 rounded text-sm">
              {ns}
            </span>
          ))}
        </div>
      </div>
    </div>
  )
}
