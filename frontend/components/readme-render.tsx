"use client";

import DOMPurify from "isomorphic-dompurify";
import { useMemo } from "react";

interface ReadmeRenderProps {
  html: string;
}

export function ReadmeRender({ html }: ReadmeRenderProps) {
  const clean = useMemo(() => DOMPurify.sanitize(html), [html]);
  return (
    <div
      className="prose"
      dangerouslySetInnerHTML={{ __html: clean }}
    />
  );
}
