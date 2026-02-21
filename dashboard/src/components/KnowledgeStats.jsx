export default function KnowledgeStats({ stats }) {
  const formatUptime = (seconds) => {
    const hours = Math.floor(seconds / 3600)
    const minutes = Math.floor((seconds % 3600) / 60)
    return `${hours}h ${minutes}m`
  }

  return (
    <div className="bg-gray-800 rounded-xl border border-gray-700 p-6">
      <h2 className="text-lg font-semibold mb-4 flex items-center">
        <span className="mr-2">🧠</span> Knowledge Base
      </h2>

      <div className="space-y-4">
        <div className="flex justify-between items-center">
          <span className="text-gray-400">Incidents Learned</span>
          <span className="font-medium">{stats?.total_incidents || 0}</span>
        </div>
        <div className="flex justify-between items-center">
          <span className="text-gray-400">Patterns Detected</span>
          <span className="font-medium">{stats?.total_patterns || 0}</span>
        </div>
        <div className="flex justify-between items-center">
          <span className="text-gray-400">Uptime</span>
          <span className="font-medium">{formatUptime(stats?.uptime_seconds || 0)}</span>
        </div>
        <div className="flex justify-between items-center">
          <span className="text-gray-400">Mode</span>
          <span className="capitalize px-2 py-1 bg-blue-500/20 text-blue-400 rounded text-sm">
            {stats?.mode || "unknown"}
          </span>
        </div>
      </div>

      {/* Pattern Types */}
      <div className="mt-4 pt-4 border-t border-gray-700">
        <p className="text-sm text-gray-400 mb-3">Top Patterns</p>
        <div className="space-y-2">
          <div className="flex justify-between text-sm">
            <span>OOM Kill Prevention</span>
            <span className="text-green-400">87% success</span>
          </div>
          <div className="flex justify-between text-sm">
            <span>CrashLoop Recovery</span>
            <span className="text-green-400">92% success</span>
          </div>
          <div className="flex justify-between text-sm">
            <span>Resource Scaling</span>
            <span className="text-yellow-400">75% success</span>
          </div>
        </div>
      </div>
    </div>
  )
}
