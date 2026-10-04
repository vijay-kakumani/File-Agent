import React, { useRef, useEffect } from 'react';
import { ThinkingOrb } from 'thinking-orbs';
import { PanelLeft, Sparkles, Clock } from 'lucide-react';
import ChatMessage from './ChatMessage';
import ThinkingMessage from './ThinkingMessage';
import Composer from './Composer';

export default function MainWorkspace({
  messages,
  isThinking,
  thinkingStatus,
  orbState,
  onSendMessage,
  onSelectOption,
  onOpenDocument,
  onShowLocation,
  isBackendReady,
  isProcessing,
  onToggleSidebar,
  sidebarOpen,
  composerFocusTrigger
}) {
  const scrollRef = useRef(null);
  const isNearBottomRef = useRef(true);

  const suggestions = [
    'Find Nikhil CS',
    'Where did I save Nikhil CS?',
    'Summarize it',
    'What issues were identified?'
  ];

  // Track if user has scrolled away from the bottom
  const handleScroll = () => {
    if (!scrollRef.current) return;
    const { scrollTop, scrollHeight, clientHeight } = scrollRef.current;
    const distanceToBottom = scrollHeight - scrollTop - clientHeight;
    isNearBottomRef.current = distanceToBottom < 100;
  };

  // Auto-scroll to newest response if near bottom
  useEffect(() => {
    if (scrollRef.current && isNearBottomRef.current) {
      scrollRef.current.scrollTo({
        top: scrollRef.current.scrollHeight,
        behavior: 'smooth'
      });
    }
  }, [messages, isThinking]);

  const hasMessages = messages.length > 0 || isThinking;

  return (
    <main className="flex-1 flex flex-col h-screen overflow-hidden relative bg-[#F5F5F5] text-neutral-900">
      {/* Top Bar */}
      <header className="h-12 border-b border-neutral-300/40 px-4 sm:px-6 flex items-center justify-between flex-shrink-0 bg-[#F5F5F5]/80 backdrop-blur-sm z-10">
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={onToggleSidebar}
            className="p-1.5 rounded-lg text-neutral-500 hover:text-neutral-900 hover:bg-neutral-200/60 transition-colors"
            aria-label={sidebarOpen ? 'Collapse sidebar' : 'Expand sidebar'}
            title={sidebarOpen ? 'Collapse sidebar' : 'Expand sidebar'}
          >
            <PanelLeft className="w-4 h-4" />
          </button>
          <span className="text-xs font-semibold text-neutral-700 tracking-tight">
            Workspace
          </span>
        </div>

        {/* Backend Ready / Activity Indicator */}
        <div className="flex items-center gap-2">
          {isBackendReady ? (
            <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-neutral-200/70 border border-neutral-300/40 text-[11px] font-medium text-neutral-600">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-500"></span>
              <span>Ready</span>
            </div>
          ) : (
            <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-neutral-200/70 border border-neutral-300/40 text-[11px] font-medium text-neutral-500 animate-pulse">
              <Clock className="w-3 h-3 text-neutral-400" />
              <span>Starting backend...</span>
            </div>
          )}
        </div>
      </header>

      {/* Scrollable Conversation Area */}
      <div
        ref={scrollRef}
        onScroll={handleScroll}
        className="flex-1 overflow-y-auto px-4 sm:px-8 py-6"
      >
        <div className="max-w-2xl mx-auto w-full flex flex-col justify-start min-h-full pb-8">
          {!hasMessages ? (
            /* Welcome / Idle State */
            <div className="flex flex-col items-center justify-center text-center my-auto py-8">
              <div className="p-3 transition-transform duration-300 mb-2">
                <ThinkingOrb state={orbState || 'breathing'} size={72} theme="light" />
              </div>

              <h2 className="text-xl sm:text-2xl font-bold text-neutral-900 tracking-tight mb-2">
                Local AI Document Agent
              </h2>
              <p className="text-xs sm:text-sm text-neutral-500 max-w-md mx-auto mb-8 leading-relaxed">
                Natural-language document search, instant retrieval, and grounded Q&A with complete local privacy.
              </p>

              {/* Suggestion Starter Pills */}
              <div className="w-full max-w-lg">
                <p className="text-[11px] font-semibold text-neutral-400 uppercase tracking-wider mb-2.5">
                  Suggested Queries
                </p>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-left">
                  {suggestions.map((item, idx) => (
                    <button
                      key={idx}
                      type="button"
                      onClick={() => onSendMessage(item)}
                      disabled={!isBackendReady || isProcessing}
                      className="p-2.5 rounded-xl neu-button text-xs font-medium text-neutral-700 hover:text-neutral-950 border border-neutral-200/80 transition-all flex items-center justify-between group active:scale-[0.98]"
                    >
                      <span className="truncate">{item}</span>
                      <Sparkles className="w-3.5 h-3.5 text-neutral-400 group-hover:text-neutral-800 transition-colors flex-shrink-0" />
                    </button>
                  ))}
                </div>
              </div>
            </div>
          ) : (
            /* Chronological Message Stream */
            <div className="w-full space-y-4 pt-2">
              {messages.map((msg) => (
                <ChatMessage
                  key={msg.id}
                  message={msg}
                  onSelectOption={onSelectOption}
                  onOpenDocument={onOpenDocument}
                  onShowLocation={onShowLocation}
                />
              ))}

              {/* Temporary Assistant Thinking State */}
              {isThinking && (
                <ThinkingMessage
                  orbState={orbState}
                  statusText={thinkingStatus}
                />
              )}
            </div>
          )}
        </div>
      </div>

      {/* Fixed Bottom Composer Container */}
      <div className="sticky bottom-0 w-full px-4 sm:px-8 pb-5 pt-3 bg-gradient-to-t from-[#F5F5F5] via-[#F5F5F5]/95 to-transparent z-20">
        <div className="max-w-2xl mx-auto w-full">
          <Composer
            onSendMessage={onSendMessage}
            disabled={!isBackendReady || isProcessing}
            isProcessing={isProcessing}
            focusTrigger={composerFocusTrigger}
          />
        </div>
      </div>
    </main>
  );
}
