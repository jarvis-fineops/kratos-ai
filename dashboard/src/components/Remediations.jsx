import { useState } from "react"

export default function Remediations() {
  const [remediations] = useState([
    {
      id: "rem-1",
      action: "scale_memory_up",
      target: "cache-server-abc",
      namespace: "production",
      status: "pending_approval",
      created_at: "2 min ago",
      explanation: "Memory at 94%, predicted OOM in 8 minutes. Recommend scaling from 512Mi to 1Gi.",
      risk: "low"
    },
    {
      id: "rem-2",
      action: "restart_pod",
      target: "api-gateway-xyz",
      namespace: "production",
      status: "completed",
      created_at: "15 min ago",
      explanation: "Pod in CrashLoopBackOff. Restart resolved the issue.",
      risk: "low"
    },
    {
      id: "rem-3",
      action: "scale_replicas_up",
      target: "worker-deployment",
      namespace: "staging",
      status: "pending_approval",
      created_at: "5 min ago",
      explanation: "Queue backlog growing. Recommend scaling from 3 to 5 replicas.",
      risk: "medium"
    }
  ])

  const statusColors = {
    pending_approval: "text-yellow-400 bg-yellow-500/20",
    in_progress: "text-blue-400 bg-blue-500/20",
    completed: "text-green-400 bg-green-500/20",
    failed: "text-red-400 bg-red-500/20"
  }

  const riskColors = {
    low: "text-green-400",
    medium: "text-yellow-400",
    high: "text-red-400"
  }

  return (
    <div className="bg-gray-800 rounded-xl border border-gray-700 p-6">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-semibold flex items-center">
          <span className="mr-2">⚡</span> Remediations
        </h2>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-gray-400 border-b border-gray-700">
              <th className="pb-3">Action</th>
              <th className="pb-3">Target</th>
              <th className="pb-3">Status</th>
              <th className="pb-3">Risk</th>
              <th className="pb-3">When</th>
              <th className="pb-3"></th>
            </tr>
          </thead>
          <tbody>
            {remediations.map(rem => (
              <tr key={rem.id} className="border-b border-gray-700/50">
                <td className="py-3">
                  <span className="font-medium">{rem.action.replace(/_/g, " ")}</span>
                </td>
                <td className="py-3">
                  <div>
                    <span>{rem.target}</span>
                    <span className="text-xs text-gray-400 ml-2">{rem.namespace}</span>
                  </div>
                </td>
                <td className="py-3">
                  <span className={`px-2 py-1 rounded text-xs ${statusColors[rem.status]}`}>
                    {rem.status.replace(/_/g, " ")}
                  </span>
                </td>
                <td className="py-3">
                  <span className={riskColors[rem.risk]}>{rem.risk}</span>
                </td>
                <td className="py-3 text-gray-400">{rem.created_at}</td>
                <td className="py-3">
                  {rem.status === "pending_approval" && (
                    <div className="flex space-x-2">
                      <button className="px-2 py-1 bg-green-500/20 text-green-400 rounded text-xs hover:bg-green-500/30">
                        Approve
                      </button>
                      <button className="px-2 py-1 bg-red-500/20 text-red-400 rounded text-xs hover:bg-red-500/30">
                        Reject
                      </button>
                    </div>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
