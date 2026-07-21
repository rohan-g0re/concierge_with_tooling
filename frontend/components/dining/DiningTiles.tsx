"use client";
import React, { useState } from "react";
import type { ComponentDescriptor } from "@/lib/api";
import type { RegistryHandlers } from "@/lib/componentRegistry";

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

export function DiningTiles({
  descriptor,
  handlers,
}: {
  descriptor: ComponentDescriptor;
  handlers?: RegistryHandlers;
}) {
  const draftId = descriptor.draft_id as string | undefined;
  const venues = (descriptor.venues as DiningVenue[]) ?? [];

  // Track which venue has an open popover
  const [openPopover, setOpenPopover] = useState<string | null>(null);
  // Track selected night per venue (for the popover)
  const [selectedNight, setSelectedNight] = useState<Record<string, number | null>>({});
  // Track error messages per venue
  const [errors, setErrors] = useState<Record<string, string>>({});
  // Track reserved state per venue: venue_id → { night, time }
  const [reserved, setReserved] = useState<Record<string, { night: number; time: string }>>({});
  // Loading state per venue
  const [loading, setLoading] = useState<Record<string, boolean>>({});

  const handleReserveClick = (venueId: string) => {
    setOpenPopover(venueId);
    setErrors((prev) => ({ ...prev, [venueId]: "" }));
  };

  const handleChangeClick = (venueId: string) => {
    // Remove reserved state and re-open popover
    setReserved((prev) => {
      const next = { ...prev };
      delete next[venueId];
      return next;
    });
    setOpenPopover(venueId);
    setSelectedNight((prev) => ({ ...prev, [venueId]: null }));
    setErrors((prev) => ({ ...prev, [venueId]: "" }));
  };

  const handleNightSelect = (venueId: string, night: number, status: string) => {
    if (status === "sold_out") return;
    setSelectedNight((prev) => ({ ...prev, [venueId]: night }));
  };

  const handleConfirm = async (venueId: string) => {
    const night = selectedNight[venueId];
    if (!night || !draftId) return;

    setLoading((prev) => ({ ...prev, [venueId]: true }));
    setErrors((prev) => ({ ...prev, [venueId]: "" }));

    try {
      const res = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"}/action/reserve_dining`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            session_id: typeof window !== "undefined"
              ? sessionStorage.getItem("compass_session_id") ?? ""
              : "",
            args: { draft_id: draftId, venue_id: venueId, night },
          }),
        }
      );
      const data = await res.json();

      if (data.result?.error) {
        const errCode = data.result.error;
        let msg = "Unable to reserve this night.";
        if (errCode === "sold_out") msg = "This night is now fully reserved. Please choose another.";
        else if (errCode === "double_book") msg = "You have already reserved this venue for that night.";
        setErrors((prev) => ({ ...prev, [venueId]: msg }));
      } else {
        // Success - flip tile to reserved state
        setReserved((prev) => ({ ...prev, [venueId]: { night, time: "7:30 PM" } }));
        setOpenPopover(null);
        setSelectedNight((prev) => ({ ...prev, [venueId]: null }));
      }
    } catch {
      setErrors((prev) => ({ ...prev, [venueId]: "Network error. Please try again." }));
    } finally {
      setLoading((prev) => ({ ...prev, [venueId]: false }));
    }
  };

  const isMainDining = (venue: DiningVenue) =>
    venue.price_per_guest === 0 || venue.venue_id === "main_dining";

  return (
    <div
      className="mt-3"
      style={{
        display: "grid",
        gridTemplateColumns: "1fr 1fr",
        gap: "16px",
        paddingBottom: "48px", // space for popover overflow
      }}
    >
      {venues.map((venue) => {
        const isOpen = openPopover === venue.venue_id;
        const reservedInfo = reserved[venue.venue_id];
        const isReserved = !!reservedInfo;
        const currentSelectedNight = selectedNight[venue.venue_id] ?? null;
        const errMsg = errors[venue.venue_id] ?? "";
        const isLoading = loading[venue.venue_id] ?? false;
        const isMain = isMainDining(venue);

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
            {/* Photo placeholder */}
            <div
              style={{
                height: "96px",
                background: "repeating-linear-gradient(135deg,#DCE4EC 0 10px,#E6EBF1 10px 20px)",
                borderRadius: "12px 12px 0 0",
                position: "relative",
                overflow: "hidden",
              }}
            >
              <div
                style={{
                  position: "absolute",
                  left: "10px",
                  bottom: "8px",
                  fontFamily: "ui-monospace, Menlo, monospace",
                  fontSize: "9.5px",
                  color: "#5A6B7E",
                }}
              >
                {venue.venue_id.replace(/_/g, " ")}
              </div>
            </div>

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
                <button
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
              ) : isReserved ? (
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
                    ✓ Reserved · Night {reservedInfo.night} · {reservedInfo.time}
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
                  Choose a night
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
                    const isAlreadyReserved = n.status === "reserved";
                    const isChosen = currentSelectedNight === n.night;
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
                      border = "1px solid #C8A45C";
                      cursor = "default";
                    } else if (isChosen) {
                      bg = "#C8A45C";
                      color = "#fff";
                      border = "2px solid #C8A45C";
                    }

                    return (
                      <div
                        key={n.night}
                        title={isSoldOut ? "Fully reserved this night" : isAlreadyReserved ? "Already reserved" : `Night ${n.night}`}
                        onClick={() => !isDisabled && handleNightSelect(venue.venue_id, n.night, n.status)}
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

                {/* Selected night label */}
                {currentSelectedNight && (
                  <p style={{ fontSize: "12.5px", color: "#5A6B7E", marginBottom: "10px" }}>
                    Night {currentSelectedNight} · 7:30 PM
                  </p>
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
                    disabled={!currentSelectedNight || isLoading}
                    style={{
                      flex: 2,
                      padding: "9px 0",
                      borderRadius: "8px",
                      background: currentSelectedNight && !isLoading ? "#C8A45C" : "rgba(200,164,92,.4)",
                      border: "none",
                      color: "#fff",
                      fontSize: "13px",
                      fontWeight: 700,
                      cursor: currentSelectedNight && !isLoading ? "pointer" : "not-allowed",
                    }}
                  >
                    {isLoading ? "Reserving…" : "Confirm"}
                  </button>
                </div>
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
