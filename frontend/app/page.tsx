/**
 * P0 placeholder — Chat Shell root route.
 *
 * Renders the Meridian Line top bar per frame 1a/1b of the design:
 *   - Left:  "MERIDIAN LINE" wordmark (Playfair, letter-spaced, gold)
 *             + "COMPASS · CRUISE CONCIERGE" subtitle
 *   - Right: "Exit AI Assistant" | "Start New Chat" nav links
 *
 * Background: seaMist (#E9ECEF) page, chatBg (#F4F6F8) chat column.
 * Full Chat Shell wired in P7.
 */
export default function ChatShellPage() {
  return (
    <div className="min-h-screen bg-seaMist flex flex-col">
      {/* ── Top bar ── */}
      <header
        className="w-full flex items-center justify-between px-6 py-4"
        style={{ backgroundColor: "#0C2340" }}
      >
        {/* Brand identity */}
        <div className="flex flex-col leading-tight">
          <span
            className="font-display font-semibold tracking-widest2 uppercase"
            style={{ color: "#C8A45C", fontSize: "1.05rem", letterSpacing: "0.2em" }}
          >
            MERIDIAN LINE
          </span>
          <span
            className="font-sans tracking-widest uppercase"
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
          >
            Start New Chat
          </button>
        </nav>
      </header>

      {/* ── Chat column placeholder ── */}
      <main className="flex-1 flex justify-center">
        <div
          className="w-full max-w-2xl flex flex-col items-center justify-center px-6 py-24 gap-4"
          style={{ backgroundColor: "#F4F6F8" }}
        >
          <p
            className="font-display text-3xl font-medium text-center"
            style={{ color: "#0C2340" }}
          >
            Good afternoon.
          </p>
          <p
            className="font-sans text-base text-center"
            style={{ color: "#5A6B7E" }}
          >
            Where would you like to sail? I can help you search, compare, and
            build your cruise — step by step.
          </p>
        </div>
      </main>
    </div>
  );
}
