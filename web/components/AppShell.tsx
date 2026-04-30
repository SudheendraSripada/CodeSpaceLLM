"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { clearToken, User } from "@/lib/api";
import { LogOut, MessageSquare, Settings } from "lucide-react";

export function AppShell({ user, children }: { user: User; children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();

  function logout() {
    clearToken();
    router.replace("/login");
  }

  return (
    <div className="app-shell">
      <header className="topbar">
        <Link href="/chat" className="brand">
          Assistant
        </Link>
        <nav className="topnav">
          <Link className={pathname === "/chat" ? "active" : ""} href="/chat">
            <MessageSquare size={17} />
            Chat
          </Link>
          {user.role === "admin" ? (
            <Link className={pathname === "/admin" ? "active" : ""} href="/admin">
              <Settings size={17} />
              Admin
            </Link>
          ) : null}
          <button type="button" className="icon-button" onClick={logout} title="Sign out">
            <LogOut size={18} />
          </button>
        </nav>
      </header>
      {children}
    </div>
  );
}

