'use client';

import React, { useState, useEffect } from 'react';
import { TopicSourceRow } from '../lib/types';
import { CheckSquare, Square, Upload } from 'lucide-react';

export function TopicSelectionPanel() {
  const [topics, setTopics] = useState<TopicSourceRow[]>([]);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [loading, setLoading] = useState(true);
  const [exhausted, setExhausted] = useState(false);

  useEffect(() => {
    fetchTopics();
  }, []);

  const fetchTopics = async () => {
    try {
      const res = await fetch('/api/topics/available?page=1');
      const data = await res.json();
      if (data.topics && data.topics.length > 0) {
        setTopics(data.topics);
      } else {
        setExhausted(true);
      }
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const toggleSelect = (id: string) => {
    const next = new Set(selectedIds);
    if (next.has(id)) next.delete(id);
    else next.add(id);
    setSelectedIds(next);
  };

  const handleGenerate = async () => {
    if (selectedIds.size === 0) return;
    const ids = Array.from(selectedIds);
    try {
      await fetch('/api/topics/select', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ids })
      });
      setTopics(topics.filter(t => !selectedIds.has(t.id)));
      setSelectedIds(new Set());
    } catch (err) {
      console.error(err);
    }
  };

  if (loading) {
    return <div className="p-4 text-center text-gray-400 text-sm">Loading available topics...</div>;
  }

  if (exhausted || topics.length === 0) {
    return (
      <div className="p-6 border-t border-[#333] bg-[#0a0a0a] flex flex-col items-center justify-center gap-4">
        <p className="text-gray-400 text-sm">No more unconsumed topics available.</p>
        <button className="flex items-center gap-2 px-4 py-2 bg-gray-800 hover:bg-gray-700 text-white rounded-md text-sm font-medium transition-colors">
          <Upload size={16} /> Upload New Topic File
        </button>
      </div>
    );
  }

  return (
    <div className="border-t border-[#333] bg-[#0a0a0a] flex flex-col max-h-[300px]">
      <div className="p-3 border-b border-[#222] flex justify-between items-center bg-[#111]">
        <h4 className="text-sm font-semibold text-gray-200">Available Topics</h4>
        <span className="text-xs text-gray-500">{selectedIds.size} selected</span>
      </div>
      
      <div className="overflow-y-auto p-2 flex-1 space-y-1">
        {topics.map(topic => (
          <div 
            key={topic.id}
            onClick={() => toggleSelect(topic.id)}
            className={`flex items-center gap-3 p-2 rounded cursor-pointer transition-colors ${selectedIds.has(topic.id) ? 'bg-[#222]' : 'hover:bg-[#1a1a1a]'}`}
          >
            <div className="text-blue-500">
              {selectedIds.has(topic.id) ? <CheckSquare size={18} /> : <Square size={18} className="text-gray-500" />}
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-sm text-gray-200 truncate">{topic.topic}</p>
              <p className="text-xs text-gray-500 truncate">{topic.category} &bull; {topic.subject}</p>
            </div>
          </div>
        ))}
      </div>

      <div className="p-3 border-t border-[#222] flex justify-end bg-[#111]">
        <button 
          onClick={handleGenerate}
          disabled={selectedIds.size === 0}
          className="px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-800 disabled:text-gray-500 text-white rounded-md text-sm font-medium transition-colors"
        >
          Generate Selected
        </button>
      </div>
    </div>
  );
}
