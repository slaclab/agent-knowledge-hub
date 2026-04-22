"use client";

import { useState } from "react";
import { cn } from "@/lib/utils";
import { Star } from "lucide-react";

interface StarRatingProps {
  value: number;
  count?: number;
  readonly?: boolean;
  onRate?: (value: number) => void;
  className?: string;
}

export function StarRating({ value, count, readonly = false, onRate, className }: StarRatingProps) {
  const [hovered, setHovered] = useState<number | null>(null);
  const stars = Array.from({ length: 5 }, (_, i) => i + 1);
  const interactive = !!onRate;
  const displayValue = hovered ?? value;

  return (
    <span className={cn("inline-flex items-center gap-1", className)}>
      <span className="flex items-center">
        {stars.map((star) =>
          interactive ? (
            <button
              key={star}
              type="button"
              aria-label={`Rate ${star} out of 5 stars`}
              onClick={() => onRate(star)}
              onMouseEnter={() => setHovered(star)}
              onMouseLeave={() => setHovered(null)}
              className="p-0 border-0 bg-transparent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            >
              <Star
                className={cn(
                  "h-5 w-5 cursor-pointer transition-colors",
                  star <= Math.round(displayValue)
                    ? "fill-yellow-400 text-yellow-400"
                    : "fill-muted text-muted-foreground",
                )}
              />
            </button>
          ) : (
            <Star
              key={star}
              className={cn(
                "h-3.5 w-3.5",
                star <= Math.round(value)
                  ? "fill-yellow-400 text-yellow-400"
                  : "fill-muted text-muted-foreground",
                readonly && "cursor-not-allowed opacity-50",
              )}
            />
          ),
        )}
      </span>
      {count !== undefined && count > 0 && (
        <span className="text-xs text-muted-foreground" aria-live="polite">
          {value.toFixed(1)} ({count})
        </span>
      )}
      {count === 0 && <span className="text-xs text-muted-foreground">No ratings</span>}
    </span>
  );
}
