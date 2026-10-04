import React from 'react';
import { FileText, Copy, Check } from 'lucide-react';

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

export default function ResponseArea({
  response,
  ambiguous,
  searchResults,
  onSelectOption,
  onCopy,
  copied
}) {
  if (!response && (!ambiguous || !searchResults?.length)) return null;

  return (
    <div className="w-full neu-raised rounded-2xl p-5 sm:p-6 border border-neutral-200/80 transition-all animate-fadeIn">
      {/* Header bar with copy option */}
      <div className="flex items-center justify-between mb-3 border-b border-neutral-200/60 pb-2">
        <span className="text-[11px] font-semibold text-neutral-400 uppercase tracking-wider">
          Result
        </span>

        {typeof response === 'string' && response && (
          <button
            type="button"
            onClick={onCopy}
            className="text-neutral-400 hover:text-neutral-700 p-1 rounded transition-colors focus:outline-none focus:ring-1 focus:ring-neutral-400"
            aria-label="Copy response text"
            title="Copy response"
          >
            {copied ? <Check className="w-3.5 h-3.5 text-neutral-800" /> : <Copy className="w-3.5 h-3.5" />}
          </button>
        )}
      </div>

      {/* Main Response Content */}
      {response && (
        <div className="max-h-[320px] overflow-y-auto pr-1">
          <SimpleMarkdown content={response} />
        </div>
      )}

      {/* Ambiguity Clarification Options */}
      {ambiguous && searchResults && searchResults.length > 0 && (
        <div className="mt-4 pt-3 border-t border-neutral-200/60">
          <div className="text-xs font-medium text-neutral-500 mb-2">
            Select a document:
          </div>
          <div className="flex flex-wrap gap-2">
            {searchResults.map((doc, idx) => (
              <button
                key={doc.path || idx}
                type="button"
                onClick={() => onSelectOption(doc)}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl neu-button text-xs font-medium text-neutral-800 hover:text-neutral-900 border border-neutral-300/50 transition-all focus:outline-none focus:ring-2 focus:ring-neutral-400 active:scale-95"
              >
                <FileText className="w-3.5 h-3.5 text-neutral-600" />
                <span>{doc.name}</span>
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
