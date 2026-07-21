/**
 * P8 Chat Shell — CardRow + ItineraryPanel wired.
 *
 * Added in P8:
 *  - ItineraryPanel state (open/close, loaded data)
 *  - onSelect: postAction('create_draft', {cruise_id}) → merge components/chips
 *  - onOpenItinerary: postAction('get_itinerary', {cruise_id}) → open panel
 *  - handlers passed to renderComponent via registryHandlers prop on MessageStream
 */
"use client";

import React, { useState, useEffect, useCallback, useRef } from "react";
import { MessageStream } from "@/components/chat/MessageStream";
import { Composer } from "@/components/chat/Composer";
import { SuggestionChips } from "@/components/chips/SuggestionChips";
import { ItineraryPanel } from "@/components/itinerary/ItineraryPanel";
import type { ItineraryDay } from "@/components/itinerary/ItineraryPanel";
import { postChat, postAction } from "@/lib/api";
import {
  getSessionId,
  saveTranscript,
  loadTranscript,
  newMessageId,
} from "@/lib/session";
import type { TranscriptMessage } from "@/lib/session";
import type { ComponentDescriptor } from "@/lib/api";
import type { RegistryHandlers } from "@/lib/componentRegistry";
import { DraftRail } from "@/components/drafts/DraftRail";
import type { DraftInfo } from "@/components/drafts/DraftRail";

// ---------------------------------------------------------------------------
// Session fetch
// ---------------------------------------------------------------------------

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

async function fetchSession(sessionId: string): Promise<{ drafts: DraftInfo[]; active_draft_id: string | null }> {
  try {
    const res = await fetch(`${API_BASE}/session/${sessionId}`);
    if (!res.ok) return { drafts: [], active_draft_id: null };
    const data = await res.json();
    return {
      drafts: (data.drafts ?? []) as DraftInfo[],
      active_draft_id: data.active_draft_id ?? null,
    };
  } catch {
    return { drafts: [], active_draft_id: null };
  }
}

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
// Itinerary panel state shape
// ---------------------------------------------------------------------------

interface ItineraryPanelState {
  open: boolean;
  loading: boolean;
  cruiseId: string;
  cruiseName: string;
  nights: number;
  isCruisetour: boolean;
  datesLine?: string;
  ship?: string;
  days: ItineraryDay[];
}

const PANEL_CLOSED: ItineraryPanelState = {
  open: false,
  loading: false,
  cruiseId: "",
  cruiseName: "",
  nights: 0,
  isCruisetour: false,
  days: [],
};

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

