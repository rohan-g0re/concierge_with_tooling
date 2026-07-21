"use client";
import React, { useEffect, useState } from "react";
import { getSessionId } from "@/lib/session";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

interface DebugData {
  session_id: string;
  party: number;
  constraints: Record<string, unknown>;
  active_draft_id: string | null;
  drafts: Array<{
    draft_id: string;
    label: string;
    fare_package: string | null;
    stateroom: unknown;
    dining: unknown;
    completed_steps: number[];
    total_per_person: number | null;
  }>;
  messages_count: number;
  messages_meta: Array<{ role: string; id: string | null; ts: unknown }>;
  tool_log: Array<{ event: string; tool?: string; latency_ms?: number; elapsed_ms?: number; ts: number; vote?: string; message_id?: string }>;
}

export default function DebugPage() {
  const [data, setData] = useState<DebugData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [sessionId, setSessionId] = useState<string>("demo");

  useEffect(() => {
    const sid = getSessionId();
    setSessionId(sid);
    fetch(`${API_BASE}/debug?session_id=${encodeURIComponent(sid)}`)
      .then((r) => r.json())
      .then(setData)
      .catch((e) => setError(String(e)));
  }, []);

  const refresh = () => {
    fetch(`${API_BASE}/debug?session_id=${encodeURIComponent(sessionId)}`)
      .then((r) => r.json())
      .then(setData)
      .catch((e) => setError(String(e)));
  };

  return (
    <div style={{ background: "#f8f9fb", minHeight: "100vh", padding: "32px 24px", fontFamily: "ui-monospace, Menlo, monospace" }}>
      <div style={{ maxWidth: 960, margin: "0 auto" }}>
        {/* Header */}
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 24 }}>
          <div>
            <h1 style={{ fontSize: 22, fontWeight: 700, color: "#0C2340", margin: 0 }}>
              🧭 Compass Debug
            </h1>
            <p style={{ fontSize: 12, color: "#8A97A6", margin: "4px 0 0" }}>
              Session: <code>{sessionId}</code>
            </p>
          </div>
          <button
            onClick={refresh}
            style={{
              padding: "8px 20px",
              borderRadius: 999,
              background: "#0C2340",
              color: "#fff",
              border: "none",
              cursor: "pointer",
              fontSize: 13,
              fontWeight: 600,
            }}
          >
            Refresh
          </button>
        </div>

        {error && (
          <div style={{ background: "#fee", border: "1px solid #fcc", borderRadius: 10, padding: 16, marginBottom: 20, color: "#c33", fontSize: 13 }}>
            {error}
          </div>
        )}

        {data ? (
          <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
            {/* Constraints */}
            <Section title="Constraints">
              <pre style={preStyle}>{JSON.stringify({ ...data.constraints, party: data.party }, null, 2)}</pre>
            </Section>

            {/* Active Draft */}
            <Section title={`Active Draft · ${data.active_draft_id ?? "none"}`}>
              {data.active_draft_id ? (
                <pre style={preStyle}>
                  {JSON.stringify(data.drafts.find((d) => d.draft_id === data.active_draft_id), null, 2)}
                </pre>
              ) : (
                <p style={{ fontSize: 13, color: "#8A97A6", margin: 0 }}>No active draft.</p>
              )}
            </Section>

            {/* All Drafts */}
            <Section title={`Drafts (${data.drafts.length})`}>
              {data.drafts.length === 0 ? (
                <p style={{ fontSize: 13, color: "#8A97A6", margin: 0 }}>No drafts yet.</p>
              ) : (
                <pre style={preStyle}>{JSON.stringify(data.drafts, null, 2)}</pre>
              )}
            </Section>

            {/* Messages */}
            <Section title={`Messages (${data.messages_count} total, last 20 shown)`}>
              <pre style={preStyle}>{JSON.stringify(data.messages_meta, null, 2)}</pre>
            </Section>

            {/* Tool Log */}
            <Section title={`Tool-Call Log (last ${data.tool_log.length} events)`}>
              {data.tool_log.length === 0 ? (
                <p style={{ fontSize: 13, color: "#8A97A6", margin: 0 }}>No events yet.</p>
              ) : (
                <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12 }}>
                  <thead>
                    <tr style={{ borderBottom: "1px solid rgba(12,35,64,.12)" }}>
                      {["ts", "event", "tool / id", "latency_ms / elapsed_ms"].map((h) => (
                        <th key={h} style={{ textAlign: "left", padding: "4px 8px", color: "#8A97A6", fontWeight: 600 }}>{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {data.tool_log.map((e, i) => (
                      <tr key={i} style={{ borderBottom: "1px solid rgba(12,35,64,.06)" }}>
                        <td style={tdStyle}>{e.ts?.toFixed?.(3) ?? e.ts}</td>
                        <td style={{ ...tdStyle, color: e.event === "feedback" ? "#C8A45C" : e.event === "first_token" ? "#4E7E86" : "#0C2340" }}>
                          {e.event}
                        </td>
                        <td style={tdStyle}>{e.tool ?? e.message_id ?? "—"}</td>
                        <td style={tdStyle}>{e.latency_ms ?? e.elapsed_ms ?? "—"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </Section>
          </div>
        ) : !error ? (
          <p style={{ color: "#8A97A6", fontSize: 13 }}>Loading…</p>
        ) : null}
      </div>
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div style={{ background: "#fff", borderRadius: 14, border: "1px solid rgba(12,35,64,.10)", padding: "18px 20px" }}>
      <h2 style={{ fontSize: 13, fontWeight: 700, color: "#0C2340", margin: "0 0 12px", textTransform: "uppercase", letterSpacing: ".08em" }}>
        {title}
      </h2>
      {children}
    </div>
  );
}

const preStyle: React.CSSProperties = {
  margin: 0,
  fontSize: 11.5,
  color: "#22344B",
  whiteSpace: "pre-wrap",
  wordBreak: "break-all",
};

const tdStyle: React.CSSProperties = {
  padding: "5px 8px",
  color: "#22344B",
  verticalAlign: "top",
};
