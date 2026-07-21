/**
 * Compass session management — per-tab sessionStorage persistence.
 *
 * Each browser tab gets its own session ID (crypto.randomUUID persisted in
 * sessionStorage). Opening a new tab = new session. Page reload within the
 * same tab = same session with transcript restored.
 */

import type { ComponentDescriptor } from "./api";

const SESSION_ID_KEY = "compass_session_id";
const TRANSCRIPT_KEY = "compass_transcript";

export type MessageRole = "user" | "assistant";

export type TranscriptMessage = {
  id: string;
  role: MessageRole;
  text: string;
  /** Streaming: text accumulates; false until streaming ends */
  streaming?: boolean;
  components?: ComponentDescriptor[];
  chips?: string[];
};

export type Transcript = {
  messages: TranscriptMessage[];
};

/**
 * Get (or create) the session ID for this tab.
 * Uses sessionStorage so each tab has its own isolated session.
 */
export function getSessionId(): string {
  if (typeof window === "undefined") return "ssr-placeholder";

  let id = sessionStorage.getItem(SESSION_ID_KEY);
  if (!id) {
    id = crypto.randomUUID();
    sessionStorage.setItem(SESSION_ID_KEY, id);
  }
  return id;
}

/**
 * Persist the transcript to sessionStorage.
 * Replaces the entire transcript (cheap — transcripts are small).
 */
export function saveTranscript(transcript: Transcript): void {
  if (typeof window === "undefined") return;
  try {
    sessionStorage.setItem(TRANSCRIPT_KEY, JSON.stringify(transcript));
  } catch {
    // sessionStorage quota exceeded — fail silently
  }
}

/**
 * Load the transcript from sessionStorage.
 * Returns null if none exists (fresh tab).
 */
export function loadTranscript(): Transcript | null {
  if (typeof window === "undefined") return null;
  const raw = sessionStorage.getItem(TRANSCRIPT_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as Transcript;
  } catch {
    return null;
  }
}

/** Generate a unique message ID. */
export function newMessageId(): string {
  return crypto.randomUUID();
}
