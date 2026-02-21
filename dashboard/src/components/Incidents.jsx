import { useState } from "react"

export default function Incidents() {
  const [incidents] = useState([
    {
      id: "inc-1",
      type: "oom_kill",
      target: "api-server-old",
      severity: "high",
      time: "1h ago",
      resolved: true
    },
    {
      id: "inc-2",
      type: "crash_loop",
      target: "worker-def456",
      severity: "medium",
      time: "3h ago",
      resolved: true
    },
    {
      id: "inc-3",
      type: "node_not_ready",
      target: "node-3",
      severity: "high",
      time: "6h ago",
      resolved: true
    }
  ])

  const severityColors = {
    high: "text-red-400",
    medium: "text-yellow-400",
    low: "text-blue-400"
  }

  return (
    <div className="bg-gray-800 rounded-xl border border-gray-700 p-6">
      <h2 className="text-lg font-semibold mb-4 flex items-center">
        <span className="mr-2">📋</span> Recent Incidents
      </h2>

      <div className="space-y-3">
        {incidents.map(inc => (
          <div key={inc.id} className="flex items-center justify-between text-sm py-2 border-b border-gray-700/50">
            <div>
              <p className="font-medium">{inc.type.replace(/_/g, " ")}</p>
              <p className="text-xs text-gray-400">{inc.target}</p>
            </div>
            <div className="text-right">
              <span className={severityColors[inc.severity]}>{inc.severity}</span>
              <p className="text-xs text-gray-400">{inc.time}</p>
            </div>
          </div>
        ))}
      </div>

      <button className="w-full mt-4 py-2 text-sm text-gray-400 hover:text-white transition">
        View all incidents →
      </button>
    </div>
  )
}
