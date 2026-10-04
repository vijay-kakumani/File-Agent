import React from 'react';
import { Plus, MessageSquare, Settings, Sparkles, PanelLeftClose } from 'lucide-react';
import CurrentDocument from './CurrentDocument';

export default function Sidebar({
  currentDocument,
  onNewSearch,
  onOpenSettings,
  isOpen,
  onToggleOpen
}) {
  return (
    <aside
      className={`h-screen w-64 bg-[#f0f0f0] border-r border-neutral-300/60 flex flex-col flex-shrink-0 transition-all duration-300 z-30 ${
        isOpen ? 'translate-x-0' : '-translate-x-full md:translate-x-0 md:w-64'
      }`}
    >
      {/* Brand Header */}
      <div className="p-4 sm:p-5 border-b border-neutral-300/50 flex items-center justify-between">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-xl bg-neutral-900 text-white flex items-center justify-center neu-button">
            <Sparkles className="w-4 h-4 stroke-[2]" />
          </div>
          <div>
            <h1 className="text-xs font-bold text-neutral-900 tracking-tight leading-tight uppercase">
              Local AI
            </h1>
            <p className="text-[11px] font-medium text-neutral-500 tracking-normal leading-tight">
              Document Agent
            </p>
          </div>
        </div>

        {/* Mobile / Narrow Screen Collapse button */}
        {onToggleOpen && (
          <button
            type="button"
            onClick={onToggleOpen}
            className="md:hidden p-1 text-neutral-400 hover:text-neutral-700 rounded-lg"
            aria-label="Close sidebar"
          >
            <PanelLeftClose className="w-4 h-4" />
          </button>
        )}
      </div>

      {/* Main Action: New Search */}
      <div className="p-3.5 pb-2">
        <button
          type="button"
          onClick={onNewSearch}
          className="w-full flex items-center justify-center gap-2 py-2 px-3 rounded-xl neu-button text-xs font-semibold text-neutral-800 hover:text-neutral-950 active:scale-95 transition-all border border-neutral-300/40"
        >
          <Plus className="w-3.5 h-3.5 stroke-[2.5]" />
          <span>New Search</span>
        </button>
      </div>

      {/* Navigation Sections */}
      <div className="flex-1 overflow-y-auto px-3.5 py-2 space-y-5">
        {/* Navigation Category: Ask Documents */}
        <div>
          <div className="px-1 mb-1.5 text-[10px] font-bold text-neutral-400 uppercase tracking-wider">
            Ask Documents
          </div>
          <div className="flex items-center gap-2 px-3 py-2 rounded-xl bg-neutral-200/80 text-xs font-medium text-neutral-900 neu-inset">
            <MessageSquare className="w-3.5 h-3.5 text-neutral-700" />
            <span>Active Session</span>
          </div>
        </div>

        {/* Current Document Section */}
        <div>
          <div className="px-1 mb-1.5 text-[10px] font-bold text-neutral-400 uppercase tracking-wider">
            Current Document
          </div>
          <CurrentDocument currentDocument={currentDocument} />
        </div>
      </div>

      {/* Bottom Footer: Settings */}
      <div className="p-3 border-t border-neutral-300/50 mt-auto">
        <button
          type="button"
          onClick={onOpenSettings}
          className="w-full flex items-center gap-2 px-3 py-2 rounded-xl text-xs font-medium text-neutral-600 hover:text-neutral-900 hover:bg-neutral-200/70 transition-colors"
        >
          <Settings className="w-4 h-4 text-neutral-500" />
          <span>Settings</span>
        </button>
      </div>
    </aside>
  );
}
