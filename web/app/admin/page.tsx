"use client";

import { AdminPanel } from "@/components/AdminPanel";
import { AuthGate } from "@/components/AuthGate";

export default function AdminPage() {
  return (
    <AuthGate requireRole="admin">
      {({ user, token }) => <AdminPanel user={user} token={token} />}
    </AuthGate>
  );
}

