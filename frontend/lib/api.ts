/**
 * Compass API client — SSE streaming chat + action bridge.
 */

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export type ComponentDescriptor = {
  type: string;
  [key: string]: unknown;
};

export type TerminalPayload = {
  components: ComponentDescriptor[];
  chips: string[];
};

/**
 * Stream a chat turn via SSE fetch.
 * Parses `event:` / `data:` SSE frames from the ReadableStream.
 *
 * @param sessionId  - session identifier
 * @param message    - user message text
 * @param onDelta    - called with each text delta string as it arrives
 * @param onTerminal - called once with the terminal {components, chips} payload
 */
export async function postChat(
  sessionId: string,
  message: string,
  onDelta: (delta: string) => void,
  onTerminal: (payload: TerminalPayload) => void
): Promise<void> {
  const res = await fetch(`${API_BASE}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session_id: sessionId, message }),
  });

  if (!res.ok) {
    throw new Error(`Chat request failed: ${res.status} ${res.statusText}`);
  }

  const reader = res.body?.getReader();
  if (!reader) throw new Error("No response body");

  const decoder = new TextDecoder();
  let buffer = "";

  // SSE frame parser state
  let currentEvent = "";
  let currentData = "";

  function flushEvent() {
    if (!currentData) return;
    const data = currentData.trim();
    const event = currentEvent || "message";

    try {
      const parsed = JSON.parse(data);
      if (event === "text_delta" && typeof parsed.delta === "string") {
        onDelta(parsed.delta);
      } else if (event === "components") {
        onTerminal({
          components: parsed.components ?? [],
          chips: parsed.chips ?? [],
        });
      }
    } catch {
      // malformed JSON — skip
    }

    currentEvent = "";
    currentData = "";
  }

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });

    // Process complete lines
    const lines = buffer.split("\n");
    // Keep last incomplete line in buffer
    buffer = lines.pop() ?? "";

    for (const line of lines) {
      const trimmed = line.trimEnd();
      if (trimmed === "") {
        // Blank line = event boundary
        flushEvent();
      } else if (trimmed.startsWith("event:")) {
        currentEvent = trimmed.slice("event:".length).trim();
      } else if (trimmed.startsWith("data:")) {
        currentData = trimmed.slice("data:".length).trim();
      }
      // Ignore comment lines (starting with ':')
    }
  }

  // Flush any remaining event
  if (currentData) flushEvent();
}

/**
 * Execute a tool action (tile tap / direct action).
 */
export async function postAction(
  tool: string,
  sessionId: string,
  args: Record<string, unknown>
): Promise<{ result: unknown; components: ComponentDescriptor[]; chips: string[] }> {
  const res = await fetch(`${API_BASE}/action/${tool}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session_id: sessionId, args }),
  });

  if (!res.ok) {
    throw new Error(`Action request failed: ${res.status} ${res.statusText}`);
  }

  return res.json();
}
