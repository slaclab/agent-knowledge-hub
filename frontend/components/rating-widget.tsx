"use client";

import { useState, useEffect, useCallback } from "react";
import { useAuth } from "@/lib/auth";
import { rateSkill, getSkill } from "@/lib/api";
import { StarRating } from "@/components/star-rating";

interface RatingWidgetProps {
  slug: string;
  initialAvgRating: number;
  initialRatingCount: number;
}

export function RatingWidget({ slug, initialAvgRating, initialRatingCount }: RatingWidgetProps) {
  const { user, loading } = useAuth();
  const [avgRating, setAvgRating] = useState(initialAvgRating);
  const [ratingCount, setRatingCount] = useState(initialRatingCount);
  const [myRating, setMyRating] = useState<number | null>(null);
  const [myRatingLoading, setMyRatingLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Fetch user's prior rating on mount once auth resolves
  useEffect(() => {
    if (!user) return;
    setMyRatingLoading(true);
    getSkill(slug, false).then(({ skill }) => {
      if (skill?.my_rating != null) setMyRating(skill.my_rating);
      setMyRatingLoading(false);
    });
  }, [slug, user]);

  const handleRate = useCallback(
    async (value: number) => {
      setError(null);
      // Optimistic: pre-fill picker with clicked value
      const prevMyRating = myRating;
      const prevAvg = avgRating;
      const prevCount = ratingCount;
      setMyRating(value);

      const { data, error: err } = await rateSkill(slug, value);
      if (err || !data) {
        setMyRating(prevMyRating);
        setAvgRating(prevAvg);
        setRatingCount(prevCount);
        setError("Failed to submit rating. Please try again.");
        return;
      }
      setAvgRating(data.avg_rating);
      setRatingCount(data.rating_count);
      setMyRating(data.my_rating);
    },
    [slug, myRating, avgRating, ratingCount],
  );

  // While auth is still resolving, show read-only without sign-in prompt
  if (loading) {
    return <StarRating value={avgRating} count={ratingCount} />;
  }

  if (!user) {
    return (
      <div className="space-y-1">
        <StarRating value={avgRating} count={ratingCount} />
        <p
          className="text-xs text-muted-foreground cursor-default"
          title="Authentication required to rate. Refresh if your session expired."
        >
          Sign in to rate.
        </p>
      </div>
    );
  }

  // While my_rating is loading, pre-fill picker with avgRating to avoid empty jump
  const pickerValue = myRatingLoading ? Math.round(initialAvgRating) || 0 : (myRating ?? 0);

  return (
    <div className="space-y-1">
      <StarRating value={pickerValue} count={ratingCount} onRate={handleRate} />
      {error && <p className="text-xs text-destructive">{error}</p>}
    </div>
  );
}