export default function ChatShellPage() {
  const [messages, setMessages] = useState<TranscriptMessage[]>([]);
  const [chips, setChips] = useState<string[]>([]);
  const [streaming, setStreaming] = useState(false);
  const [panel, setPanel] = useState<ItineraryPanelState>(PANEL_CLOSED);
  const sessionIdRef = useRef<string>("");
  const [drafts, setDrafts] = useState<DraftInfo[]>([]);
  const [activeDraftId, setActiveDraftId] = useState<string | null>(null);

  // Hydrate transcript from sessionStorage on mount
  useEffect(() => {
    sessionIdRef.current = getSessionId();
    const saved = loadTranscript();
    if (saved) {
      setMessages(saved.messages);
      const lastAssistant = [...saved.messages].reverse().find((m) => m.role === "assistant");
      if (lastAssistant?.chips) setChips(lastAssistant.chips);
    }

    // Hydrate drafts from GET /session (backend source of truth)
    // Also try sessionStorage as fallback for immediate render
    const savedDraftsRaw = sessionStorage.getItem("compass_drafts");
    if (savedDraftsRaw) {
      try {
        const savedDrafts = JSON.parse(savedDraftsRaw) as { drafts: DraftInfo[]; activeDraftId: string | null };
        setDrafts(savedDrafts.drafts);
        setActiveDraftId(savedDrafts.activeDraftId);
      } catch { /* ignore */ }
    }
    // Then fetch from backend (authoritative)
    fetchSession(sessionIdRef.current).then(({ drafts: d, active_draft_id }) => {
      setDrafts(d);
      setActiveDraftId(active_draft_id);
      // Mirror to sessionStorage for refresh survival
      sessionStorage.setItem("compass_drafts", JSON.stringify({ drafts: d, activeDraftId: active_draft_id }));
    });
  }, []);

  // Persist transcript whenever messages change
  useEffect(() => {
    if (messages.length > 0) {
      saveTranscript({ messages });
    }
  }, [messages]);

  // ---------------------------------------------------------------------------
  // Core send message
  // ---------------------------------------------------------------------------

  const sendMessage = useCallback(
    async (text: string) => {
      if (streaming) return;

      const userMsg: TranscriptMessage = {
        id: newMessageId(),
        role: "user",
        text,
      };

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
          (delta: string) => {
            setMessages((prev) =>
              prev.map((m) =>
                m.id === assistantId
                  ? { ...m, text: m.text + delta }
                  : m
              )
            );
          },
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

  // ---------------------------------------------------------------------------
  // Chip click
  // ---------------------------------------------------------------------------

  const handleChipClick = useCallback(
    (chip: string) => {
      sendMessage(chip);
    },
    [sendMessage]
  );

  // ---------------------------------------------------------------------------
  // Refresh drafts from backend
  // ---------------------------------------------------------------------------

  const refreshDrafts = useCallback(async () => {
    const { drafts: d, active_draft_id } = await fetchSession(sessionIdRef.current);
    setDrafts(d);
    setActiveDraftId(active_draft_id);
    sessionStorage.setItem("compass_drafts", JSON.stringify({ drafts: d, activeDraftId: active_draft_id }));
  }, []);

  // ---------------------------------------------------------------------------
  // Select cruise → create_draft action
  // Merges returned components/chips into a new synthetic assistant message
  // so tracker_update stub renders in the transcript.
  // ---------------------------------------------------------------------------

  const handleSelect = useCallback(
    async (cruiseId: string) => {
      try {
        const response = await postAction("create_draft", sessionIdRef.current, { cruise_id: cruiseId });

        // Merge components + chips as a synthetic assistant message
        if (response.components && response.components.length > 0) {
          const syntheticId = newMessageId();
          const syntheticMsg: TranscriptMessage = {
            id: syntheticId,
            role: "assistant",
            text: `Draft created for cruise ${cruiseId}.`,
            streaming: false,
            components: response.components,
            chips: response.chips ?? [],
          };
          setMessages((prev) => [...prev, syntheticMsg]);
          if (response.chips && response.chips.length > 0) {
            setChips(response.chips);
          }
          // Refresh draft rail from backend
          await refreshDrafts();
        }
      } catch (err) {
        console.error("create_draft failed:", err);
      }
    },
    [refreshDrafts]
  );

  // ---------------------------------------------------------------------------
  // Set active draft
  // ---------------------------------------------------------------------------

  const handleSetActiveDraft = useCallback(
    async (draftId: string) => {
      try {
        await postAction("set_active_draft", sessionIdRef.current, { draft_id: draftId });
        await refreshDrafts();
      } catch (err) {
        console.error("set_active_draft failed:", err);
      }
    },
    [refreshDrafts]
  );

  // ---------------------------------------------------------------------------
  // Open itinerary panel → get_itinerary action
  // ---------------------------------------------------------------------------

  const handleOpenItinerary = useCallback(
    async (card: unknown) => {
      const c = card as {
        cruise_id: string;
        name: string;
        nights: number;
        is_cruisetour?: boolean;
        ship?: string;
      };

      // Open panel in loading state immediately
      setPanel({
        open: true,
        loading: true,
        cruiseId: c.cruise_id,
        cruiseName: c.name,
        nights: c.nights ?? 0,
        isCruisetour: c.is_cruisetour ?? false,
        ship: c.ship,
        datesLine: undefined,
        days: [],
      });

      try {
        const response = await postAction("get_itinerary", sessionIdRef.current, {
          cruise_id: c.cruise_id,
        });

        const result = response.result as {
          days?: ItineraryDay[];
          cruise_id?: string;
          day_count?: number;
        };

        setPanel((prev) => ({
          ...prev,
          loading: false,
          days: (result.days ?? []) as ItineraryDay[],
        }));
      } catch (err) {
        console.error("get_itinerary failed:", err);
        setPanel((prev) => ({ ...prev, loading: false }));
      }
    },
    []
  );

  // ---------------------------------------------------------------------------
  // Close itinerary panel
  // ---------------------------------------------------------------------------

  const handleClosePanel = useCallback(() => {
    setPanel(PANEL_CLOSED);
  }, []);

  // ---------------------------------------------------------------------------
  // Set fare → postAction('set_fare', ...) + update transcript + refreshDrafts
  // ---------------------------------------------------------------------------

  const handleSetFare = useCallback(
    async (args: { draft_id: string; package: string }) => {
      try {
        const response = await postAction("set_fare", sessionIdRef.current, args);
        if (response.components && response.components.length > 0) {
          const syntheticId = newMessageId();
          const syntheticMsg: TranscriptMessage = {
            id: syntheticId,
            role: "assistant",
            text: `Fare package updated.`,
            streaming: false,
            components: response.components,
            chips: response.chips ?? [],
          };
          setMessages((prev) => [...prev, syntheticMsg]);
          if (response.chips && response.chips.length > 0) {
            setChips(response.chips);
          }
          await refreshDrafts();
        }
      } catch (err) {
        console.error("set_fare failed:", err);
      }
    },
    [refreshDrafts]
  );

  // ---------------------------------------------------------------------------
  // Set stateroom → postAction('set_stateroom', ...) + update transcript + refreshDrafts
  // Returns { total_formatted } for StateroomPicker live total update
  // ---------------------------------------------------------------------------

  const handleSetStateroom = useCallback(
    async (args: { draft_id: string; category: string; location: string }): Promise<{ total_formatted?: string } | undefined> => {
      try {
        const response = await postAction("set_stateroom", sessionIdRef.current, args);
        if (response.components && response.components.length > 0) {
          const syntheticId = newMessageId();
          const syntheticMsg: TranscriptMessage = {
            id: syntheticId,
            role: "assistant",
            text: `Stateroom updated.`,
            streaming: false,
            components: response.components,
            chips: response.chips ?? [],
          };
          setMessages((prev) => [...prev, syntheticMsg]);
          if (response.chips && response.chips.length > 0) {
            setChips(response.chips);
          }
          await refreshDrafts();
          // Return total_formatted for live total update in StateroomPicker
          const tracker = response.components.find(c => c.type === "tracker_update");
          return { total_formatted: tracker?.total_formatted as string | undefined };
        }
      } catch (err) {
        console.error("set_stateroom failed:", err);
      }
      return undefined;
    },
    [refreshDrafts]
  );

  // ---------------------------------------------------------------------------
  // Itinerary Q&A — scoped to the open cruise (P8 D2).
  // The ItineraryPanel handles the request itself (local postChat) and renders
  // the answer INSIDE the panel, keeping the panel open. The scoped message is
  // intentionally NOT forwarded to sendMessage, so it never enters the main
  // transcript. This handler is a no-op notification hook.
  // ---------------------------------------------------------------------------

  const handleItineraryAsk = useCallback((_message: string) => {
    // Intentionally does nothing: panel renders the answer locally.
  }, []);

  // ---------------------------------------------------------------------------
  // Registry handlers (stable reference via useCallback)
  // ---------------------------------------------------------------------------

  const registryHandlers: RegistryHandlers = {
    onSelect: handleSelect,
    onOpenItinerary: handleOpenItinerary,
    onSetFare: handleSetFare,
    onSetStateroom: handleSetStateroom,
  };

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
                registryHandlers={registryHandlers}
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
        <DraftRail
          drafts={drafts}
          activeDraftId={activeDraftId}
          onSetActive={handleSetActiveDraft}
        />
      </div>

      {/* ── Itinerary slide-over ── */}
      {panel.open && (
        <ItineraryPanel
          cruiseId={panel.cruiseId}
          cruiseName={panel.cruiseName}
          nights={panel.nights}
          isCruisetour={panel.isCruisetour}
          datesLine={panel.datesLine}
          ship={panel.ship}
          days={panel.days}
          loading={panel.loading}
          sessionId={sessionIdRef.current}
          onClose={handleClosePanel}
          onAsk={handleItineraryAsk}
        />
      )}
    </div>
  );
}
