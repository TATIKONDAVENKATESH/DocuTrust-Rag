import { useState } from "react";
import { BookOpen, Globe, ChevronDown, ChevronUp, Gauge } from "lucide-react";
import type { Citation, RetrievedChunkPreview } from "../types";

interface CitationListProps {
  citations: Citation[];
  confidence?: number;
  usedWebFallback?: boolean;
  retrievedChunks?: RetrievedChunkPreview[];
}

function confidenceColor(score: number): string {
  if (score >= 0.6) return "text-green-400 border-green-800/60 bg-green-900/30";
  if (score >= 0.3) return "text-yellow-400 border-yellow-800/60 bg-yellow-900/30";
  return "text-red-400 border-red-800/60 bg-red-900/30";
}

export function CitationList({
  citations,
  confidence,
  usedWebFallback,
  retrievedChunks,
}: CitationListProps) {
  const [showRetrieved, setShowRetrieved] = useState(false);

  if (!citations || citations.length === 0) return null;

  const hasConfidence = typeof confidence === "number";

  return (
    <div className="mt-3 pt-3 border-t border-slate-700/50">
      <div className="flex items-center gap-2 mb-2">
        <p className="text-xs font-semibold text-slate-500 flex items-center gap-1">
          <BookOpen className="w-3 h-3" />
          Sources
        </p>

        {hasConfidence && (
          <span
            className={`inline-flex items-center gap-1 rounded-md border px-1.5 py-0.5 text-xs font-mono ${confidenceColor(
              confidence!
            )}`}
            title="Average cross-encoder relevance score of the chunks used in this answer"
          >
            <Gauge className="w-3 h-3" />
            {(confidence! * 100).toFixed(0)}% confidence
          </span>
        )}

        {usedWebFallback && (
          <span
            className="inline-flex items-center gap-1 rounded-md border border-blue-800/60 bg-blue-900/30 text-blue-300 px-1.5 py-0.5 text-xs"
            title="No sufficiently relevant document chunks were found — this answer used web search fallback"
          >
            <Globe className="w-3 h-3" />
            Web fallback
          </span>
        )}
      </div>

      <div className="flex flex-wrap gap-1.5">
        {citations.map((c, i) => (
          <span
            key={i}
            className="inline-flex items-center gap-1 bg-brand-900/40 border border-brand-800/60 text-brand-300 rounded-md px-2 py-0.5 text-xs font-mono"
            title={c.text_preview ? `${c.text_preview}` : `Chunk ID: ${c.chunk_id}`}
          >
            {c.filename}
            {c.page_number != null && (
              <span className="text-brand-500">p.{c.page_number}</span>
            )}
            {typeof c.relevance_score === "number" && (
              <span className="text-brand-500">· {(c.relevance_score * 100).toFixed(0)}%</span>
            )}
          </span>
        ))}
      </div>

      {retrievedChunks && retrievedChunks.length > 0 && (
        <div className="mt-2">
          <button
            onClick={() => setShowRetrieved((v) => !v)}
            className="flex items-center gap-1 text-xs text-slate-500 hover:text-slate-300 transition-colors"
          >
            {showRetrieved ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
            {showRetrieved ? "Hide" : "Show"} all retrieved chunks ({retrievedChunks.length})
          </button>
          {showRetrieved && (
            <div className="mt-2 space-y-1.5">
              {retrievedChunks.map((chunk, i) => (
                <div
                  key={i}
                  className="bg-slate-900/60 border border-slate-800 rounded-md px-2 py-1.5 text-xs text-slate-400"
                >
                  <p className="text-slate-500 font-mono mb-0.5">
                    {chunk.filename}
                    {chunk.page_number != null && ` · p.${chunk.page_number}`}
                  </p>
                  <p className="line-clamp-2">{chunk.text_preview}</p>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}