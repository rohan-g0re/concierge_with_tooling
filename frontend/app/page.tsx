/**
 * P7 Chat Shell — Full implementation.
 *
 * Layout (1280px desktop-first):
 *   - Top bar (navy, Meridian Line brand) — unchanged from P0
 *   - Body: flex row
 *     - Chat column (flex:1, bg chatBg): greeting → message stream → suggestion chips → composer
 *     - Draft rail (240px, bg white): placeholder for P9
 *
 * Session: per-tab sessionStorage (new tab = new session, reload = restored transcript)
 * Streaming: SSE via fetch ReadableStream; text deltas accumulate in last assistant message
 */
"use client";

import React, { useState, useEffect, useCallback, useRef } from "react";
import { MessageStream } from "@/components/chat/MessageStream";
import { Composer } from "@/components/chat/Composer";
import { SuggestionChips } from "@/components/chips/SuggestionChips";
import { postChat } from "@/lib/api";
import {
  getSessionId,
  saveTranscript,
  loadTranscript,
  newMessageId,
} from "@/lib/session";
import type { TranscriptMessage } from "@/lib/session";
import type { ComponentDescriptor } from "@/lib/api";

// ---------------------------------------------------------------------------
// Greeting
// ---------------------------------------------------------------------------

function Greeting() {
  return (
    <div className="flex flex-col items-center justify-center flex-1 px-6 py-16 gap-3 text-center">
      <p
        className="font-display text-3xl font-medium"
        style={{ color: "#0C2340" }}
      >
        Good afternoon, Eleanor.
      </p>
      <p
        className="font-sans text-base max-w-md"
        style={{ color: "#5A6B7E" }}
      >
        Where would you like to sail? I can help you search, compare, and
        build your cruise — step by step.
      </p>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Draft rail placeholder
// ---------------------------------------------------------------------------

function DraftRail() {
  return (
    <aside
      className="flex-none flex flex-col"
      style={{ width: "240px", background: "#fff", borderLeft: "1px solid rgba(12,35,64,0.08)" }}
    >
      <div
        className="px-4 py-4 font-sans font-semibold text-sm"
        style={{ color: "#0C2340", borderBottom: "1px solid rgba(12,35,64,0.08)" }}
      >
        Drafts
      </div>
      <div className="flex-1 flex items-center justify-center px-4">
        <p
          className="font-sans text-xs text-center"
          style={{ color: "#8A97A6", lineHeight: "1.6" }}
        >
          Pinned drafts appear here
        </p>
      </div>
    </aside>
  );
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

export default function ChatShellPage() {
  const [messages, setMessages] = useState<TranscriptMessage[]>([]);
  const [chips, setChips] = useState<string[]>([]);
  const [streaming, setStreaming] = useState(false);
  const sessionIdRef = useRef<string>("");

  // Hydrate transcript from sessionStorage on mount
  useEffect(() => {
    sessionIdRef.current = getSessionId();
    const saved = loadTranscript();
    if (saved) {
      setMessages(saved.messages);
      // Restore chips from the last assistant message
      const lastAssistant = [...saved.messages].reverse().find((m) => m.role === "assistant");
      if (lastAssistant?.chips) setChips(lastAssistant.chips);
    }
  }, []);

  // Persist transcript whenever messages change
  useEffect(() => {
    if (messages.length > 0) {
      saveTranscript({ messages });
    }
  }, [messages]);

  const sendMessage = useCallback(
    async (text: string) => {
      if (streaming) return;

      // Add user message
      const userMsg: TranscriptMessage = {
        id: newMessageId(),
        role: "user",
        text,
      };

      // Add streaming assistant placeholder
      const assistantId = newMessageId();
      const assistantMsg: TranscriptMessage = {
        id: assistantId,
        role: "assistant",
        text: "",
        streaming: true,
        components: [],
        chips: [],
      };

      setMessages((prev) => [...prev, userMsg, assistantMsg]);
      setChips([]);
      setStreaming(true);

      try {
        await postChat(
          sessionIdRef.current,
          text,
          // onDelta — accumulate streaming text
          (delta: string) => {
            setMessages((prev) =>
              prev.map((m) =>
                m.id === assistantId
                  ? { ...m, text: m.text + delta }
                  : m
              )
            );
          },
          // onTerminal — attach components and chips
          (payload: { components: ComponentDescriptor[]; chips: string[] }) => {
            setMessages((prev) =>
              prev.map((m) =>
                m.id === assistantId
                  ? {
                      ...m,
                      streaming: false,
                      components: payload.components,
                      chips: payload.chips,
                    }
                  : m
              )
            );
            setChips(payload.chips);
          }
        );
      } catch {
        // Show error in assistant bubble
        setMessages((prev) =>
          prev.map((m) =>
            m.id === assistantId
              ? {
                  ...m,
                  streaming: false,
                  text: "Sorry, I couldn't reach the server. Please try again.",
                  components: [],
                }
              : m
          )
        );
      } finally {
        setStreaming(false);
      }
    },
    [streaming]
  );

  const handleChipClick = useCallback(
    (chip: string) => {
      sendMessage(chip);
    },
    [sendMessage]
  );

  const isEmpty = messages.length === 0;

  return (
    <div className="min-h-screen flex flex-col" style={{ background: "#E9ECEF" }}>
      {/* ── Top bar ── */}
      <header
        className="w-full flex items-center justify-between px-6 py-4 flex-none"
        style={{ backgroundColor: "#0C2340" }}
      >
        {/* Brand identity */}
        <div className="flex flex-col leading-tight">
          <span
            className="font-display font-semibold uppercase"
            style={{ color: "#C8A45C", fontSize: "1.05rem", letterSpacing: "0.2em" }}
          >
            MERIDIAN LINE
          </span>
          <span
            className="font-sans uppercase"
            style={{ color: "rgba(255,255,255,0.55)", fontSize: "0.65rem", letterSpacing: "0.18em" }}
          >
            COMPASS · CRUISE CONCIERGE
          </span>
        </div>

        {/* Navigation */}
        <nav className="flex items-center gap-6">
          <button
            className="font-sans text-sm transition-colors"
            style={{ color: "rgba(255,255,255,0.65)" }}
            aria-label="Exit AI Assistant"
          >
            Exit AI Assistant
          </button>
          <button
            className="font-sans text-sm px-4 py-1.5 rounded-full border transition-colors"
            style={{
              color: "#C8A45C",
              borderColor: "#C8A45C",
              backgroundColor: "transparent",
            }}
            aria-label="Start New Chat"
            onClick={() => {
              if (typeof window !== "undefined") {
                sessionStorage.clear();
                window.location.reload();
              }
            }}
          >
            Start New Chat
          </button>
        </nav>
      </header>

      {/* ── Body: chat column + draft rail ── */}
      <div className="flex flex-1 min-h-0 max-w-[1280px] w-full mx-auto">
        {/* Chat column */}
        <main
          className="flex-1 flex flex-col min-h-0"
          style={{ background: "#F4F6F8" }}
        >
          {/* Scrollable message area */}
          <div className="flex-1 overflow-y-auto">
            {isEmpty ? (
              <Greeting />
            ) : (
              <MessageStream
                messages={messages}
                onChipClick={handleChipClick}
              />
            )}
          </div>

          {/* Suggestion chips from last turn */}
          {!streaming && chips.length > 0 && (
            <SuggestionChips chips={chips} onChipClick={handleChipClick} />
          )}

          {/* Composer */}
          <Composer onSend={sendMessage} disabled={streaming} />
        </main>

        {/* Draft rail */}
        <DraftRail />
      </div>
    </div>
  );
}
