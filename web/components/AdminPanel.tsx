"use client";

import { FormEvent, useEffect, useState } from "react";
import { AppShell } from "@/components/AppShell";
import { AppSettings, listTools, readSettings, saveSettings, User } from "@/lib/api";
import { AlertCircle, Check, Loader2, Save } from "lucide-react";

export function AdminPanel({ token, user }: { token: string; user: User }) {
  const [settings, setSettings] = useState<AppSettings | null>(null);
  const [availableTools, setAvailableTools] = useState<string[]>([]);
  const [status, setStatus] = useState<"loading" | "ready" | "saving">("loading");
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function load() {
      try {
        const [settingsData, toolData] = await Promise.all([readSettings(token), listTools(token)]);
        setSettings(settingsData);
        setAvailableTools(toolData.available);
        setStatus("ready");
      } catch (error) {
        setError(error instanceof Error ? error.message : "Could not load settings");
        setStatus("ready");
      }
    }
    load();
  }, [token]);

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!settings) return;
    setStatus("saving");
    setError(null);
    setNotice(null);
    try {
      const updated = await saveSettings(token, {
        model_name: settings.model_name,
        system_prompt: settings.system_prompt,
        enabled_tools: settings.enabled_tools
      });
      setSettings(updated);
      setNotice("Settings saved.");
    } catch (error) {
      setError(error instanceof Error ? error.message : "Could not save settings");
    } finally {
      setStatus("ready");
    }
  }

  function toggleTool(name: string) {
    if (!settings) return;
    const enabled = new Set(settings.enabled_tools);
    if (enabled.has(name)) {
      enabled.delete(name);
    } else {
      enabled.add(name);
    }
    setSettings({ ...settings, enabled_tools: Array.from(enabled).sort() });
  }

  return (
    <AppShell user={user}>
      <main className="admin-layout">
        <section className="admin-header">
          <h1>Admin settings</h1>
          <p>Provider: {settings?.provider || "loading"}</p>
        </section>
        {status === "loading" ? (
          <div className="center-inline">
            <Loader2 className="spin" size={22} />
          </div>
        ) : null}
        {error ? (
          <div className="error-banner">
            <AlertCircle size={18} />
            {error}
          </div>
        ) : null}
        {notice ? (
          <div className="success-banner">
            <Check size={18} />
            {notice}
          </div>
        ) : null}
        {settings ? (
          <form className="admin-form" onSubmit={submit}>
            <label>
              <span>Model name</span>
              <input
                value={settings.model_name}
                onChange={(event) => setSettings({ ...settings, model_name: event.target.value })}
              />
            </label>
            <label>
              <span>System prompt</span>
              <textarea
                value={settings.system_prompt}
                rows={8}
                onChange={(event) => setSettings({ ...settings, system_prompt: event.target.value })}
              />
            </label>
            <fieldset className="tool-fieldset">
              <legend>Enabled tools</legend>
              <div className="tool-grid">
                {availableTools.map((tool) => (
                  <label className="check-row" key={tool}>
                    <input
                      type="checkbox"
                      checked={settings.enabled_tools.includes(tool)}
                      onChange={() => toggleTool(tool)}
                    />
                    <span>{tool}</span>
                  </label>
                ))}
              </div>
            </fieldset>
            <button className="primary-button" type="submit" disabled={status === "saving"}>
              {status === "saving" ? <Loader2 className="spin" size={18} /> : <Save size={18} />}
              Save settings
            </button>
          </form>
        ) : null}
      </main>
    </AppShell>
  );
}

