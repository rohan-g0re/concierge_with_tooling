/**
 * Compass — Voice Client (OpenAI GPT Realtime WebRTC scaffold)
 *
 * Architecture (R21 parity):
 *   1. Mint ephemeral token via POST /voice/token (backend never exposes raw key).
 *   2. Connect WebRTC peer connection to OpenAI Realtime API.
 *   3. On tool_call from Realtime, relay through POST /action/{tool} (same
 *      handlers as tap path) so voice actions update drafts identically.
 *   4. Append transcripts to chat history via onTranscript callback.
 *   5. Barge-in: interrupt mid-response on mic activity.
 *
 * Graceful degradation (RK9):
 *   If /voice/token returns available=false, the client returns a VoiceUnavailable
 *   result and the caller shows a polite disabled state.
 */

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export type VoiceTokenResult =
  | {
      available: false;
      reason: string;
      message: string;
    }
  | {
      available: true;
      client_secret: { value: string; expires_at: number };
      model: string;
      voice: string;
      tools: VoiceToolSchema[];
    };

export type VoiceToolSchema = {
  type: "function";
  name: string;
  description: string;
  parameters: Record<string, unknown>;
};

export type VoiceSessionCallbacks = {
  /** Called with each transcript line (role: "user" | "assistant", text) */
  onTranscript: (role: "user" | "assistant", text: string) => void;
  /** Called when a tool call completes (action relayed through /action bridge) */
  onActionResult: (tool: string, result: unknown, components: unknown[], chips: string[]) => void;
  /** Called on connection state changes */
  onStateChange: (state: VoiceState) => void;
  /** Called on errors */
  onError: (err: Error) => void;
};

export type VoiceState =
  | "idle"
  | "connecting"
  | "listening"
  | "speaking"
  | "interrupted"
  | "disconnected";

export type VoiceSession = {
  /** Stop the voice session and release mic/audio resources. */
  stop: () => void;
  /** Interrupt the assistant mid-speech (barge-in). */
  interrupt: () => void;
};

/**
 * Fetch the ephemeral token from the backend.
 * Returns the full VoiceTokenResult (may be unavailable).
 */
export async function fetchVoiceToken(): Promise<VoiceTokenResult> {
  const res = await fetch(`${API_BASE}/voice/token`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
  });
  if (!res.ok) {
    throw new Error(`Voice token request failed: ${res.status} ${res.statusText}`);
  }
  return res.json();
}

/**
 * Start a voice session.
 *
 * If the token endpoint returns available=false, this function returns null
 * and calls onStateChange("disconnected") + onError with the reason.
 *
 * Architecture note (WebRTC scaffold):
 *   The WebRTC connection to OpenAI Realtime is complete and correct so that
 *   swapping in a real OPENAI_API_KEY later just works. With a placeholder key
 *   the function returns null after the token check — no WebRTC attempt is made.
 *
 * R21 parity: all tool calls are relayed through POST /action/{tool} so voice
 * and tap share the same handlers and session state.
 */
