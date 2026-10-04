import React, { useState } from 'react';
import { Sparkles, FileText, ExternalLink, MapPin, Copy, Check } from 'lucide-react';

function formatInline(text) {
  const parts = text.split(/(\*\*.*?\*\*|`.*?`)/g);
  return parts.map((part, i) => {
    if (part.startsWith('**') && part.endsWith('**')) {
      return <strong key={i} className="font-semibold text-neutral-900">{part.slice(2, -2)}</strong>;
    }
    if (part.startsWith('`') && part.endsWith('`')) {
      return <code key={i} className="bg-neutral-200/70 px-1.5 py-0.5 rounded text-xs font-mono text-neutral-900">{part.slice(1, -1)}</code>;
    }
    return part;
  });
}

function SimpleMarkdown({ content }) {
  if (typeof content !== 'string') return null;

  const lines = content.split('\n');
  const elements = [];
  let key = 0;
  let inCodeBlock = false;
  let codeBuffer = [];

  lines.forEach((line) => {
    if (line.trim().startsWith('```')) {
      if (inCodeBlock) {
        elements.push(
          <pre key={key++} className="bg-neutral-200/80 p-3 rounded-lg text-xs font-mono overflow-x-auto my-2 text-neutral-900 border border-neutral-300/60">
            <code>{codeBuffer.join('\n')}</code>
          </pre>
        );
        codeBuffer = [];
        inCodeBlock = false;
      } else {
        inCodeBlock = true;
      }
      return;
    }

    if (inCodeBlock) {
      codeBuffer.push(line);
      return;
    }

    const trimmed = line.trim();
    if (!trimmed) {
      elements.push(<div key={key++} className="h-2" />);
      return;
    }

    if (trimmed.startsWith('### ')) {
      elements.push(
        <h3 key={key++} className="text-sm font-semibold text-neutral-900 mt-3 mb-1 tracking-tight">
          {formatInline(trimmed.slice(4))}
        </h3>
      );
    } else if (trimmed.startsWith('## ')) {
      elements.push(
        <h2 key={key++} className="text-base font-semibold text-neutral-900 mt-4 mb-1 tracking-tight">
          {formatInline(trimmed.slice(3))}
        </h2>
      );
    } else if (trimmed.startsWith('# ')) {
      elements.push(
        <h1 key={key++} className="text-lg font-bold text-neutral-900 mt-4 mb-2 tracking-tight">
          {formatInline(trimmed.slice(2))}
        </h1>
      );
    } else if (trimmed.startsWith('- ') || trimmed.startsWith('* ')) {
      elements.push(
        <li key={key++} className="ml-4 list-disc text-sm text-neutral-800 my-0.5 leading-relaxed">
          {formatInline(trimmed.slice(2))}
        </li>
      );
    } else {
      elements.push(
        <p key={key++} className="text-sm text-neutral-800 my-1 leading-relaxed">
          {formatInline(trimmed)}
        </p>
      );
    }
  });

  return <div className="space-y-1">{elements}</div>;
}

