'use client';

import React from 'react';
import { MessageCircle } from 'lucide-react';

interface Props {
  connected: boolean;
}

export function TelegramStatusIndicator({ connected }: Props) {
  return (
    <div className="flex items-center gap-2 text-sm font-medium">
      <MessageCircle size={16} className={connected ? 'text-green-500' : 'text-gray-500'} />
      <span className={connected ? 'text-green-400' : 'text-gray-400'}>
        Telegram: {connected ? 'Connected' : 'Not Connected'}
      </span>
    </div>
  );
}
