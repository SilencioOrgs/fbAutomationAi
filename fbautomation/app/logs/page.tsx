import { TelegramStatusIndicator } from '@/src/components/TelegramStatusIndicator';
import { UsageLogModel } from '@/src/models/UsageLogModel';
import { getConfig } from '@/src/lib/config';

export const dynamic = 'force-dynamic';

export default function LogsPage() {
  const config = getConfig();
  const telegramConnected = !!process.env.TELEGRAM_BOT_TOKEN;
  const recentLogs = UsageLogModel.getRecentLogs(100);

  return (
    <main className="flex flex-col h-screen bg-black">
      <header className="h-14 border-b border-[#333] flex items-center justify-between px-6 bg-[#0a0a0a]">
        <div className="flex items-center gap-4">
          <h1 className="text-lg font-semibold tracking-tight text-white">{config.branding.page_name} — Content Pipeline Logs</h1>
          <nav className="flex items-center gap-4 ml-6 text-sm">
            <a href="/" className="text-gray-500 hover:text-gray-300">Pipeline</a>
            <a href="/settings" className="text-gray-500 hover:text-gray-300">Settings</a>
            <a href="/logs" className="text-white">Logs</a>
          </nav>
        </div>
        <TelegramStatusIndicator connected={telegramConnected} />
      </header>

      <div className="flex-1 overflow-y-auto p-6 max-w-4xl mx-auto w-full">
        <h2 className="text-xl font-medium text-gray-200 mb-6">Usage Logs</h2>
        
        {recentLogs.length === 0 ? (
          <p className="text-gray-500 text-sm">No logs recorded yet.</p>
        ) : (
          <div className="overflow-x-auto rounded-lg border border-[#333]">
            <table className="w-full text-sm text-left text-gray-300">
              <thead className="text-xs text-gray-400 uppercase bg-[#111] border-b border-[#333]">
                <tr>
                  <th className="px-6 py-3">Timestamp</th>
                  <th className="px-6 py-3">Provider</th>
                  <th className="px-6 py-3">Endpoint</th>
                  <th className="px-6 py-3">Status</th>
                  <th className="px-6 py-3">Cost</th>
                  <th className="px-6 py-3">Error</th>
                </tr>
              </thead>
              <tbody>
                {recentLogs.map((log) => (
                  <tr key={log.id} className="bg-[#0a0a0a] border-b border-[#222] hover:bg-[#111]">
                    <td className="px-6 py-3 whitespace-nowrap">{new Date(log.timestamp).toLocaleString()}</td>
                    <td className="px-6 py-3">{log.provider}</td>
                    <td className="px-6 py-3">{log.endpoint}</td>
                    <td className="px-6 py-3">
                      {log.success ? (
                        <span className="text-green-400">Success</span>
                      ) : (
                        <span className="text-red-400">Failed</span>
                      )}
                    </td>
                    <td className="px-6 py-3">{log.credit_cost !== null ? log.credit_cost : '-'}</td>
                    <td className="px-6 py-3 text-red-400">{log.error_msg || '-'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </main>
  );
}