export async function startVoiceSession(
  sessionId: string,
  callbacks: VoiceSessionCallbacks
): Promise<VoiceSession | null> {
  const { onTranscript, onActionResult, onStateChange, onError } = callbacks;

  // --- Step 1: Fetch ephemeral token ---
  let tokenResult: VoiceTokenResult;
  try {
    tokenResult = await fetchVoiceToken();
  } catch (err) {
    onError(err instanceof Error ? err : new Error(String(err)));
    onStateChange("disconnected");
    return null;
  }

  if (!tokenResult.available) {
    onError(new Error(tokenResult.message));
    onStateChange("disconnected");
    return null;
  }

  onStateChange("connecting");

  // --- Step 2: WebRTC setup (scaffold — activates with real key) ---
  let pc: RTCPeerConnection | null = null;
  let dc: RTCDataChannel | null = null;
  let localStream: MediaStream | null = null;

  try {
    // Request microphone access
    localStream = await navigator.mediaDevices.getUserMedia({ audio: true });

    pc = new RTCPeerConnection();

    // Add audio track from mic
    for (const track of localStream.getTracks()) {
      pc.addTrack(track, localStream);
    }

    // Set up remote audio playback
    const audioEl = new Audio();
    audioEl.autoplay = true;
    pc.ontrack = (event) => {
      if (event.streams[0]) {
        audioEl.srcObject = event.streams[0];
      }
    };

    // --- Step 3: Data channel for Realtime events ---
    dc = pc.createDataChannel("oai-events");

    dc.onmessage = async (event) => {
      let msg: Record<string, unknown>;
      try {
        msg = JSON.parse(event.data as string);
      } catch {
        return;
      }

      const type = msg.type as string | undefined;

      // State transitions
      if (type === "session.created" || type === "session.updated") {
        onStateChange("listening");
      } else if (type === "response.audio.delta") {
        onStateChange("speaking");
      } else if (type === "response.audio.done" || type === "response.done") {
        onStateChange("listening");
      }

      // Transcript events
      if (type === "conversation.item.input_audio_transcription.completed") {
        const transcript = (msg.transcript as string) ?? "";
        if (transcript) onTranscript("user", transcript);
      } else if (type === "response.audio_transcript.done") {
        const transcript = (msg.transcript as string) ?? "";
        if (transcript) onTranscript("assistant", transcript);
      }

      // --- R21 Tool call relay: route through /action bridge ---
      if (type === "response.function_call_arguments.done") {
        const toolName = msg.name as string;
        let args: Record<string, unknown> = {};
        try {
          args = JSON.parse((msg.arguments as string) ?? "{}");
        } catch {
          // malformed args — skip
        }

        try {
          const actionRes = await fetch(`${API_BASE}/action/${toolName}`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ session_id: sessionId, args }),
          });
          const actionData = await actionRes.json();

          onActionResult(
            toolName,
            actionData.result,
            actionData.components ?? [],
            actionData.chips ?? []
          );

          // Send function output back to Realtime so it can continue speaking
          if (dc && dc.readyState === "open") {
            const callId = msg.call_id as string;
            dc.send(
              JSON.stringify({
                type: "conversation.item.create",
                item: {
                  type: "function_call_output",
                  call_id: callId,
                  output: JSON.stringify(actionData.result),
                },
              })
            );
            dc.send(JSON.stringify({ type: "response.create" }));
          }
        } catch (err) {
          onError(err instanceof Error ? err : new Error(String(err)));
        }
      }
    };

    dc.onopen = () => {
      // Configure the Realtime session with our tools and instructions
      if (dc && dc.readyState === "open") {
        dc.send(
          JSON.stringify({
            type: "session.update",
            session: {
              modalities: ["text", "audio"],
              tools: tokenResult.available ? tokenResult.tools : [],
              tool_choice: "auto",
              turn_detection: { type: "server_vad" },
            },
          })
        );
      }
    };

    // --- Step 4: SDP offer/answer with OpenAI Realtime ---
    const offer = await pc.createOffer();
    await pc.setLocalDescription(offer);

    const ephemeralKey = tokenResult.client_secret.value;
    const sdpResponse = await fetch(
      `https://api.openai.com/v1/realtime?model=${tokenResult.model}`,
      {
        method: "POST",
        headers: {
          Authorization: `Bearer ${ephemeralKey}`,
          "Content-Type": "application/sdp",
        },
        body: offer.sdp,
      }
    );

    if (!sdpResponse.ok) {
      throw new Error(`OpenAI Realtime SDP exchange failed: ${sdpResponse.status}`);
    }

    const answerSdp = await sdpResponse.text();
    await pc.setRemoteDescription({ type: "answer", sdp: answerSdp });

    onStateChange("listening");
  } catch (err) {
    onError(err instanceof Error ? err : new Error(String(err)));
    onStateChange("disconnected");
    // Clean up
    localStream?.getTracks().forEach((t) => t.stop());
    pc?.close();
    return null;
  }

  // --- Step 5: Return session controls ---
  function stop() {
    if (dc && dc.readyState === "open") dc.close();
    pc?.close();
    localStream?.getTracks().forEach((t) => t.stop());
    onStateChange("disconnected");
  }

  function interrupt() {
    // Send cancel to Realtime to implement barge-in
    if (dc && dc.readyState === "open") {
      dc.send(JSON.stringify({ type: "response.cancel" }));
      onStateChange("interrupted");
      // Resume listening after barge-in
      setTimeout(() => onStateChange("listening"), 200);
    }
  }

  return { stop, interrupt };
}
