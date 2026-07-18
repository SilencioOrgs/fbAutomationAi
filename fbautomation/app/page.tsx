import { TelegramStatusIndicator } from '@/src/components/TelegramStatusIndicator';
import { ChatFeed } from '@/src/components/ChatFeed';
import { TopicSelectionPanel } from '@/src/components/TopicSelectionPanel';
import { ContentItemModel } from '@/src/models/ContentItemModel';

export const dynamic = 'force-dynamic';

export default async function Home() {
  // Check telegram connection status
  const telegramConnected = !!process.env.TELEGRAM_BOT_TOKEN;

  // We could fetch active items from DB to seed initial state
  // Let's get items that are not 'published', 'failed' etc. (or just fetch last 20)
  const dbItems = ContentItemModel.getByStatus('pending_approval').concat(
    ContentItemModel.getByStatus('approved'),
    ContentItemModel.getByStatus('generating_content'),
    ContentItemModel.getByStatus('generating_image'),
    ContentItemModel.getByStatus('preview_pending'),
    ContentItemModel.getByStatus('preview_approved'),
    ContentItemModel.getByStatus('scheduled'),
    ContentItemModel.getByStatus('publishing')
  ).slice(0, 50);

  return (
    <main className="flex flex-col h-screen bg-black">
      {/* Header Bar */}
      <header className="h-14 border-b border-[#333] flex items-center justify-between px-6 bg-[#0a0a0a]">
        <div className="flex items-center gap-4">
          <h1 className="text-lg font-semibold tracking-tight text-white">Pipeline Pipeline</h1>
          <nav className="flex items-center gap-4 ml-6 text-sm">
            <a href="/" className="text-white">Pipeline</a>
            <a href="/settings" className="text-gray-500 hover:text-gray-300">Settings</a>
            <a href="/logs" className="text-gray-500 hover:text-gray-300">Logs</a>
          </nav>
        </div>
        <TelegramStatusIndicator connected={telegramConnected} />
      </header>

      {/* Main Feed Area */}
      <ChatFeed initialItems={dbItems} />

      {/* Footer Topic Selection (Replaces chat input) */}
      <div className="mt-auto">
        <TopicSelectionPanel />
      </div>
    </main>
  );
}
