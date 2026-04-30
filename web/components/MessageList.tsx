"use client";

import { FileText } from "lucide-react";
import { MessageOut } from "@/lib/api";

export function MessageList({ messages, isLoading }: { messages: MessageOut[]; isLoading: boolean }) {
  return (
    <div className="message-list">
      {messages.length === 0 ? (
        <div className="empty-state">
          <h1>Start a conversation</h1>
          <p>Ask a question, attach a file, or continue from the history.</p>
        </div>
      ) : (
        messages.map((message) => (
          <article key={message.id} className={`message ${message.role}`}>
            <div className="message-meta">{message.role === "assistant" ? "Assistant" : "You"}</div>
            <div className="message-body">{message.content}</div>
            {message.attachments?.length ? (
              <div className="attachment-row">
                {message.attachments.map((file) => (
                  <span className="file-chip" key={file.id}>
                    <FileText size={14} />
                    {file.filename}
                  </span>
                ))}
              </div>
            ) : null}
          </article>
        ))
      )}
      {isLoading ? (
        <article className="message assistant pending">
          <div className="message-meta">Assistant</div>
          <div className="typing-bars" aria-label="Assistant is responding">
            <span />
            <span />
            <span />
          </div>
        </article>
      ) : null}
    </div>
  );
}

