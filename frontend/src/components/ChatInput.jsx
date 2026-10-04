import React, { useState, useRef, useEffect } from 'react';
import { MetalFx, useMetalBend } from 'metal-fx';
import { ArrowUp } from 'lucide-react';

export default function ChatInput({ onSendMessage, disabled, isProcessing }) {
  const [text, setText] = useState('');
  const textareaRef = useRef(null);
  const sendButtonRef = useRef(null);

  // Apply cursor-driven dent effect to metal send button
  useMetalBend(sendButtonRef);

  useEffect(() => {
    // Focus input on initial mount
    if (textareaRef.current) {
      textareaRef.current.focus();
    }
  }, []);

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleSend = () => {
    const trimmed = text.trim();
    if (trimmed && !disabled && !isProcessing) {
      onSendMessage(trimmed);
      setText('');
    }
  };

  return (
    <div className="w-full relative">
      <div className="neu-inset-deep rounded-2xl p-2 sm:p-2.5 flex items-center gap-3 border border-neutral-300/60 focus-within:border-neutral-400 focus-within:ring-1 focus-within:ring-neutral-400 transition-all">
        <label htmlFor="agent-chat-input" className="sr-only">
          Ask or search your documents
        </label>
        <textarea
          id="agent-chat-input"
          ref={textareaRef}
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Ask or search your documents..."
          disabled={disabled || isProcessing}
          rows={1}
          className="w-full bg-transparent text-neutral-900 placeholder-neutral-400 text-sm sm:text-base resize-none focus:outline-none px-3 py-2 min-h-[44px] max-h-[140px] leading-relaxed"
        />

        <div className="flex-shrink-0 flex items-center pr-1">
          <div ref={sendButtonRef} className="inline-block">
            <MetalFx
              preset="chromatic"
              variant="circle"
              innerShadow
              strength={0.90}
            >
              <button
                type="button"
                aria-label="Send query"
                onClick={handleSend}
                disabled={disabled || isProcessing || !text.trim()}
                className={`w-10 h-10 rounded-full flex items-center justify-center transition-all ${
                  !text.trim() || disabled || isProcessing
                    ? 'opacity-40 cursor-not-allowed bg-neutral-200 text-neutral-400'
                    : 'bg-neutral-900 hover:bg-neutral-800 text-white cursor-pointer active:scale-95'
                }`}
              >
                <ArrowUp className="w-5 h-5 stroke-[2.5]" />
              </button>
            </MetalFx>
          </div>
        </div>
      </div>
    </div>
  );
}
