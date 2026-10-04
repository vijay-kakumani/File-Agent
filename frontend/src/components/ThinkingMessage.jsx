import React from 'react';
import { ThinkingOrb } from 'thinking-orbs';

export default function ThinkingMessage({ orbState, statusText }) {
  return (
    <div className="flex justify-start w-full animate-fadeIn">
      <div className="flex items-center gap-3 px-4 py-3 rounded-2xl neu-raised-sm border border-neutral-200/90 text-neutral-800 shadow-sm">
        <div className="w-6 h-6 flex items-center justify-center">
          <ThinkingOrb state={orbState || 'working'} size={24} theme="light" />
        </div>
        <span className="text-xs font-semibold text-neutral-600 animate-pulse tracking-wide">
          {statusText || 'Thinking...'}
        </span>
      </div>
    </div>
  );
}
