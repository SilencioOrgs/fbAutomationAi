import { TelegramStatusIndicator } from '@/src/components/TelegramStatusIndicator';

export default function SettingsPage() {
  const telegramConnected = !!process.env.TELEGRAM_BOT_TOKEN;

  return (
    <main className="flex flex-col h-screen bg-black">
      <header className="h-14 border-b border-[#333] flex items-center justify-between px-6 bg-[#0a0a0a]">
        <div className="flex items-center gap-4">
          <h1 className="text-lg font-semibold tracking-tight text-white">Pipeline Settings</h1>
          <nav className="flex items-center gap-4 ml-6 text-sm">
            <a href="/" className="text-gray-500 hover:text-gray-300">Pipeline</a>
            <a href="/settings" className="text-white">Settings</a>
            <a href="/logs" className="text-gray-500 hover:text-gray-300">Logs</a>
          </nav>
        </div>
        <TelegramStatusIndicator connected={telegramConnected} />
      </header>

      <div className="flex-1 overflow-y-auto p-6 max-w-4xl mx-auto w-full space-y-6">
        <h2 className="text-xl font-medium text-gray-200">Configuration</h2>
        <p className="text-sm text-gray-400">Settings are currently managed via <code className="bg-[#222] px-1 py-0.5 rounded text-gray-300">config/prompt-templates.json</code>.</p>
      </div>
    </main>
  );
}
