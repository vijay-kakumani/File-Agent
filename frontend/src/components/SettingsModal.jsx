import React from 'react';
import { X, ShieldCheck, Database, HardDrive, Cpu, Network } from 'lucide-react';

export default function SettingsModal({ isOpen, onClose }) {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-neutral-900/30 backdrop-blur-sm animate-fadeIn">
      <div className="w-full max-w-md rounded-2xl neu-raised border border-neutral-200/90 p-5 sm:p-6 text-neutral-900 shadow-xl">
        {/* Header */}
        <div className="flex items-center justify-between pb-3 border-b border-neutral-200">
          <div>
            <h3 className="text-sm font-semibold text-neutral-900 tracking-tight">
              Settings & System Status
            </h3>
            <p className="text-[11px] text-neutral-500">
              Local AI Document Agent v1.0.0
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="p-1.5 rounded-lg text-neutral-400 hover:text-neutral-800 hover:bg-neutral-200/60 transition-colors"
            aria-label="Close settings"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* System Diagnostics Info */}
        <div className="mt-4 space-y-3 text-xs">
          <div className="flex items-start gap-3 p-2.5 rounded-xl bg-neutral-100 border border-neutral-200/60">
            <ShieldCheck className="w-4 h-4 text-neutral-700 flex-shrink-0 mt-0.5" />
            <div>
              <div className="font-medium text-neutral-900">Privacy & Isolation</div>
              <div className="text-[11px] text-neutral-500">100% offline-first. Zero telemetry. Zero remote leaks.</div>
            </div>
          </div>

          <div className="flex items-start gap-3 p-2.5 rounded-xl bg-neutral-100 border border-neutral-200/60">
            <Database className="w-4 h-4 text-neutral-700 flex-shrink-0 mt-0.5" />
            <div>
              <div className="font-medium text-neutral-900">Retrieval Engine</div>
              <div className="text-[11px] text-neutral-500">Hybrid: SQLite FTS5 + RapidFuzz + ChromaDB</div>
            </div>
          </div>

          <div className="flex items-start gap-3 p-2.5 rounded-xl bg-neutral-100 border border-neutral-200/60">
            <Cpu className="w-4 h-4 text-neutral-700 flex-shrink-0 mt-0.5" />
            <div>
              <div className="font-medium text-neutral-900">Local Embeddings & LLM</div>
              <div className="text-[11px] text-neutral-500">all-MiniLM-L6-v2 (Bundled) · Ollama qwen2.5:1.5b</div>
            </div>
          </div>

          <div className="flex items-start gap-3 p-2.5 rounded-xl bg-neutral-100 border border-neutral-200/60">
            <Network className="w-4 h-4 text-neutral-700 flex-shrink-0 mt-0.5" />
            <div>
              <div className="font-medium text-neutral-900">Localhost Connection</div>
              <div className="text-[11px] text-neutral-500">API Port: 127.0.0.1:8000</div>
            </div>
          </div>

          <div className="flex items-start gap-3 p-2.5 rounded-xl bg-neutral-100 border border-neutral-200/60">
            <HardDrive className="w-4 h-4 text-neutral-700 flex-shrink-0 mt-0.5" />
            <div>
              <div className="font-medium text-neutral-900">User Data Location</div>
              <div className="text-[11px] text-neutral-500 truncate" title="%LOCALAPPDATA%\LocalAIDocumentAgent\data">
                %LOCALAPPDATA%\LocalAIDocumentAgent\data
              </div>
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="mt-5 pt-3 border-t border-neutral-200 flex justify-end">
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-1.5 rounded-xl neu-button text-xs font-semibold text-neutral-800 hover:text-neutral-950 transition-all active:scale-95"
          >
            Done
          </button>
        </div>
      </div>
    </div>
  );
}
