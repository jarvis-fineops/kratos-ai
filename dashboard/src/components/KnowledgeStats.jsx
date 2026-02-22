import { useState, useEffect } from "react"

export default function KnowledgeStats() {
  const [stats, setStats] = useState(null)
  const [loading, setLoading] = useState(true)
  const [learning, setLearning] = useState(false)

  useEffect(() => {
    fetchStats()
    // Also trigger learning on mount
    triggerLearning()
    const interval = setInterval(() => {
      fetchStats()
      triggerLearning()
    }, 30000)  // Learn every 30 seconds
    return () => clearInterval(interval)
  }, [])

  const triggerLearning = async () => {
    try {
      await fetch("/api/v1/kratos/learn/record-events", { method: "POST" })
    } catch (err) {
      console.error("Learning failed:", err)
    }
  }

  const fetchStats = async () => {
    try {
      const res = await fetch("/api/v1/kratos/learn/stats")
      const data = await res.json()
      
      setStats({
        incidents: data.total_incidents || 0,
        patterns: data.total_patterns || 0,
        remediations: data.total_remediations || 0,
        recentIncidents: data.recent_incidents || [],
        recentRemediations: data.recent_remediations || [],
        patternsList: data.patterns || []
      })
      setLoading(false)
    } catch (err) {
      console.error("Failed to fetch stats:", err)
      setStats({
        incidents: 0,
        patterns: 0,
        remediations: 0,
        recentIncidents: [],
        recentRemediations: [],
        patternsList: []
      })
      setLoading(false)
    }
  }

  const handleLearnNow = async () => {
    setLearning(true)
    await triggerLearning()
    await fetchStats()
    setLearning(false)
  }

  if (loading) {
    return (
      <div className="bg-gray-800 rounded-xl border border-gray-700 p-6">
        <h2 className="text-lg font-semibold mb-4">🧠 Knowledge Base</h2>
        <div className="animate-pulse space-y-3">
          <div className="h-4 bg-gray-700 rounded w-3/4"></div>
          <div className="h-4 bg-gray-700 rounded w-1/2"></div>
        </div>
      </div>
    )
  }

  return (
    <div className="bg-gray-800 rounded-xl border border-gray-700 p-6">
      <h2 className="text-lg font-semibold mb-4 flex items-center">
        <span className="mr-2">🧠</span> Knowledge Base
        <span className="ml-auto text-xs text-gray-500">Learning</span>
        <span className="ml-1 w-2 h-2 bg-purple-500 rounded-full animate-pulse"></span>
      </h2>

      <div className="space-y-3">
        <div className="flex justify-between">
          <span className="text-gray-400">Incidents Learned</span>
          <span className="font-medium text-blue-400">{stats?.incidents || 0}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-gray-400">Patterns Detected</span>
          <span className="font-medium text-purple-400">{stats?.patterns || 0}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-gray-400">Remediations</span>
          <span className="font-medium text-green-400">{stats?.remediations || 0}</span>
        </div>
      </div>

      {stats?.patternsList?.length > 0 && (
        <div className="mt-4 pt-4 border-t border-gray-700">
          <p className="text-sm text-gray-400 mb-2">Detected Patterns</p>
          <div className="space-y-2">
            {stats.patternsList.slice(0, 5).map((pattern, idx) => (
              <div key={idx} className="flex justify-between text-sm">
                <span className="text-gray-300">
                  {pattern.type.replace(/_/g, " ")} 
                  <span className="text-gray-500 text-xs ml-1">({pattern.namespace})</span>
                </span>
                <span className="text-yellow-400">×{pattern.count}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="mt-4 pt-4 border-t border-gray-700">
        <button
          onClick={handleLearnNow}
          disabled={learning}
          className="w-full py-2 bg-purple-600 hover:bg-purple-700 disabled:opacity-50 rounded text-sm transition"
        >
          {learning ? "Learning..." : "Learn from Current Events"}
        </button>
      </div>

      {stats?.incidents === 0 && (
        <p className="text-gray-500 text-xs mt-2 text-center">
          Click above to start learning from cluster events
        </p>
      )}
    </div>
  )
}
