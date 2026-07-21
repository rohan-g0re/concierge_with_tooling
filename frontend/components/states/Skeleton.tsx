"use client";
import React from "react";

interface SkeletonProps {
  height?: number | string;
  width?: number | string;
  borderRadius?: number | string;
  className?: string;
}

export function Skeleton({ height = 80, width = "100%", borderRadius = 12, className }: SkeletonProps) {
  return (
    <div
      className={className}
      style={{
        height,
        width,
        borderRadius,
        background: "linear-gradient(90deg, #e8edf2 0%, #f4f6f8 50%, #e8edf2 100%)",
        backgroundSize: "200% 100%",
        animation: "shimmer 1.4s ease-in-out infinite",
      }}
    />
  );
}

export function SkeletonCardRow() {
  return (
    <div className="mt-3" style={{ display: "flex", flexDirection: "column", gap: 12 }}>
      <style>{`
        @keyframes shimmer {
          0% { background-position: -200% 0; }
          100% { background-position: 200% 0; }
        }
      `}</style>
      {[0, 1, 2].map((i) => (
        <div
          key={i}
          style={{
            background: "#fff",
            borderRadius: 16,
            border: "1px solid rgba(12,35,64,.10)",
            padding: "16px",
            display: "flex",
            gap: 14,
            alignItems: "center",
          }}
        >
          <Skeleton height={72} width={100} borderRadius={10} />
          <div style={{ flex: 1, display: "flex", flexDirection: "column", gap: 8 }}>
            <Skeleton height={16} width="60%" borderRadius={6} />
            <Skeleton height={13} width="40%" borderRadius={6} />
            <Skeleton height={13} width="30%" borderRadius={6} />
          </div>
          <Skeleton height={34} width={90} borderRadius={999} />
        </div>
      ))}
    </div>
  );
}
