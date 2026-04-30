"use client";

import { useRouter } from "next/navigation";
import { ReactNode, useEffect, useState } from "react";
import { clearToken, getStoredToken, me, Role, User } from "@/lib/api";
import { Loader2, Lock } from "lucide-react";

export function AuthGate({
  children,
  requireRole
}: {
  children: (context: { user: User; token: string }) => ReactNode;
  requireRole?: Role;
}) {
  const router = useRouter();
  const [state, setState] = useState<
    | { status: "loading" }
    | { status: "ready"; user: User; token: string }
    | { status: "blocked"; message: string }
  >({ status: "loading" });

  useEffect(() => {
    const token = getStoredToken();
    if (!token) {
      router.replace("/login");
      return;
    }
    me(token)
      .then((user) => {
        if (requireRole && user.role !== requireRole) {
          setState({ status: "blocked", message: "Admin access required." });
          return;
        }
        setState({ status: "ready", user, token });
      })
      .catch(() => {
        clearToken();
        router.replace("/login");
      });
  }, [requireRole, router]);

  if (state.status === "loading") {
    return (
      <main className="center-screen">
        <Loader2 className="spin" size={24} />
      </main>
    );
  }

  if (state.status === "blocked") {
    return (
      <main className="center-screen blocked">
        <Lock size={28} />
        <h1>Access blocked</h1>
        <p>{state.message}</p>
      </main>
    );
  }

  return <>{children({ user: state.user, token: state.token })}</>;
}

