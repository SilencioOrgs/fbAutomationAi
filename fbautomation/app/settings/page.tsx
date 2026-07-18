import { TelegramStatusIndicator } from '@/src/components/TelegramStatusIndicator';
import { SettingsPanel } from '@/src/components/SettingsPanel';
import { getConfig } from '@/src/lib/config';

export default function SettingsPage() {
  const config = getConfig();
  return <main className="flex min-h-screen flex-col bg-black"><header className="h-14 border-b border-[#333] flex items-center justify-between px-6 bg-[#0a0a0a]"><div className="flex items-center gap-4"><h1 className="text-lg font-semibold tracking-tight text-white">{config.branding.page_name} — Content Pipeline Settings</h1><nav className="flex items-center gap-4 ml-6 text-sm"><a href="/" className="text-gray-500 hover:text-gray-300">Pipeline</a><a href="/settings" className="text-white">Settings</a><a href="/logs" className="text-gray-500 hover:text-gray-300">Logs</a></nav></div><TelegramStatusIndicator connected={!!process.env.TELEGRAM_BOT_TOKEN}/></header><div className="flex-1 overflow-y-auto p-6 max-w-4xl mx-auto w-full"><SettingsPanel/></div></main>;
}
