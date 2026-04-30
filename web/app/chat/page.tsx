"use client";

import { AuthGate } from "@/components/AuthGate";
import { ChatClient } from "@/components/ChatClient";

export default function ChatPage() {
  return <AuthGate>{({ user, token }) => <ChatClient user={user} token={token} />}</AuthGate>;
}