export default function ChatMessage({
  message,
  onSelectOption,
  onOpenDocument,
  onShowLocation
}) {
  const [copied, setCopied] = useState(false);

  if (message.role === 'user') {
    return (
      <div className="flex justify-end w-full animate-fadeIn">
        <div className="max-w-[85%] sm:max-w-[75%] px-4 py-2.5 rounded-2xl bg-neutral-900 text-neutral-100 text-sm font-normal shadow-sm leading-relaxed whitespace-pre-wrap">
          {message.content}
        </div>
      </div>
    );
  }

  // Assistant message
  const handleCopy = () => {
    if (message.content) {
      navigator.clipboard.writeText(message.content);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  const action = message.action;
  const targetDoc = message.targetDocument;
  const canOpen = targetDoc && targetDoc.path && action !== 'open' && action !== 'search_open' && !message.ambiguous;
  const canLocation = targetDoc && action === 'search' && !message.ambiguous;

  let badgeLabel = null;
  if (action === 'search') badgeLabel = 'Search';
  else if (action === 'search_open' || action === 'open') badgeLabel = 'Opened';
  else if (action === 'location') badgeLabel = 'Location';
  else if (action === 'summarize' || action === 'search_summarize') badgeLabel = 'Summary';
  else if (action === 'ask') badgeLabel = 'Answer';

  return (
    <div className="flex justify-start w-full animate-fadeIn">
      <div className="max-w-[92%] sm:max-w-[85%] rounded-2xl p-4 sm:p-5 neu-raised border border-neutral-200/90 text-neutral-900 shadow-sm transition-all">
        {/* Header */}
        <div className="flex items-center justify-between pb-2.5 mb-2.5 border-b border-neutral-200/60">
          <div className="flex items-center gap-2">
            <div className="w-5 h-5 rounded-md bg-neutral-900 text-white flex items-center justify-center p-0.5 neu-button">
              <Sparkles className="w-3 h-3 stroke-[2.5]" />
            </div>
            <span className="text-xs font-bold text-neutral-900 tracking-tight">
              Local AI
            </span>
            {badgeLabel && (
              <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-neutral-200/80 text-neutral-600 uppercase tracking-wider">
                {badgeLabel}
              </span>
            )}
            {message.isStreaming && (
              <span className="text-[10px] font-medium px-2 py-0.5 rounded-full bg-neutral-200/60 text-neutral-500 animate-pulse">
                Streaming...
              </span>
            )}
          </div>
        </div>

        {/* Message Content */}
        <div className="text-sm text-neutral-800 leading-relaxed overflow-x-auto">
          <SimpleMarkdown content={message.content} />
          {message.isStreaming && (
            <span className="inline-block w-1.5 h-3.5 ml-1 bg-neutral-700 animate-pulse align-middle" />
          )}
        </div>

        {/* Ambiguity Choices */}
        {message.ambiguous && message.results && message.results.length > 0 && (
          <div className="mt-3 pt-3 border-t border-neutral-200/60">
            <p className="text-xs font-medium text-neutral-500 mb-2">Select a document:</p>
            <div className="flex flex-wrap gap-2">
              {message.results.map((doc, idx) => (
                <button
                  key={doc.path || idx}
                  type="button"
                  onClick={() => onSelectOption && onSelectOption(doc)}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl neu-button text-xs font-medium text-neutral-800 hover:text-neutral-950 border border-neutral-300/50 transition-all active:scale-95"
                >
                  <FileText className="w-3.5 h-3.5 text-neutral-600" />
                  <span>{doc.name}</span>
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Contextual Action Buttons */}
        <div className="mt-3 pt-2.5 border-t border-neutral-200/60 flex items-center justify-end gap-1.5 text-xs">
          {canOpen && onOpenDocument && (
            <button
              type="button"
              onClick={() => onOpenDocument(targetDoc)}
              className="flex items-center gap-1 px-2.5 py-1 rounded-lg hover:bg-neutral-200/70 text-neutral-600 hover:text-neutral-900 transition-colors"
              title="Open document in native viewer"
            >
              <ExternalLink className="w-3.5 h-3.5 text-neutral-500" />
              <span>Open</span>
            </button>
          )}

          {canLocation && onShowLocation && (
            <button
              type="button"
              onClick={() => onShowLocation(targetDoc)}
              className="flex items-center gap-1 px-2.5 py-1 rounded-lg hover:bg-neutral-200/70 text-neutral-600 hover:text-neutral-900 transition-colors"
              title="Find file location"
            >
              <MapPin className="w-3.5 h-3.5 text-neutral-500" />
              <span>Location</span>
            </button>
          )}

          <button
            type="button"
            onClick={handleCopy}
            className="flex items-center gap-1 px-2.5 py-1 rounded-lg hover:bg-neutral-200/70 text-neutral-500 hover:text-neutral-900 transition-colors"
            title="Copy response text"
          >
            {copied ? (
              <>
                <Check className="w-3.5 h-3.5 text-neutral-900" />
                <span className="text-neutral-900 font-medium">Copied</span>
              </>
            ) : (
              <>
                <Copy className="w-3.5 h-3.5" />
                <span>Copy</span>
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
}
