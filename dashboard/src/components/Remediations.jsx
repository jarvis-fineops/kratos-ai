import { useState, useEffect } from "react"

export default function Remediations() {
  const [remediations, setRemediations] = useState([])
  const [loading, setLoading] = useState(true)
  const [executing, setExecuting] = useState(null)

  useEffect(() => {
    fetchRemediations()
    const interval = setInterval(fetchRemediations, 10000)
    return () => clearInterval(interval)
  }, [])

  const fetchRemediations = async () => {
    try {
      const podsRes = await fetch("/api/v1/kratos/cluster/pods")
      const podsData = await podsRes.json()
      
      const suggestions = podsData.pods
        .filter(pod => pod.restarts > 0 || pod.status === "Pending")
        .map((pod, idx) => {
          let action = "monitor"
          let status = "suggested"
          let risk = "low"
          
          if (pod.restarts > 5) {
            action = "restart_pod"
            status = "pending approval"
            risk = "medium"
          } else if (pod.restarts > 2) {
            action = "scale_memory_up"
            status = "pending approval"
            risk = "low"
          } else if (pod.status === "Pending") {
            action = "check_resources"
            status = "suggested"
            risk = "low"
          } else if (pod.restarts > 0) {
            action = "monitor"
            status = "watching"
            risk = "low"
          }
          
          return {
            id: idx,
            action,
            target: pod.name,
            namespace: pod.namespace,
            status,
            risk,
            when: `${pod.restarts} restarts`,
            restarts: pod.restarts
          }
        })
        .filter(r => r.action !== "monitor" || r.restarts > 0)
        .sort((a, b) => b.restarts - a.restarts)
        .slice(0, 5)
      
      setRemediations(suggestions)
      setLoading(false)
    } catch (err) {
      console.error("Failed to fetch remediations:", err)
      setRemediations([])
      setLoading(false)
    }
  }

  const executeRemediation = async (rem, approved) => {
    if (!approved) {
      // Just remove from list on reject
      setRemediations(prev => prev.filter(r => r.id !== rem.id))
      return
    }
    
    setExecuting(rem.id)
    try {
      const res = await fetch("/api/v1/kratos/remediation/execute", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          action: rem.action,
          pod_name: rem.target,
          namespace: rem.namespace,
          parameters: {}
        })
      })
      
      const result = await res.json()
      
      if (result.status === "success") {
        // Update status to completed
        setRemediations(prev => prev.map(r => 
          r.id === rem.id ? { ...r, status: "completed" } : r
        ))
        // Refresh after action
        setTimeout(fetchRemediations, 3000)
      } else {
        alert(`Failed: ${result.message || result.detail}`)
      }
    } catch (err) {
      console.error("Remediation failed:", err)
      alert("Remediation failed: " + err.message)
    }
    setExecuting(null)
  }

  const statusColor = (status) => {
    const colors = {
      "pending approval": "bg-yellow-500/20 text-yellow-400",
      "completed": "bg-green-500/20 text-green-400",
      "suggested": "bg-blue-500/20 text-blue-400",
      "watching": "bg-gray-500/20 text-gray-400",
      "failed": "bg-red-500/20 text-red-400",
      "executing": "bg-purple-500/20 text-purple-400"
    }
    return colors[status] || "bg-gray-500/20 text-gray-400"
  }

  const riskColor = (risk) => {
    const colors = {
      high: "text-red-400",
      medium: "text-yellow-400",
      low: "text-green-400"
    }
    return colors[risk] || "text-gray-400"
  }

  if (loading) {
    return (
      <div className="bg-gray-800 rounded-xl border border-gray-700 p-6">
        <h2 className="text-lg font-semibold mb-4">⚡ Remediations</h2>
        <div className="animate-pulse">
          <div className="h-20 bg-gray-700 rounded"></div>
        </div>
      </div>
    )
  }

  return (
    <div className="bg-gray-800 rounded-xl border border-gray-700 p-6">
      <h2 className="text-lg font-semibold mb-4 flex items-center">
        <span className="mr-2">⚡</span> Remediations
        <span className="ml-auto text-xs text-gray-500">Live</span>
        <span className="ml-1 w-2 h-2 bg-green-500 rounded-full animate-pulse"></span>
      </h2>

      {remediations.length === 0 ? (
        <div className="text-center py-6 text-gray-400">
          <p className="text-2xl mb-2">✨</p>
          <p className="text-sm">No remediations needed</p>
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-gray-400 text-left">
                <th className="pb-3">Action</th>
                <th className="pb-3">Target</th>
                <th className="pb-3">Status</th>
                <th className="pb-3">Risk</th>
                <th className="pb-3">Info</th>
                <th className="pb-3"></th>
              </tr>
            </thead>
            <tbody>
              {remediations.map(rem => (
                <tr key={rem.id} className="border-t border-gray-700">
                  <td className="py-3 font-medium">{rem.action.replace(/_/g, " ")}</td>
                  <td className="py-3">
                    <span title={rem.target}>
                      {rem.target.length > 20 ? rem.target.substring(0, 20) + "..." : rem.target}
                    </span>
                    <span className="text-gray-500 ml-1 text-xs">{rem.namespace}</span>
                  </td>
                  <td className="py-3">
                    <span className={`px-2 py-0.5 rounded text-xs ${statusColor(executing === rem.id ? "executing" : rem.status)}`}>
                      {executing === rem.id ? "executing..." : rem.status}
                    </span>
                  </td>
                  <td className={`py-3 ${riskColor(rem.risk)}`}>{rem.risk}</td>
                  <td className="py-3 text-gray-400">{rem.when}</td>
                  <td className="py-3">
                    {rem.status === "pending approval" && (
                      <div className="flex gap-1">
                        <button 
                          onClick={() => executeRemediation(rem, true)}
                          disabled={executing === rem.id}
                          className="px-2 py-1 bg-green-600 hover:bg-green-700 disabled:opacity-50 rounded text-xs"
                        >
                          {executing === rem.id ? "..." : "Approve"}
                        </button>
                        <button 
                          onClick={() => executeRemediation(rem, false)}
                          disabled={executing === rem.id}
                          className="px-2 py-1 bg-red-600 hover:bg-red-700 disabled:opacity-50 rounded text-xs"
                        >
                          Reject
                        </button>
                      </div>
                    )}
                    {rem.status === "completed" && (
                      <span className="text-green-400 text-xs">✓ Done</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
