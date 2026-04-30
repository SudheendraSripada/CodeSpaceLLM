"use client";

import { ChangeEvent, useRef, useState } from "react";
import { FileOut, uploadFile } from "@/lib/api";
import { FileText, Loader2, Paperclip, X } from "lucide-react";

export function FilePicker({
  token,
  files,
  onFilesChange,
  onError
}: {
  token: string;
  files: FileOut[];
  onFilesChange: (files: FileOut[]) => void;
  onError: (message: string) => void;
}) {
  const inputRef = useRef<HTMLInputElement | null>(null);
  const [uploading, setUploading] = useState(false);

  async function onSelect(event: ChangeEvent<HTMLInputElement>) {
    const selected = Array.from(event.target.files || []);
    if (!selected.length) return;
    setUploading(true);
    try {
      const uploaded: FileOut[] = [];
      for (const file of selected) {
        uploaded.push(await uploadFile(token, file));
      }
      onFilesChange([...files, ...uploaded]);
    } catch (error) {
      onError(error instanceof Error ? error.message : "Upload failed");
    } finally {
      setUploading(false);
      event.target.value = "";
    }
  }

  return (
    <div className="file-picker">
      <input
        ref={inputRef}
        type="file"
        multiple
        accept="image/*,.pdf,.txt,.md,.csv,.json,.log"
        onChange={onSelect}
      />
      <button type="button" className="icon-button" onClick={() => inputRef.current?.click()} disabled={uploading} title="Attach files">
        {uploading ? <Loader2 className="spin" size={18} /> : <Paperclip size={18} />}
      </button>
      {files.length ? (
        <div className="selected-files">
          {files.map((file) => (
            <span className="file-chip" key={file.id} title={file.summary}>
              <FileText size={14} />
              {file.filename}
              <button
                type="button"
                title="Remove file"
                onClick={() => onFilesChange(files.filter((item) => item.id !== file.id))}
              >
                <X size={13} />
              </button>
            </span>
          ))}
        </div>
      ) : null}
    </div>
  );
}

