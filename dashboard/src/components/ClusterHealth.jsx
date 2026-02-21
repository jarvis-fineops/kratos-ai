import { useState, useEffect } from "react"

export default function ClusterHealth() {
  const [health, setHealth] = useState({
    nodes: { total: 3, ready: 3 },
    pods: { running: 45, pending: 3, failed: 2, total: 50 },
    namespaces: ["default", "kube-system", "production", "staging"]
  })

  const nodeHealth = (health.nodes.ready / health.nodes.total) * 100
  const podHealth = (health.pods.running / health.pods.total) * 100

  return (
    <div className="bg-gray-800 rounded-xl border border-gray-700 p-6">
      <h2 className="text-lg font-semibold mb-4 flex items-center">
        <span className="mr-2">🏥</span> Cluster Health
      </h2>

      <div className="grid grid-cols-2 gap-6">
        {/* Nodes */}
        <div>
          <div className="flex justify-between mb-2">
            <span className="text-gray-400">Nodes</span>
            <span className="font-medium">{health.nodes.ready}/{health.nodes.total} Ready</span>
          </div>
          <div className="h-3 bg-gray-700 rounded-full overflow-hidden">
            <div 
              className="h-full bg-green-500 rounded-full transition-all"
              style={{ width: `${nodeHealth}%` }}
            />
          </div>
        </div>

        {/* Pods */}
        <div>
          <div className="flex justify-between mb-2">
            <span className="text-gray-400">Pods</span>
            <span className="font-medium">{health.pods.running}/{health.pods.total} Running</span>
          </div>
          <div className="h-3 bg-gray-700 rounded-full overflow-hidden flex">
            <div 
              className="h-full bg-green-500 transition-all"
              style={{ width: `${(health.pods.running / health.pods.total) * 100}%` }}
            />
            <div 
              className="h-full bg-yellow-500 transition-all"
              style={{ width: `${(health.pods.pending / health.pods.total) * 100}%` }}
            />
            <div 
              className="h-full bg-red-500 transition-all"
              style={{ width: `${(health.pods.failed / health.pods.total) * 100}%` }}
            />
          </div>
        </div>
      </div>

      {/* Pod Status Breakdown */}
      <div className="mt-4 flex space-x-4 text-sm">
        <span className="flex items-center">
          <span className="w-3 h-3 bg-green-500 rounded-full mr-2"></span>
          Running: {health.pods.running}
        </span>
        <span className="flex items-center">
          <span className="w-3 h-3 bg-yellow-500 rounded-full mr-2"></span>
          Pending: {health.pods.pending}
        </span>
        <span className="flex items-center">
          <span className="w-3 h-3 bg-red-500 rounded-full mr-2"></span>
          Failed: {health.pods.failed}
        </span>
      </div>

      {/* Namespaces */}
      <div className="mt-4 pt-4 border-t border-gray-700">
        <p className="text-sm text-gray-400 mb-2">Active Namespaces</p>
        <div className="flex flex-wrap gap-2">
          {health.namespaces.map(ns => (
            <span key={ns} className="px-2 py-1 bg-gray-700 rounded text-sm">
              {ns}
            </span>
          ))}
        </div>
      </div>
    </div>
  )
}
