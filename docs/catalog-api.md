# GET /api/skills — Catalog List API

Full contract for the skill catalog list endpoint.

---

## Request

```
GET /api/skills
```

### Query Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `q` | string | — | Full-text search query (MongoDB `$text`). Exact name/slug matches are boosted to the top of results. |
| `sort` | string | `newest` | Sort order: `newest`, `highest_rated`, `most_rated`, `most_stars` |
| `page` | integer (1–1000) | `1` | Page number for offset-based pagination |
| `page_size` | integer (1–100) | `20` | Results per page |
| `labels` | string | — | Comma-separated label names (AND filter) |
| `visibility` | string | — | Filter by visibility: `public`, `internal`, `all` |
| `forked_from` | string | — | Filter by upstream fork URL |
| `submitted_by` | string | — | Filter by submitter user_id |
| `cursor` | string | — | Opaque keyset cursor (see Cursor Pagination below) |

---

## Response

```json
{
  "items": [ /* SkillListOut objects */ ],
  "total": 1234,
  "page": 3,
  "page_size": 20,
  "pages": 62,
  "next_cursor": "eyJzdiI6ICIyMDI2...",
  "prev_cursor": null
}
```

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `items` | array | Page of skill summaries (see SkillListOut schema) |
| `total` | integer | Total matching skills (cached for 30s on filtered requests; see Count Caching) |
| `page` | integer | Current page number |
| `page_size` | integer | Results per page |
| `pages` | integer | Total number of pages |
| `next_cursor` | string \| null | Opaque keyset cursor for the next page. Null on the last page or when sort ≠ `newest` |
| `prev_cursor` | string \| null | Reserved; currently always null (backward navigation uses `?page=N`) |

---

## Cursor Pagination

For `sort=newest`, the API supports keyset (cursor-based) pagination that avoids O(N) skip scans at high page numbers.

### How it works

1. Fetch any page normally using `?page=N`. The response includes `next_cursor` when more pages exist.
2. To fetch the *next* page without a skip scan, pass `?cursor=<next_cursor>` in place of `?page`.
3. The `?page=N` URL parameter is still accepted alongside `cursor` for bookmarkability.

The cursor is an opaque base64-encoded string encoding `{sv, id}` (sort value + document ID). **Do not parse or construct cursors manually** — the format may change.

### Security

Malformed cursors (bad base64, invalid JSON, non-scalar `sv`, non-hex `id`) return **HTTP 422** with message `"Invalid or expired cursor"`. Raw exception detail is never exposed.

### Keyset availability

| Sort | Keyset eligible? | Notes |
|------|-----------------|-------|
| `newest` | Yes | `submitted_at` is non-nullable; cursor math is unambiguous |
| `most_stars` | Deferred | `github_stars` is nullable; `$lt: null` semantics are ambiguous |
| `highest_rated` | No | — |
| `most_rated` | No | — |

### Recommended client pattern

```js
// Pages 1–10: use page param (cheap — at most 180 docs scanned)
// Pages 11+: use cursor for sort=newest
const params = page > 10 && cursor && sort === "newest"
  ? { cursor, page_size: 20 }
  : { page, page_size: 20 };
```

---

## Count Caching

To avoid re-running a `count()` on every page load:

- **Unfiltered requests** (no `q`, `labels`, `visibility`, `forked_from`, `submitted_by`) use `estimatedDocumentCount()` — O(1), reads collection metadata.  
  *Note: may slightly over-count by orphaned documents on sharded clusters; acceptable for display.*
- **Filtered requests** cache counts per filter fingerprint with a **30-second TTL** in-process. Cache is size-bounded at 1,000 entries (LRU eviction).
- **Any skill write** (create, deactivate, reactivate) flushes the entire count cache immediately.
- In multi-worker deployments, caches are per-process — counts may differ by up to 30s across workers.

---

## Search Quality

Search uses MongoDB `$text` (stemmed keyword match). A **name boost pre-pass** runs before returning results: skills whose `name` or `slug` exactly matches the query are prepended to the result list regardless of page position.

**Tip for users:** Exact name or slug matches rank first. For conceptual searches (e.g. "kubernetes deployment"), include keywords that appear in the skill's name or description.

### Atlas Search (feature-flagged)

Set `MONGODB_ATLAS_SEARCH=1` to use a MongoDB Atlas Search aggregation pipeline instead of `$text`. **This is permanently inactive on the current self-hosted Percona PSMDB cluster** — Atlas Search is a MongoDB Atlas-cloud-only feature. The flag is reserved for a future Atlas migration. See ADR-U34.

On `OperationFailure` (e.g. index not found), the service logs a warning and falls back to `$text`.

---

## Compound Indexes

The following compound indexes cover all four sort paths:

| Index | Covers |
|-------|--------|
| `(status, submitted_at DESC, _id DESC)` | `sort=newest` + keyset cursor |
| `(status, github_stars DESC, submitted_at DESC)` | `sort=most_stars` |
| `(status, avg_rating DESC, submitted_at DESC)` | `sort=highest_rated` |
| `(status, rating_count DESC, submitted_at DESC)` | `sort=most_rated` |

These make skip-based pages 1–10 fast (index-only scan). Note: when `q` is present, MongoDB uses the `$text` index pipeline and sorts in-memory — compound indexes are bypassed for search queries.

---

## Related ADRs

- **ADR-U32** — Keyset vs. offset pagination strategy (hybrid skip/cursor, backward-compat)
- **ADR-U33** — Count caching strategy (in-process TTL cache + estimatedDocumentCount)
- **ADR-U34** — Search quality improvement (name boost; Atlas Search reserved for Atlas migration)
