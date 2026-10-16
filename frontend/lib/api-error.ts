/** The text to show for a failed API response. FastAPI sends `detail` as a string for HTTP errors
 * it raises, and as a list of `{msg}` objects for a request that fails validation (422). */
export function errorMessage(body: unknown, status: number): string {
  const detail = (body as { detail?: unknown } | null)?.detail;
  if (typeof detail === "string" && detail) return detail;
  if (Array.isArray(detail)) {
    const messages = detail
      .map((d) => (d as { msg?: unknown })?.msg)
      .filter((m): m is string => typeof m === "string" && m.length > 0)
      .map((m) => m.replace(/^Value error, /, ""));
    if (messages.length) return messages.join("; ");
  }
  return `HTTP ${status}`;
}
