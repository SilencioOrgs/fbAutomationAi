'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { FileText, Home, Settings } from 'lucide-react';
import { TelegramStatusIndicator } from './TelegramStatusIndicator';

export function Sidebar({ pageName, telegramConnected }: { pageName: string; telegramConnected: boolean }) {
  const pathname = usePathname();
  const links = [{ href: '/', label: 'Home', icon: Home }, { href: '/settings', label: 'Settings', icon: Settings }, { href: '/logs', label: 'Logs', icon: FileText }];
  return <aside className="flex h-screen w-64 shrink-0 flex-col border-r border-[#333] bg-[#0a0a0a] p-3"><div className="px-3 py-5 text-lg font-semibold text-white">{pageName}</div><nav className="space-y-1">{links.map(({ href, label, icon: Icon }) => { const active = href === '/' ? pathname === '/' : pathname.startsWith(href); return <Link key={href} href={href} className={`flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm transition-colors ${active ? 'bg-[#222] text-white' : 'text-gray-500 hover:bg-[#151515] hover:text-gray-200'}`}><Icon size={18}/>{label}</Link>; })}</nav><div className="mt-auto border-t border-[#333] px-3 py-4"><TelegramStatusIndicator connected={telegramConnected}/></div></aside>;
}
