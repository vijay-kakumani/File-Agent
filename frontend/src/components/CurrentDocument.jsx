import React from 'react';
import { FileText, FileSpreadsheet, FileCode, File, CheckCircle2 } from 'lucide-react';

function getFileIcon(extension) {
  const ext = (extension || '').toLowerCase();
  if (ext === '.pdf') {
    return <FileText className="w-4 h-4 text-neutral-700" />;
  }
  if (['.xlsx', '.xls', '.csv'].includes(ext)) {
    return <FileSpreadsheet className="w-4 h-4 text-neutral-700" />;
  }
  if (['.py', '.js', '.ts', '.json', '.html', '.css', '.rs'].includes(ext)) {
    return <FileCode className="w-4 h-4 text-neutral-700" />;
  }
  return <File className="w-4 h-4 text-neutral-700" />;
}

export default function CurrentDocument({ currentDocument }) {
  if (!currentDocument || !currentDocument.name) {
    return (
      <div className="px-3 py-3 rounded-xl border border-dashed border-neutral-300/80 bg-neutral-200/40 text-neutral-400 text-xs">
        <p className="italic">No document selected</p>
      </div>
    );
  }

  const { name, folder, extension, path } = currentDocument;
  const extLabel = (extension || '').replace('.', '').toUpperCase() || 'FILE';
  const folderLabel = folder || 'Local';

  return (
    <div
      className="p-3 rounded-xl neu-raised-sm border border-neutral-200/90 text-neutral-900 transition-all hover:border-neutral-300"
      title={path || name}
    >
      <div className="flex items-start gap-2.5">
        <div className="p-1.5 rounded-lg bg-neutral-200/70 flex-shrink-0 mt-0.5">
          {getFileIcon(extension)}
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-1.5">
            <h4 className="text-xs font-semibold text-neutral-900 truncate" title={name}>
              {name}
            </h4>
            <CheckCircle2 className="w-3 h-3 text-neutral-700 flex-shrink-0" />
          </div>
          <p className="text-[11px] text-neutral-500 truncate mt-0.5">
            {extLabel} · {folderLabel}
          </p>
        </div>
      </div>
    </div>
  );
}
