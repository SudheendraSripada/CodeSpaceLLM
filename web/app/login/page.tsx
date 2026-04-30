"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import { login, register, storeToken } from "@/lib/api";
import { Loader2, LogIn, UserPlus } from "lucide-react";

export default function LoginPage() {
  const router = useRouter();
  const [mode, setMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const response = mode === "login" ? await login(email, password) : await register(email, password);
      storeToken(response.access_token);
      router.replace("/chat");
    } catch (error) {
      setError(error instanceof Error ? error.message : "Authentication failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="login-screen">
      <section className="login-panel">
        <div className="login-heading">
          <h1>Assistant</h1>
          <p>{mode === "login" ? "Sign in to continue." : "Create a user account."}</p>
        </div>
        <form onSubmit={submit} className="login-form">
          <label>
            <span>Email</span>
            <input type="email" value={email} onChange={(event) => setEmail(event.target.value)} required />
          </label>
          <label>
            <span>Password</span>
            <input
              type="password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              minLength={1}
              required
            />
          </label>
          {error ? <div className="form-error">{error}</div> : null}
          <button className="primary-button" type="submit" disabled={loading}>
            {loading ? <Loader2 className="spin" size={18} /> : mode === "login" ? <LogIn size={18} /> : <UserPlus size={18} />}
            {mode === "login" ? "Sign in" : "Create account"}
          </button>
        </form>
        <button className="link-button" type="button" onClick={() => setMode(mode === "login" ? "register" : "login")}>
          {mode === "login" ? "Create account" : "Use existing account"}
        </button>
      </section>
    </main>
  );
}

