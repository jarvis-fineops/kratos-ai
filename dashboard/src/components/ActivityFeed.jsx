import { useState, useEffect } from "react"

export default function ActivityFeed() {
  const [activities] = useState([
    { id: 1, type: "prediction", message: "Predicted OOM for api-server-7d8f9c", time: "2s ago", icon: "🔮" },
    { id: 2, type: "remediation", message: "Scaled memory for cache-server", time: "2m ago", icon: "⚡" },
    { id: 3, type: "incident", message: "Detected CrashLoopBackOff", time: "5m ago", icon: "🚨" },
    { id: 4, type: "learning", message: "New pattern detected: OOM in production", time: "8m ago", icon: "🧠" },
    { id: 5, type: "remediation", message: "Restarted pod worker-abc123", time: "15m ago", icon: "⚡" },
    { id: 6, type: "prediction", message: "Resource exhaustion risk identified", time: "20m ago", icon: "🔮" },
  ])

  return (
    <div className="bg-gray-800 rounded-xl border border-gray-700 p-6">
      <h2 className="text-lg font-semibold mb-4 flex items-center">
        <span className="mr-2">📡</span> Live Activity
      </h2>

      <div className="space-y-3 max-h-80 overflow-y-auto">
        {activities.map(activity => (
          <div key={activity.id} className="flex items-start space-x-3 text-sm">
            <span className="text-lg">{activity.icon}</span>
            <div className="flex-1">
              <p className="text-gray-300">{activity.message}</p>
              <p className="text-xs text-gray-500">{activity.time}</p>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
