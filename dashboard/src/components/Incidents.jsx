import { useState, useEffect } from "react"

export default function Incidents() {
  const [incidents, setIncidents] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetchIncidents()
    const interval = setInterval(fetchIncidents, 15000)
    return () => clearInterval(interval)
  }, [])

  const fetchIncidents = async () => {
    try {
      // Fetch cluster events that could be incidents
      const res = await fetch("/api/v1/kratos/cluster/events?limit=50")
      const data = await res.json()
      
      // Filter for warning events and map to incidents format
      const warningEvents = data.events
        .filter(e => e.type === "Warning" || e.reason?.includes("Failed") || e.reason?.includes("Kill"))
        .map((event, idx) => {
          let severity = "medium"
          let type = event.reason?.toLowerCase() || "unknown"
          
          if (event.reason?.includes("OOM") || event.reason?.includes("Kill")) {
            severity = "high"
            type = "oom kill"
          } else if (event.reason?.includes("BackOff") || event.reason?.includes("CrashLoop")) {
            severity = "high" 
            type = "crash loop"
          } else if (event.reason?.includes("Failed")) {
            severity = "medium"
            type = "failed"
          } else if (event.reason?.includes("Unhealthy")) {
            severity = "medium"
            type = "unhealthy"
          }
          
          return {
            id: idx,
            type,
            target: event.object?.split("/")[1] || event.object,
            namespace: event.namespace,
            severity,
            time: event.last_seen ? formatTime(event.last_seen) : "Unknown",
            message: event.message,
            count: event.count
          }
        })
        .slice(0, 10)
      
      setIncidents(warningEvents)
      setLoading(false)
    } catch (err) {
      console.error("Failed to fetch incidents:", err)
      setIncidents([])
      setLoading(false)
    }
  }

  const formatTime = (isoString) => {
    const date = new Date(isoString)
    const now = new Date()
    const diffMs = now - date
    const diffMins = Math.floor(diffMs / 60000)
    
    if (diffMins < 1) return "just now"
    if (diffMins < 60) return `${diffMins}m ago`
    if (diffMins < 1440) return `${Math.floor(diffMins / 60)}h ago`
    return `${Math.floor(diffMins / 1440)}d ago`
  }

  const severityColor = (severity) => {
    const colors = {
      high: "text-red-400",
      medium: "text-yellow-400",
      low: "text-blue-400"
    }
    return colors[severity] || "text-gray-400"
  }

  if (loading) {
    return (
      <div className="bg-gray-800 rounded-xl border border-gray-700 p-6">
        <h2 className="text-lg font-semibold mb-4">📋 Recent Incidents</h2>
        <div className="animate-pulse space-y-3">
          <div className="h-4 bg-gray-700 rounded w-full"></div>
          <div className="h-4 bg-gray-700 rounded w-3/4"></div>
        </div>
      </div>
    )
  }

  return (
    <div className="bg-gray-800 rounded-xl border border-gray-700 p-6">
      <h2 className="text-lg font-semibold mb-4 flex items-center">
        <span className="mr-2">📋</span> Recent Incidents
        <span className="ml-auto text-xs text-gray-500">Live</span>
        <span className="ml-1 w-2 h-2 bg-green-500 rounded-full animate-pulse"></span>
      </h2>

      {incidents.length === 0 ? (
        <div className="text-center py-4 text-gray-400">
          <p className="text-2xl mb-2">✅</p>
          <p className="text-sm">No recent incidents</p>
          <p className="text-xs text-gray-500 mt-1">Cluster is healthy</p>
        </div>
      ) : (
        <div className="space-y-3">
          {incidents.map(incident => (
            <div key={incident.id} className="flex items-center justify-between py-2 border-b border-gray-700 last:border-0">
              <div className="flex-1 min-w-0">
                <p className="font-medium truncate">{incident.type}</p>
                <p className="text-xs text-gray-400 truncate" title={incident.target}>
                  {incident.target}
                  {incident.count > 1 && <span className="ml-1 text-yellow-500">(×{incident.count})</span>}
                </p>
              </div>
              <div className="text-right ml-4">
                <span className={`text-sm font-medium ${severityColor(incident.severity)}`}>
                  {incident.severity}
                </span>
                <p className="text-xs text-gray-500">{incident.time}</p>
              </div>
            </div>
          ))}
        </div>
      )}

      {incidents.length > 0 && (
        <div className="mt-4 pt-2 text-center">
          <button className="text-sm text-blue-400 hover:text-blue-300">
            View all incidents →
          </button>
        </div>
      )}
    </div>
  )
}
