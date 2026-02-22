import { useState, useEffect } from "react"

export default function Predictions() {
  const [predictions, setPredictions] = useState([])
  const [pods, setPods] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetchData()
    const interval = setInterval(fetchData, 10000)
    return () => clearInterval(interval)
  }, [])

  const fetchData = async () => {
    try {
      // Fetch pods with potential issues
      const podsRes = await fetch("/api/v1/kratos/cluster/pods")
      const podsData = await podsRes.json()
      
      // Analyze pods for potential issues
      const analyzedPods = podsData.pods
        .filter(pod => pod.status === "Running" || pod.status === "Pending")
        .map(pod => {
          // Generate predictions based on pod status
          let probability = 0
          let type = "healthy"
          let evidence = []
          let eta = 0
          
          if (pod.restarts > 5) {
            probability = 0.85
            type = "crash_loop"
            evidence = [`Restarts: ${pod.restarts}`, "High restart count"]
            eta = 10
          } else if (pod.restarts > 2) {
            probability = 0.65
            type = "crash_loop"
            evidence = [`Restarts: ${pod.restarts}`, "Moderate restart count"]
            eta = 30
          } else if (pod.status === "Pending") {
            probability = 0.7
            type = "scheduling_issue"
            evidence = ["Pod pending", "Resource constraints possible"]
            eta = 15
          }
          
          return {
            id: pod.name,
            type,
            target: pod.name,
            namespace: pod.namespace,
            probability,
            eta_minutes: eta,
            evidence,
            recommended_action: type === "crash_loop" ? "restart_pod" : "scale_resources"
          }
        })
        .filter(p => p.probability > 0)
        .sort((a, b) => b.probability - a.probability)
        .slice(0, 5)
      
      setPredictions(analyzedPods)
      setPods(podsData.pods)
      setLoading(false)
    } catch (err) {
      console.error("Failed to fetch predictions:", err)
      setPredictions([])
      setLoading(false)
    }
  }

  const severityColor = (prob) => {
    if (prob >= 0.8) return "text-red-400 bg-red-500/20"
    if (prob >= 0.6) return "text-yellow-400 bg-yellow-500/20"
    return "text-blue-400 bg-blue-500/20"
  }

  const typeIcon = (type) => {
    const icons = {
      oom_kill: "💀",
      crash_loop: "🔄",
      resource_exhaustion: "📈",
      scheduling_issue: "📦",
      node_not_ready: "🖥️",
      healthy: "✅"
    }
    return icons[type] || "⚠️"
  }

  if (loading) {
    return (
      <div className="bg-gray-800 rounded-xl border border-gray-700 p-6">
        <h2 className="text-lg font-semibold mb-4">🔮 Active Predictions</h2>
        <div className="animate-pulse space-y-4">
          <div className="h-20 bg-gray-700 rounded"></div>
          <div className="h-20 bg-gray-700 rounded"></div>
        </div>
      </div>
    )
  }

  return (
    <div className="bg-gray-800 rounded-xl border border-gray-700 p-6">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-semibold flex items-center">
          <span className="mr-2">🔮</span> Active Predictions
          <span className="ml-2 text-xs text-gray-500">Live</span>
          <span className="ml-1 w-2 h-2 bg-green-500 rounded-full animate-pulse"></span>
        </h2>
        <span className="text-sm text-gray-400">{predictions.length} active</span>
      </div>

      {predictions.length === 0 ? (
        <div className="text-center py-8 text-gray-400">
          <p className="text-4xl mb-2">✨</p>
          <p>All pods are healthy!</p>
          <p className="text-sm mt-1">No issues predicted</p>
        </div>
      ) : (
        <div className="space-y-4">
          {predictions.map(pred => (
            <div key={pred.id} className="bg-gray-700/50 rounded-lg p-4 border border-gray-600">
              <div className="flex items-start justify-between">
                <div className="flex items-start space-x-3">
                  <span className="text-2xl">{typeIcon(pred.type)}</span>
                  <div>
                    <div className="flex items-center space-x-2">
                      <span className="font-medium">{pred.target}</span>
                      <span className="text-xs px-2 py-0.5 bg-gray-600 rounded">
                        {pred.namespace}
                      </span>
                    </div>
                    <p className="text-sm text-gray-400 mt-1">
                      {pred.type.replace(/_/g, " ").toUpperCase()}
                    </p>
                  </div>
                </div>
                <div className="text-right">
                  <span className={`px-2 py-1 rounded text-sm font-medium ${severityColor(pred.probability)}`}>
                    {Math.round(pred.probability * 100)}%
                  </span>
                  <p className="text-xs text-gray-400 mt-1">
                    ETA: {pred.eta_minutes}min
                  </p>
                </div>
              </div>

              <div className="mt-3 pt-3 border-t border-gray-600">
                <p className="text-xs text-gray-400 mb-2">Evidence:</p>
                <div className="flex flex-wrap gap-2">
                  {pred.evidence.map((ev, i) => (
                    <span key={i} className="text-xs px-2 py-1 bg-gray-600 rounded">
                      {ev}
                    </span>
                  ))}
                </div>
              </div>

              <div className="mt-3 flex items-center justify-between">
                <span className="text-sm text-gray-400">
                  Recommended: <span className="text-blue-400">{pred.recommended_action.replace(/_/g, " ")}</span>
                </span>
                <button className="px-3 py-1 bg-blue-500 hover:bg-blue-600 rounded text-sm transition">
                  Apply
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
