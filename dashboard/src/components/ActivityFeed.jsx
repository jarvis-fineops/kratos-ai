import { useState, useEffect } from "react"

export default function ActivityFeed() {
  const [activities, setActivities] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetchEvents()
    const interval = setInterval(fetchEvents, 15000)
    return () => clearInterval(interval)
  }, [])

  const fetchEvents = async () => {
    try {
      const res = await fetch("/api/v1/kratos/cluster/events?limit=20")
      const data = await res.json()
      
      const formattedEvents = data.events.map((event, idx) => {
        let icon = "📋"
        if (event.type === "Warning") icon = "⚠️"
        if (event.type === "Normal" && event.reason === "Scheduled") icon = "📦"
        if (event.reason === "Pulling" || event.reason === "Pulled") icon = "🐳"
        if (event.reason === "Started") icon = "🚀"
        if (event.reason === "Created") icon = "✨"
        if (event.reason === "Killing" || event.reason === "Unhealthy") icon = "🚨"
        if (event.reason === "FailedScheduling") icon = "❌"
        
        return {
          id: idx,
          type: event.type.toLowerCase(),
          icon,
          message: `[${event.reason}] ${event.message?.substring(0, 60) || "No message"}...`,
          object: event.object,
          namespace: event.namespace,
          time: event.last_seen ? formatTime(event.last_seen) : "Unknown",
          count: event.count
        }
      })
      
      setActivities(formattedEvents)
      setLoading(false)
    } catch (err) {
      console.error("Failed to fetch events:", err)
      setActivities([
        { id: 1, type: "info", message: "Waiting for cluster events...", time: "now", icon: "⏳" }
      ])
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

  if (loading) {
    return (
      <div className="bg-gray-800 rounded-xl border border-gray-700 p-6">
        <h2 className="text-lg font-semibold mb-4">📡 Live Activity</h2>
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
        <span className="mr-2">📡</span> Cluster Events
        <span className="ml-auto text-xs text-gray-500">Live</span>
        <span className="ml-1 w-2 h-2 bg-green-500 rounded-full animate-pulse"></span>
      </h2>

      <div className="space-y-3 max-h-80 overflow-y-auto">
        {activities.length === 0 ? (
          <p className="text-gray-400 text-sm">No recent events</p>
        ) : (
          activities.map(activity => (
            <div key={activity.id} className={"flex items-start space-x-3 text-sm p-2 rounded " + 
              (activity.type === "warning" ? "bg-yellow-900/20" : "")}>
              <span className="text-lg">{activity.icon}</span>
              <div className="flex-1 min-w-0">
                <p className="text-gray-300 truncate">{activity.message}</p>
                <p className="text-xs text-gray-500">
                  {activity.object} • {activity.time}
                  {activity.count > 1 && <span className="ml-1 text-yellow-500">(×{activity.count})</span>}
                </p>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  )
}
