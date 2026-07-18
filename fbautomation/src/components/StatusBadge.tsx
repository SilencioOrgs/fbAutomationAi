import React from 'react';
import { ContentItem } from '../lib/types';

interface StatusBadgeProps {
  status: string;
}

export function StatusBadge({ status }: StatusBadgeProps) {
  const getStyle = () => {
    switch (status) {
      case 'approved':
      case 'published':
      case 'preview_approved':
        return 'bg-green-900 text-green-300 border-green-700';
      case 'failed':
      case 'rejected':
        return 'bg-red-900 text-red-300 border-red-700';
      case 'scheduled':
        return 'bg-blue-900 text-blue-300 border-blue-700';
      default:
        // pending_approval, generating_content, generating_image, preview_pending, publishing
        return 'bg-gray-800 text-gray-300 border-gray-600';
    }
  };

  const getLabel = () => {
    return status.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
  };

  return (
    <span className={`px-2 py-1 text-xs font-medium rounded-full border ${getStyle()}`}>
      {getLabel()}
    </span>
  );
}
