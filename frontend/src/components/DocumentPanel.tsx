import { useCallback, useEffect, useState } from "react";
import { useDropzone } from "react-dropzone";
import {
  FileText,
  Upload,
  Trash2,
  CheckCircle,
  Clock,
  AlertCircle,
  FileType,
} from "lucide-react";
import type { Document } from "../types";
import { uploadDocument, listDocuments, deleteDocument } from "../services/api";

function StatusIcon({ status }: { status: Document["status"] }) {
  if (status === "ready") return <CheckCircle className="w-3.5 h-3.5 text-green-400" />;
  if (status === "processing") return <Clock className="w-3.5 h-3.5 text-yellow-400 animate-pulse" />;
  return <AlertCircle className="w-3.5 h-3.5 text-red-400" />;
}

function formatBytes(bytes: number) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function DocumentPanel() {
  const [docs, setDocs] = useState<Document[]>([]);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState("");

  const fetchDocs = useCallback(async () => {
    try {
      setDocs(await listDocuments());
    } catch {
      /* silently retry */
    }
  }, []);

  useEffect(() => {
    fetchDocs();
    const interval = setInterval(fetchDocs, 5000);
    return () => clearInterval(interval);
  }, [fetchDocs]);

  const onDrop = useCallback(
    async (acceptedFiles: File[]) => {
      setError("");
      setUploading(true);
      try {
        for (const file of acceptedFiles) {
          await uploadDocument(file);
        }
        await fetchDocs();
      } catch (err: unknown) {
        const msg =
          (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ||
          "Upload failed.";
        setError(msg);
      } finally {
        setUploading(false);
      }
    },
    [fetchDocs]
  );

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      "application/pdf": [".pdf"],
      "text/plain": [".txt"],
      "application/vnd.openxmlformats-officedocument.wordprocessingml.document": [".docx"],
    },
    disabled: uploading,
  });

  const handleDelete = async (id: string) => {
    try {
      await deleteDocument(id);
      setDocs((prev) => prev.filter((d) => d.id !== id));
    } catch {
      setError("Delete failed.");
    }
  };

  return (
    <div className="panel h-full">
      <div className="panel-header">
        <FileText className="w-4 h-4 text-brand-400" />
        Documents
        <span className="ml-auto text-xs text-slate-500 font-normal">{docs.length} files</span>
      </div>

      <div className="p-3 shrink-0">
        <div
          {...getRootProps()}
          className={`border-2 border-dashed rounded-xl p-5 text-center cursor-pointer transition-colors ${
            isDragActive
              ? "border-brand-400 bg-brand-600/10"
              : "border-slate-700 hover:border-slate-600"
          } ${uploading ? "opacity-50 cursor-not-allowed" : ""}`}
        >
          <input {...getInputProps()} />
          <Upload className="w-6 h-6 mx-auto mb-2 text-slate-500" />
          <p className="text-xs text-slate-400">
            {isDragActive ? "Drop files here" : "Drop PDF, TXT, or DOCX"}
          </p>
          <p className="text-xs text-slate-600 mt-1">or click to browse</p>
        </div>
        {uploading && (
          <p className="text-xs text-brand-400 text-center mt-2 animate-pulse">Uploading…</p>
        )}
        {error && (
          <p className="text-xs text-red-400 mt-2 text-center">{error}</p>
        )}
      </div>

      <div className="flex-1 overflow-y-auto px-3 pb-3 space-y-2">
        {docs.length === 0 && (
          <p className="text-slate-600 text-xs text-center py-8">
            No documents uploaded yet.
          </p>
        )}
        {docs.map((doc) => (
          <div
            key={doc.id}
            className="flex items-start gap-2 bg-slate-800/50 rounded-lg p-3 group"
          >
            <FileType className="w-4 h-4 text-slate-500 mt-0.5 shrink-0" />
            <div className="flex-1 min-w-0">
              <p className="text-xs font-medium text-slate-200 truncate">{doc.filename}</p>
              <div className="flex items-center gap-1.5 mt-1">
                <StatusIcon status={doc.status} />
                <span className="text-xs text-slate-500">
                  {formatBytes(doc.size_bytes)}
                  {doc.chunk_count > 0 && ` · ${doc.chunk_count} chunks`}
                </span>
              </div>
            </div>
            <button
              onClick={() => handleDelete(doc.id)}
              className="btn-ghost opacity-0 group-hover:opacity-100 p-1 transition-opacity"
              title="Delete document"
            >
              <Trash2 className="w-3.5 h-3.5 text-red-400" />
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}
