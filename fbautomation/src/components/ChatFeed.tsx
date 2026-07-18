'use client';

import React, { useEffect, useState, useRef } from 'react';
import { ContentItem } from '../lib/types';
import { PostPreviewCard } from './PostPreviewCard';

interface Props {
  initialItems?: ContentItem[];
}

export function ChatFeed({ initialItems = [] }: Props) {
  const [items, setItems] = useState<ContentItem[]>(initialItems);
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const sse = new EventSource('/api/pipeline/stream');
    
    sse.onmessage = (e) => {
      try {
        const updatedItem = JSON.parse(e.data) as ContentItem;
        setItems(prev => {
          const idx = prev.findIndex(i => i.id === updatedItem.id);
          if (idx >= 0) {
            const newArr = [...prev];
            newArr[idx] = updatedItem;
            return newArr;
          }
          return [...prev, updatedItem];
        });
      } catch (err) {}
    };

    return () => sse.close();
  }, []);

  useEffect(() => {
    // Scroll to bottom on new items
    endRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [items]);

  const handleApprove = async (id: string) => {
    await fetch(`/api/preview/${id}/approve`, { method: 'POST' });
  };
  
  const handleReject = async (id: string) => {
    await fetch(`/api/preview/${id}/reject`, { method: 'POST' });
  };
  
  const handleRegenerate = async (id: string) => {
    await fetch(`/api/preview/${id}/regenerate-image`, { method: 'POST' });
  };
  
  const handleUpdateCaption = async (id: string, caption: string) => {
    await fetch(`/api/preview/${id}/caption`, { 
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ caption })
    });
  };

  return (
    <div className="flex-1 overflow-y-auto p-4 space-y-6">
      {items.length === 0 ? (
        <div className="text-center text-gray-500 mt-20">
          No active pipeline items. Select topics below to begin.
        </div>
      ) : (
        items.map(item => (
          <div key={item.id} className="animate-in fade-in slide-in-from-bottom-4 duration-300">
            {item.status === 'preview_pending' || item.status === 'preview_approved' || item.status === 'rejected' ? (
              <PostPreviewCard 
                item={item} 
                onApprove={handleApprove}
                onReject={handleReject}
                onRegenerate={handleRegenerate}
                onUpdateCaption={handleUpdateCaption}
              />
            ) : (
              <div className="max-w-4xl mx-auto flex items-start gap-4 p-4 rounded-xl bg-[#111] border border-[#222]">
                <div className="flex-1">
                  <h4 className="text-sm font-medium text-gray-200 mb-1">{item.headline || item.topic}</h4>
                  <p className="text-xs text-gray-500">Status: {item.status.replace(/_/g, ' ')}</p>
                  {item.error_message && (
                    <p className="text-xs text-red-400 mt-2 bg-red-900/20 p-2 rounded border border-red-900/50">
                      {item.error_message}
                    </p>
                  )}
                </div>
              </div>
            )}
          </div>
        ))
      )}
      <div ref={endRef} />
    </div>
  );
}
