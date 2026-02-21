import { useState } from "react"

export default function Predictions() {
  const [predictions] = useState([
    {
      id: "pred-1",
      type: "oom_kill",
      target: "api-server-7d8f9c",
      namespace: "production",
      probability: 0.87,
      eta_minutes: 12,
      evidence: ["Memory at 92%", "Growth rate 5MB/min", "Similar pod crashed 2x"],
      recommended_action: "scale_memory_up"
    },
    {
      id: "pred-2", 
      type: "crash_loop",
      target: "worker-abc123",
      namespace: "staging",
      probability: 0.72,
      eta_minutes: 25,
      evidence: ["OOM restarts: 3", "Error rate increasing"],
      recommended_action: "restart_pod"
    },
    {
      id: "pred-3",
      type: "resource_exhaustion",
      target: "batch-processor-xyz",
      namespace: "production",
      probability: 0.65,
      eta_minutes: 45,
      evidence: ["CPU at 85%", "Queue backlog growing"],
      recommended_action: "scale_replicas_up"
    }
  ])

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
      node_not_ready: "🖥️"
    }
    return icons[type] || "⚠️"
  }

  return (
    <div className="bg-gray-800 rounded-xl border border-gray-700 p-6">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-semibold flex items-center">
          <span className="mr-2">🔮</span> Active Predictions
        </h2>
        <span className="text-sm text-gray-400">{predictions.length} active</span>
      </div>

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

            {/* Evidence */}
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

            {/* Action */}
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
    </div>
  )
}
