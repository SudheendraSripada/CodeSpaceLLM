"use client";

import { FormEvent, useEffect, useState } from "react";
import { AppShell } from "@/components/AppShell";
import { FilePicker } from "@/components/FilePicker";
import { MessageList } from "@/components/MessageList";
import {
  ConversationOut,
  FileOut,
  listConversations,
  listMessages,
  MessageOut,
  sendMessage,
  User
} from "@/lib/api";
import { AlertCircle, Plus, Send } from "lucide-react";

export function ChatClient({ token, user }: { token: string; user: User }) {
  const [conversations, setConversations] = useState<ConversationOut[]>([]);
  const [activeConversationId, setActiveConversationId] = useState<string | null>(null);
  const [messages, setMessages] = useState<MessageOut[]>([]);
  const [draft, setDraft] = useState("");
  const [selectedFiles, setSelectedFiles] = useState<FileOut[]>([]);
  const [isSending, setIsSending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    refreshConversations();
  }, []);

  async function refreshConversations(nextActiveId?: string) {
    try {
      const data = await listConversations(token);
      setConversations(data);
      const id = nextActiveId ?? activeConversationId ?? data[0]?.id ?? null;
      if (id) {
        setActiveConversationId(id);
        setMessages(await listMessages(token, id));
      }
    } catch (error) {
      setError(error instanceof Error ? error.message : "Could not load conversations");
    }
  }

  async function openConversation(id: string) {
    setActiveConversationId(id);
    setError(null);
    try {
      setMessages(await listMessages(token, id));
    } catch (error) {
      setError(error instanceof Error ? error.message : "Could not load messages");
    }
  }

  function newConversation() {
    setActiveConversationId(null);
    setMessages([]);
    setSelectedFiles([]);
    setDraft("");
    setError(null);
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    const message = draft.trim();
    if (!message || isSending) return;

    const optimistic: MessageOut = {
      id: `draft-${Date.now()}`,
      role: "user",
      content: message,
      attachments: selectedFiles,
      created_at: new Date().toISOString()
    };
    setMessages((current) => [...current, optimistic]);
    setDraft("");
    setSelectedFiles([]);
    setIsSending(true);
    setError(null);

    try {
      const response = await sendMessage(token, {
        message,
        conversation_id: activeConversationId,
        file_ids: selectedFiles.map((file) => file.id)
      });
      setActiveConversationId(response.conversation.id);
      await refreshConversations(response.conversation.id);
    } catch (error) {
      setError(error instanceof Error ? error.message : "Message failed");
      setMessages((current) => current.filter((item) => item.id !== optimistic.id));
    } finally {
      setIsSending(false);
    }
  }

  return (
    <AppShell user={user}>
      <main className="chat-layout">
        <aside className="conversation-sidebar">
          <button type="button" className="new-chat-button" onClick={newConversation}>
            <Plus size={17} />
            New chat
          </button>
          <div className="conversation-list">
            {conversations.map((conversation) => (
              <button
                type="button"
                key={conversation.id}
                className={conversation.id === activeConversationId ? "conversation active" : "conversation"}
                onClick={() => openConversation(conversation.id)}
              >
                <span>{conversation.title}</span>
              </button>
            ))}
          </div>
        </aside>
        <section className="chat-panel">
          {error ? (
            <div className="error-banner">
              <AlertCircle size={18} />
              {error}
            </div>
          ) : null}
          <MessageList messages={messages} isLoading={isSending} />
          <form className="composer" onSubmit={submit}>
            <FilePicker token={token} files={selectedFiles} onFilesChange={setSelectedFiles} onError={setError} />
            <textarea
              value={draft}
              onChange={(event) => setDraft(event.target.value)}
              placeholder="Message Assistant"
              rows={3}
              onKeyDown={(event) => {
                if (event.key === "Enter" && !event.shiftKey) {
                  event.preventDefault();
                  event.currentTarget.form?.requestSubmit();
                }
              }}
            />
            <button className="send-button" type="submit" disabled={!draft.trim() || isSending} title="Send message">
              <Send size={18} />
            </button>
          </form>
        </section>
      </main>
    </AppShell>
  );
}
