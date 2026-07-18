import { UsageLogModel } from '@/src/models/UsageLogModel';

export const dynamic = 'force-dynamic';

export default async function LogsPage() {
  const recentLogs = await UsageLogModel.getRecentLogs(100);
  return <div className="mx-auto w-full max-w-4xl p-6"><h1 className="mb-6 text-xl font-semibold text-white">Usage Logs</h1>{recentLogs.length === 0 ? <p className="text-sm text-gray-500">No logs recorded yet.</p> : <div className="overflow-x-auto rounded-lg border border-[#333]"><table className="w-full text-left text-sm text-gray-300"><thead className="border-b border-[#333] bg-[#111] text-xs uppercase text-gray-400"><tr><th className="px-6 py-3">Timestamp</th><th className="px-6 py-3">Provider</th><th className="px-6 py-3">Endpoint</th><th className="px-6 py-3">Status</th><th className="px-6 py-3">Cost</th><th className="px-6 py-3">Error</th></tr></thead><tbody>{recentLogs.map((log: any) => <tr key={log.id} className="border-b border-[#222] bg-[#0a0a0a]"><td className="whitespace-nowrap px-6 py-3">{new Date(log.timestamp).toLocaleString()}</td><td className="px-6 py-3">{log.provider}</td><td className="px-6 py-3">{log.endpoint}</td><td className={`px-6 py-3 ${log.success ? 'text-green-400' : 'text-red-400'}`}>{log.success ? 'Success' : 'Failed'}</td><td className="px-6 py-3">{log.credit_cost ?? '-'}</td><td className="px-6 py-3 text-red-400">{log.error_msg || '-'}</td></tr>)}</tbody></table></div>}</div>;
}
