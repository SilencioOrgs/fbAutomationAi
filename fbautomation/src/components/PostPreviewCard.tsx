'use client';

import React, { useState } from 'react';
import { ContentItem } from '../lib/types';
import { Check, X, RefreshCw, Edit2, Share2, Camera } from 'lucide-react';
import { StatusBadge } from './StatusBadge';

interface Props {
  item: ContentItem;
  onApprove: (id: string) => void;
  onReject: (id: string) => void;
  onRegenerate: (id: string) => void;
  onUpdateCaption: (id: string, newCaption: string) => void;
}

export function PostPreviewCard({ item, onApprove, onReject, onRegenerate, onUpdateCaption }: Props) {
  const [isEditing, setIsEditing] = useState(false);
  const [caption, setCaption] = useState(item.generated_description || '');
  const [platform, setPlatform] = useState<'facebook' | 'instagram'>('facebook');

  const imageUrl = item.ai33pro_task_id ? `/api/images/${item.ai33pro_task_id}.png` : null;

  const handleSaveCaption = () => {
    onUpdateCaption(item.id, caption);
    setIsEditing(false);
  };

  return (
    <div className="bg-[#1a1a1a] rounded-xl border border-[#444] overflow-hidden flex flex-col sm:flex-row max-w-5xl mx-auto w-full mb-6 shadow-2xl">
      {/* Image Section */}
      <div className="w-full sm:w-1/2 bg-black flex items-center justify-center p-4 border-b sm:border-b-0 sm:border-r border-[#333]">
        {imageUrl ? (
          <img src={imageUrl} alt="Generated Preview" className="max-h-[400px] object-contain rounded" />
        ) : (
          <div className="text-gray-500 flex flex-col items-center justify-center h-48 sm:h-full">
            <RefreshCw className="animate-spin mb-2" />
            <span className="text-sm">Image not available</span>
          </div>
        )}
      </div>

      {/* Content Section */}
      <div className="w-full sm:w-1/2 p-6 flex flex-col">
        <div className="flex justify-between items-start mb-4">
          <div><div className="mb-2 flex gap-1"><button onClick={() => setPlatform('facebook')} className={`rounded px-2 py-1 text-xs ${platform === 'facebook' ? 'bg-white text-black' : 'text-gray-400'}`}><Share2 size={14} className="inline mr-1"/>Facebook</button><button onClick={() => setPlatform('instagram')} className={`rounded px-2 py-1 text-xs ${platform === 'instagram' ? 'bg-white text-black' : 'text-gray-400'}`}><Camera size={14} className="inline mr-1"/>Instagram</button></div><h3 className="text-lg font-semibold text-gray-100">{item.generated_title || item.headline}</h3></div>
          <StatusBadge status={item.status} />
        </div>

        <div className="flex-1 bg-black/50 p-4 rounded-lg border border-[#333] mb-6 overflow-y-auto max-h-[300px]">
          {isEditing ? (
            <textarea
              className="w-full h-full min-h-[150px] bg-transparent text-gray-300 resize-none outline-none focus:ring-1 focus:ring-[#555] rounded p-2"
              value={caption}
              onChange={(e) => setCaption(e.target.value)}
            />
          ) : (
            <div className="text-sm text-gray-300 whitespace-pre-wrap">
              {item.generated_description}
              <br /><br />
              <span className="text-blue-400">{item.generated_hashtags}</span>
            </div>
          )}
        </div>

        {/* Actions */}
        <div className="flex flex-wrap gap-2 justify-end mt-auto">
          {isEditing ? (
            <button onClick={handleSaveCaption} className="flex items-center gap-1 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-md text-sm font-medium transition-colors">
              Save Caption
            </button>
          ) : (
            <button onClick={() => setIsEditing(true)} className="flex items-center gap-1 px-4 py-2 bg-gray-700 hover:bg-gray-600 text-white rounded-md text-sm font-medium transition-colors">
              <Edit2 size={16} /> Edit Caption
            </button>
          )}

          <button onClick={() => onRegenerate(item.id)} className="flex items-center gap-1 px-4 py-2 bg-gray-700 hover:bg-gray-600 text-white rounded-md text-sm font-medium transition-colors">
            <RefreshCw size={16} /> Regenerate Image
          </button>
          <button onClick={() => onReject(item.id)} className="flex items-center gap-1 px-4 py-2 bg-red-900/50 hover:bg-red-800 text-red-300 rounded-md text-sm font-medium transition-colors border border-red-800">
            <X size={16} /> Reject
          </button>
          <button onClick={() => onApprove(item.id)} className="flex items-center gap-1 px-4 py-2 bg-green-700 hover:bg-green-600 text-white rounded-md text-sm font-medium transition-colors">
            <Check size={16} /> Approve
          </button>
        </div>
      </div>
    </div>
  );
}
