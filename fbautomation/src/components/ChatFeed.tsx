'use client';

import React, { useEffect, useRef, useState } from 'react';
import { CheckCircle2, Clock3, Image as ImageIcon, Send, XCircle } from 'lucide-react';
import { ContentItem } from '../lib/types';
import { PostPreviewCard } from './PostPreviewCard';

interface Props { initialItems?: ContentItem[]; }
const labels: Record<string, string> = { approved: 'Topic approved', generating_content: 'Generating caption', generating_image: 'Generating image', preview_pending: 'Preview ready', preview_approved: 'Preview approved', scheduled: 'Post scheduled', publishing: 'Publishing post', published: 'Post published', failed: 'Pipeline failed', rejected: 'Preview rejected' };
function icon(status: string) { return status === 'failed' || status === 'rejected' ? <XCircle size={18}/> : status === 'generating_image' ? <ImageIcon size={18}/> : status === 'generating_content' || status === 'publishing' ? <Clock3 size={18}/> : status === 'scheduled' ? <Send size={18}/> : <CheckCircle2 size={18}/>; }

export function ChatFeed({ initialItems = [] }: Props) {
  const [events, setEvents] = useState<ContentItem[]>(initialItems); const endRef = useRef<HTMLDivElement>(null);
  useEffect(() => { const sse = new EventSource('/api/pipeline/stream'); sse.onmessage = e => { try { const item = JSON.parse(e.data) as ContentItem; setEvents(prev => [...prev, item]); } catch {} }; return () => sse.close(); }, []);
  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [events]);
  const post = (url: string, id: string, body?: object) => fetch(url.replace(':id', id), { method: body ? 'PATCH' : 'POST', headers: body ? { 'Content-Type': 'application/json' } : undefined, body: body ? JSON.stringify(body) : undefined });
  return <div className="flex-1 overflow-y-auto p-5 space-y-4">
    {events.length === 0 ? <div className="mt-24 flex flex-col items-center gap-3 text-center text-gray-500"><ImageIcon size={32}/><p className="text-sm">No active pipeline items. Select topics below to begin.</p></div> : events.map((item, index) => <div key={`${item.id}-${index}`} className="mx-auto max-w-4xl animate-in fade-in slide-in-from-bottom-2 duration-300">
      {item.status === 'preview_pending' || item.status === 'preview_approved' || item.status === 'rejected' ? <PostPreviewCard item={item} onApprove={id => post('/api/preview/:id/approve', id)} onReject={id => post('/api/preview/:id/reject', id)} onRegenerate={id => post('/api/preview/:id/regenerate-image', id)} onUpdateCaption={(id, caption) => post('/api/preview/:id/caption', id, { caption })}/> : <div className={`flex gap-3 rounded-xl border bg-[#151515] p-4 ${item.status === 'failed' ? 'border-red-900/70 text-red-400' : item.status === 'scheduled' ? 'border-blue-900/70 text-blue-400' : 'border-[#333] text-green-400'}`}><div className={item.status.startsWith('generating') || item.status === 'publishing' ? 'animate-pulse' : ''}>{icon(item.status)}</div><div><p className="text-sm font-medium text-gray-100">{labels[item.status] || item.status.replace(/_/g, ' ')}</p><p className="mt-1 text-xs text-gray-500">{item.headline || item.topic}</p>{item.error_message && <p className="mt-2 text-xs text-red-300">{item.error_message}</p>}</div></div>}
    </div>)}<div ref={endRef}/></div>;
}
