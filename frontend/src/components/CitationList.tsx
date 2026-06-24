import { BookOpen } from "lucide-react";
import type { Citation } from "../types";

export function CitationList({ citations }: { citations: Citation[] }) {
  if (!citations || citations.length === 0) return null;

  return (
    <div className="mt-3 pt-3 border-t border-slate-700/50">
      <p className="text-xs font-semibold text-slate-500 flex items-center gap-1 mb-2">
        <BookOpen className="w-3 h-3" />
        Sources
      </p>
      <div className="flex flex-wrap gap-1.5">
        {citations.map((c, i) => (
          <span
            key={i}
            className="inline-flex items-center gap-1 bg-brand-900/40 border border-brand-800/60 text-brand-300 rounded-md px-2 py-0.5 text-xs font-mono"
            title={`Chunk ID: ${c.chunk_id}`}
          >
            {c.filename}
            {c.page_number != null && (
              <span className="text-brand-500">p.{c.page_number}</span>
            )}
          </span>
        ))}
      </div>
    </div>
  );
}
