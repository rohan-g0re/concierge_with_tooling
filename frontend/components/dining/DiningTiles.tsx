"use client";
import React, { useState } from "react";
import type { ComponentDescriptor } from "@/lib/api";
import type { RegistryHandlers } from "@/lib/componentRegistry";
import { renderComponent } from "@/lib/componentRegistry";
import { ErrorState } from "@/components/states/ErrorState";

interface NightInfo {
  night: number;
  status: "available" | "reserved" | "sold_out";
}

interface DiningVenue {
  venue_id: string;
  name: string;
  cuisine: string[];
  price_per_guest: number;
  price_formatted: string;
  nights: NightInfo[];
}

const TIME_OPTIONS = [
  { label: "Early", display: "5:30 PM", value: "early" as const },
  { label: "Main", display: "7:30 PM", value: "main" as const },
  { label: "Late", display: "9:00 PM", value: "late" as const },
];

export function DiningTiles({
  descriptor,
  handlers,
}: {
  descriptor: ComponentDescriptor;
  handlers?: RegistryHandlers;
}) {
  const draftId = descriptor.draft_id as string | undefined;
  const venues = (descriptor.venues as DiningVenue[]) ?? [];

  const [openPopover, setOpenPopover] = useState<string | null>(null);
  // Multi-select: array of selected nights per venue
  const [selectedNight, setSelectedNight] = useState<Record<string, number[]>>({});
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [netError, setNetError] = useState<Record<string, boolean>>({});
  // Reserved nights per venue: array of night numbers
  const [reserved, setReserved] = useState<Record<string, number[]>>({});
  const [loading, setLoading] = useState<Record<string, boolean>>({});

  // Time picker state
  const [timePickerOpen, setTimePickerOpen] = useState<string | null>(null);
  const [preferredTime, setPreferredTime] = useState<Record<string, string>>({});
  const [timeLoading, setTimeLoading] = useState<Record<string, boolean>>({});
  const [timeError, setTimeError] = useState<Record<string, string>>({});
  const [diningImgFailed, setDiningImgFailed] = React.useState<Record<string, boolean>>({});

  const [handoffComponent, setHandoffComponent] = React.useState<import("@/lib/api").ComponentDescriptor | null>(null);
  const [handoffLoading, setHandoffLoading] = React.useState(false);

  const sessionId =
    typeof window !== "undefined"
      ? sessionStorage.getItem("compass_session_id") ?? ""
      : "";

  const handleReserveClick = (venueId: string) => {
    setOpenPopover(venueId);
    setErrors((prev) => ({ ...prev, [venueId]: "" }));
  };

  const handleChangeClick = (venueId: string) => {
    setReserved((prev) => {
      const next = { ...prev };
      delete next[venueId];
      return next;
    });
    setOpenPopover(venueId);
    setSelectedNight((prev) => ({ ...prev, [venueId]: [] }));
    setErrors((prev) => ({ ...prev, [venueId]: "" }));
  };

  const handleNightToggle = (venueId: string, night: number, status: string) => {
    if (status === "sold_out") return;
    setSelectedNight((prev) => {
      const current = prev[venueId] ?? [];
      const idx = current.indexOf(night);
      if (idx === -1) {
        return { ...prev, [venueId]: [...current, night] };
      } else {
        return { ...prev, [venueId]: current.filter((n) => n !== night) };
      }
    });
  };

  const handleConfirm = async (venueId: string) => {
    const nights = selectedNight[venueId] ?? [];
    if (nights.length === 0 || !draftId) return;

    setLoading((prev) => ({ ...prev, [venueId]: true }));
    setErrors((prev) => ({ ...prev, [venueId]: "" }));
    setNetError((prev) => ({ ...prev, [venueId]: false }));

    const succeededNights: number[] = [];
    let lastError = "";
    let hasNetError = false;

    for (const night of nights) {
      try {
        const res = await fetch(
          `${process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"}/action/reserve_dining`,
          {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              session_id: sessionId,
              args: { draft_id: draftId, venue_id: venueId, night },
            }),
          }
        );
        if (!res.ok) {
          hasNetError = true;
          continue;
        }
        const data = await res.json();

        if (data.result?.error) {
          const errCode = data.result.error;
          if (errCode === "sold_out") {
            lastError = `Night ${night} is now fully reserved. Please choose another.`;
          } else if (errCode === "double_book") {
            lastError = `Night ${night} is already reserved for this venue.`;
          } else {
            lastError = `Unable to reserve night ${night}.`;
          }
        } else {
          succeededNights.push(night);
          handlers?.onReserveDining?.(data);
        }
      } catch {
        hasNetError = true;
      }
    }

    if (succeededNights.length > 0) {
      setReserved((prev) => {
        const existing = prev[venueId] ?? [];
        const merged = Array.from(new Set([...existing, ...succeededNights]));
        return { ...prev, [venueId]: merged };
      });
      // Clear successfully reserved nights from selection
      setSelectedNight((prev) => {
        const remaining = (prev[venueId] ?? []).filter(
          (n) => !succeededNights.includes(n)
        );
        return { ...prev, [venueId]: remaining };
      });
    }

    if (lastError) {
      setErrors((prev) => ({ ...prev, [venueId]: lastError }));
    }
    if (hasNetError) {
      setNetError((prev) => ({ ...prev, [venueId]: true }));
    }

    // Close popover only if all nights were successfully reserved and no errors
    if (!lastError && !hasNetError && succeededNights.length === nights.length) {
      setOpenPopover(null);
    }

    setLoading((prev) => ({ ...prev, [venueId]: false }));
  };

  const handleSetTime = async (venueId: string, slot: "early" | "main" | "late") => {
    if (!draftId) return;
    setTimeLoading((prev) => ({ ...prev, [venueId]: true }));
    setTimeError((prev) => ({ ...prev, [venueId]: "" }));

    try {
      const res = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"}/action/set_dining_time`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            session_id: sessionId,
            args: { draft_id: draftId, time_slot: slot },
          }),
        }
      );
      if (!res.ok) {
        setTimeError((prev) => ({ ...prev, [venueId]: "Failed to set time. Please try again." }));
        return;
      }
      const option = TIME_OPTIONS.find((o) => o.value === slot);
      setPreferredTime((prev) => ({ ...prev, [venueId]: option?.display ?? "" }));
      setTimePickerOpen(null);
    } catch {
      setTimeError((prev) => ({ ...prev, [venueId]: "Network error. Please try again." }));
    } finally {
      setTimeLoading((prev) => ({ ...prev, [venueId]: false }));
    }
  };

  const handleDoneWithAddons = async () => {
    if (!draftId) return;
    setHandoffLoading(true);
    try {
      const res = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"}/action/handoff_checkout`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            session_id: sessionId,
            args: { draft_id: draftId },
          }),
        }
      );
      if (res.ok) {
        const data = await res.json();
        const components = data.components as import("@/lib/api").ComponentDescriptor[] | undefined;
        const handoff = components?.find((c) => c.type === "handoff");
        if (handoff) setHandoffComponent(handoff);
      }
    } catch {
      // fail silently — button stays available
    } finally {
      setHandoffLoading(false);
    }
  };

  const isMainDining = (venue: DiningVenue) =>
    venue.price_per_guest === 0 || venue.venue_id === "main_dining";

  return (
    <div>
      <div
        className="mt-3"
        style={{
          display: "grid",
          gridTemplateColumns: "1fr 1fr",
          gap: "16px",
          paddingBottom: "16px",
        }}
      >
      {venues.map((venue) => {
        const isOpen = openPopover === venue.venue_id;
        const reservedNights = reserved[venue.venue_id] ?? [];
        const hasReservations = reservedNights.length > 0;
        const currentSelected = selectedNight[venue.venue_id] ?? [];
        const errMsg = errors[venue.venue_id] ?? "";
        const isNetError = netError[venue.venue_id] ?? false;
        const isLoading = loading[venue.venue_id] ?? false;
        const isMain = isMainDining(venue);
        const isTimePickerOpen = timePickerOpen === venue.venue_id;
        const pTime = preferredTime[venue.venue_id];
        const tLoading = timeLoading[venue.venue_id] ?? false;
        const tError = timeError[venue.venue_id] ?? "";

        return (
          <div
            key={venue.venue_id}
            style={{
              position: "relative",
              background: "#fff",
              border: "1px solid rgba(12,35,64,.10)",
              borderRadius: "12px",
              overflow: "visible",
              boxShadow: "0 4px 14px rgba(12,35,64,.06)",
            }}
          >
            {/* Photo */}
            {diningImgFailed[venue.venue_id] ? (
              <div style={{ width: "100%", height: 120, background: "repeating-linear-gradient(135deg,#e5e7eb 0px,#e5e7eb 8px,#f3f4f6 8px,#f3f4f6 16px)", borderRadius: 8, display:"flex", alignItems:"center", justifyContent:"center" }}>
                <span style={{ fontFamily:"monospace", fontSize:11, color:"#9ca3af" }}>{venue.venue_id}</span>
              </div>
            ) : (
              <img
                src={`/images/dining/${venue.venue_id}.jpg`}
                alt={venue.venue_id}
                style={{ width: "100%", height: 120, objectFit: "cover", borderRadius: 8, display: "block" }}
                onError={() => setDiningImgFailed(prev => ({ ...prev, [venue.venue_id]: true }))}
              />
            )}

            {/* Content */}
            <div style={{ padding: "16px 18px 18px" }}>
              {/* Name + price */}
              <div style={{ marginBottom: "8px" }}>
                <span
                  className="font-display"
                  style={{ fontSize: "17px", color: "#0C2340", fontWeight: 600 }}
                >
                  {venue.name}
                </span>
                <span
                  style={{
                    fontSize: "13px",
                    color: "#5A6B7E",
                    marginLeft: "8px",
                    fontVariantNumeric: "tabular-nums",
                  }}
                >
                  {isMain ? "Included" : venue.price_formatted + " per guest"}
                </span>
              </div>

              {/* Cuisine chips */}
              <div style={{ display: "flex", flexWrap: "wrap", gap: "6px", marginBottom: "14px" }}>
                {venue.cuisine.map((tag) => (
                  <span
                    key={tag}
                    style={{
                      fontSize: "11px",
                      fontWeight: 600,
                      color: "#5A6B7E",
                      background: "rgba(12,35,64,.07)",
                      padding: "3px 10px",
                      borderRadius: "999px",
                    }}
                  >
                    {tag}
                  </span>
                ))}
              </div>

              {/* CTA */}
              {isMain ? (
                <div style={{ position: "relative" }}>
                  {pTime ? (
                    <div
                      style={{
                        padding: "10px 14px",
                        borderRadius: "8px",
                        background: "rgba(200,164,92,.14)",
                        border: "1px solid #C8A45C",
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "space-between",
                      }}
                    >
                      <span style={{ fontSize: "13px", color: "#0C2340", fontWeight: 600 }}>
                        Preferred time: {pTime}
                      </span>
                      <button
                        onClick={() => setTimePickerOpen(venue.venue_id)}
                        style={{
                          fontSize: "12px",
                          color: "#B08F44",
                          background: "none",
                          border: "none",
                          cursor: "pointer",
                          fontWeight: 600,
                        }}
                      >
                        Change
                      </button>
                    </div>
                  ) : (
                    <button
                      onClick={() =>
                        setTimePickerOpen(
                          isTimePickerOpen ? null : venue.venue_id
                        )
                      }
                      style={{
                        width: "100%",
                        padding: "10px 0",
                        borderRadius: "8px",
                        border: "1px solid rgba(12,35,64,.25)",
                        background: "transparent",
                        color: "#0C2340",
                        fontSize: "13.5px",
                        fontWeight: 600,
                        cursor: "pointer",
                      }}
                    >
                      Set a preferred time
                    </button>
                  )}

                  {/* Time picker popover */}
                  {isTimePickerOpen && (
                    <div
                      style={{
                        position: "absolute",
                        left: "0",
                        right: "0",
                        bottom: "-8px",
                        transform: "translateY(100%)",
                        zIndex: 10,
                        background: "#fff",
                        border: "1px solid rgba(12,35,64,.14)",
                        borderRadius: "12px",
                        boxShadow: "0 8px 32px rgba(12,35,64,.16)",
                        padding: "16px",
                      }}
                    >
                      <p
                        style={{
                          fontSize: "12px",
                          fontWeight: 700,
                          letterSpacing: ".1em",
                          textTransform: "uppercase",
                          color: "#5A6B7E",
                          marginBottom: "12px",
                        }}
                      >
                        Select seating time
                      </p>
                      <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
                        {TIME_OPTIONS.map((opt) => (
                          <button
                            key={opt.value}
                            disabled={tLoading}
                            onClick={() => handleSetTime(venue.venue_id, opt.value)}
                            style={{
                              padding: "10px 14px",
                              borderRadius: "8px",
                              border: "1px solid rgba(12,35,64,.18)",
                              background: "#fff",
                              color: "#0C2340",
                              fontSize: "13.5px",
                              fontWeight: 600,
                              cursor: tLoading ? "not-allowed" : "pointer",
                              textAlign: "left",
                              display: "flex",
                              justifyContent: "space-between",
                            }}
                          >
                            <span>{opt.label}</span>
                            <span style={{ color: "#5A6B7E", fontWeight: 400 }}>{opt.display}</span>
                          </button>
                        ))}
                      </div>
                      {tError && (
                        <p style={{ fontSize: "12px", color: "#c0392b", marginTop: "8px" }}>
                          {tError}
                        </p>
                      )}
                      <button
                        onClick={() => setTimePickerOpen(null)}
                        style={{
                          marginTop: "10px",
                          width: "100%",
                          padding: "9px 0",
                          borderRadius: "8px",
                          border: "1px solid rgba(12,35,64,.20)",
                          background: "transparent",
                          color: "#5A6B7E",
                          fontSize: "13px",
                          cursor: "pointer",
                        }}
                      >
                        Cancel
                      </button>
                    </div>
                  )}
                </div>
              ) : hasReservations ? (
                <div
                  style={{
                    padding: "10px 14px",
                    borderRadius: "8px",
                    background: "rgba(200,164,92,.14)",
                    border: "1px solid #C8A45C",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                  }}
                >
                  <span style={{ fontSize: "13px", color: "#0C2340", fontWeight: 600 }}>
                    ✓ {reservedNights.length} {reservedNights.length === 1 ? "night" : "nights"} reserved
                  </span>
                  <button
                    onClick={() => handleChangeClick(venue.venue_id)}
                    style={{
                      fontSize: "12px",
                      color: "#B08F44",
                      background: "none",
                      border: "none",
                      cursor: "pointer",
                      fontWeight: 600,
                    }}
                  >
                    Change
                  </button>
                </div>
              ) : (
                <button
                  onClick={() => handleReserveClick(venue.venue_id)}
                  style={{
                    width: "100%",
                    padding: "10px 0",
                    borderRadius: "8px",
                    background: isOpen ? "#B08F44" : "#C8A45C",
                    border: "none",
                    color: "#fff",
                    fontSize: "13.5px",
                    fontWeight: 700,
                    cursor: "pointer",
                  }}
                >
                  Reserve a night
                </button>
              )}

              {/* Inline error */}
              {errMsg && (
                <p style={{ fontSize: "12px", color: "#c0392b", marginTop: "8px" }}>{errMsg}</p>
              )}
            </div>

            {/* Night-grid popover */}
            {isOpen && (
              <div
                style={{
                  position: "absolute",
                  left: "18px",
                  right: "18px",
                  bottom: "-8px",
                  transform: "translateY(100%)",
                  zIndex: 10,
                  background: "#fff",
                  border: "1px solid rgba(12,35,64,.14)",
                  borderRadius: "12px",
                  boxShadow: "0 8px 32px rgba(12,35,64,.16)",
                  padding: "16px",
                }}
              >
                <p
                  style={{
                    fontSize: "12px",
                    fontWeight: 700,
                    letterSpacing: ".1em",
                    textTransform: "uppercase",
                    color: "#5A6B7E",
                    marginBottom: "12px",
                  }}
                >
                  Choose nights
                </p>

                <div
                  style={{
                    display: "grid",
                    gridTemplateColumns: "repeat(6, 1fr)",
                    gap: "7px",
                    marginBottom: "14px",
                  }}
                >
                  {venue.nights.map((n) => {
                    const isSoldOut = n.status === "sold_out";
                    const isAlreadyReserved = reservedNights.includes(n.night);
                    const isChosen = currentSelected.includes(n.night);
                    const isDisabled = isSoldOut || isAlreadyReserved;

                    let bg = "#fff";
                    let color = "#0C2340";
                    let border = "1px solid rgba(12,35,64,.20)";
                    let cursor = "pointer";
                    let opacity = 1;

                    if (isSoldOut) {
                      bg = "rgba(12,35,64,.05)";
                      color = "#B0BEC5";
                      border = "1px solid rgba(12,35,64,.08)";
                      cursor = "not-allowed";
                      opacity = 0.6;
                    } else if (isAlreadyReserved) {
                      bg = "rgba(200,164,92,.12)";
                      color = "#B08F44";
                      border = "2px solid #C8A45C";
                      cursor = "default";
                    } else if (isChosen) {
                      bg = "#C8A45C";
                      color = "#fff";
                      border = "2px solid #C8A45C";
                    }

                    return (
                      <div
                        key={n.night}
                        className="tile-selectable"
                        role="button"
                        tabIndex={isDisabled ? -1 : 0}
                        aria-disabled={isDisabled}
                        aria-pressed={isChosen}
                        aria-label={`Night ${n.night}${isSoldOut ? ", fully reserved" : isAlreadyReserved ? ", already reserved" : ""}`}
                        title={isSoldOut ? "Fully reserved this night" : isAlreadyReserved ? "Already reserved" : `Night ${n.night}`}
                        onClick={() => !isDisabled && handleNightToggle(venue.venue_id, n.night, n.status)}
                        onKeyDown={(e) => {
                          if (!isDisabled && (e.key === "Enter" || e.key === " ")) {
                            e.preventDefault();
                            handleNightToggle(venue.venue_id, n.night, n.status);
                          }
                        }}
                        style={{
                          background: bg,
                          color,
                          border,
                          borderRadius: "6px",
                          padding: "6px 2px",
                          textAlign: "center",
                          fontSize: "12px",
                          fontWeight: isChosen ? 700 : 500,
                          cursor,
                          opacity,
                          userSelect: "none",
                        }}
                      >
                        N{n.night}
                      </div>
                    );
                  })}
                </div>

                {currentSelected.length > 0 && (
                  <p style={{ fontSize: "12.5px", color: "#5A6B7E", marginBottom: "10px" }}>
                    {currentSelected.length} {currentSelected.length === 1 ? "night" : "nights"} selected
                  </p>
                )}

                {isNetError && (
                  <ErrorState onRetry={() => handleConfirm(venue.venue_id)} />
                )}

                <div style={{ display: "flex", gap: "8px" }}>
                  <button
                    onClick={() => setOpenPopover(null)}
                    style={{
                      flex: 1,
                      padding: "9px 0",
                      borderRadius: "8px",
                      border: "1px solid rgba(12,35,64,.20)",
                      background: "transparent",
                      color: "#5A6B7E",
                      fontSize: "13px",
                      cursor: "pointer",
                    }}
                  >
                    Cancel
                  </button>
                  <button
                    onClick={() => handleConfirm(venue.venue_id)}
                    disabled={currentSelected.length === 0 || isLoading}
                    style={{
                      flex: 2,
                      padding: "9px 0",
                      borderRadius: "8px",
                      background: currentSelected.length > 0 && !isLoading ? "#C8A45C" : "rgba(200,164,92,.4)",
                      border: "none",
                      color: "#fff",
                      fontSize: "13px",
                      fontWeight: 700,
                      cursor: currentSelected.length > 0 && !isLoading ? "pointer" : "not-allowed",
                    }}
                  >
                    {isLoading
                      ? "Reserving…"
                      : `Confirm ${currentSelected.length > 0 ? `${currentSelected.length} ` : ""}${currentSelected.length === 1 ? "night" : "nights"}`}
                  </button>
                </div>
              </div>
            )}
          </div>
        );
      })}
      </div>

      {/* Done with add-ons footer */}
      {draftId && (
        <div style={{ paddingTop: "8px", paddingBottom: "32px", textAlign: "center" }}>
          {handoffComponent ? (
            renderComponent(handoffComponent, "handoff-cta")
          ) : (
            <button
              onClick={handleDoneWithAddons}
              disabled={handoffLoading}
              style={{
                background: handoffLoading ? "rgba(200,164,92,0.4)" : "#C8A45C",
                color: "#0C2340",
                border: "none",
                borderRadius: "8px",
                padding: "12px 32px",
                fontSize: "14px",
                fontWeight: 700,
                cursor: handoffLoading ? "not-allowed" : "pointer",
                opacity: handoffLoading ? 0.7 : 1,
              }}
            >
              {handoffLoading ? "Loading…" : "Done with add-ons → Review"}
            </button>
          )}
        </div>
      )}
    </div>
  );
}
