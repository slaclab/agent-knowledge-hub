"use client";

import DOMPurify from "isomorphic-dompurify";
import { useMemo } from "react";

interface ReadmeRenderProps {
  html: string;
}

export function ReadmeRender({ html }: ReadmeRenderProps) {
  const clean = useMemo(
    () =>
      DOMPurify.sanitize(html, {
        FORBID_TAGS: ["style", "link"],
        FORBID_ATTR: ["style"],
      }),
    [html],
  );
  return (
    <div
      className="prose"
      dangerouslySetInnerHTML={{ __html: clean }}
    />
  );
}
