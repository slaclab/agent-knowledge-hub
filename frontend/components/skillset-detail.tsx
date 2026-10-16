"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ArrowDown, ArrowUp, Check, Copy, Lock } from "lucide-react";
import type { SkillsetOut } from "@/types/skillset";
import { useAuth } from "@/lib/auth";
import {
  addSkillsetMember,
  deleteSkillset,
  getSkillset,
  removeSkillsetMember,
  reorderSkillset,
  updateSkillset,
} from "@/lib/api";
import { membershipMessage, moveMember } from "@/lib/skillset";
import { formatDate } from "@/lib/utils";
import { SkillSearchPicker } from "@/components/skill-search-picker";

// Where an FR-2g message shows: next to the picker, the list (reorder), or one member's row.
type Notice = { at: string; text: string } | null;

const smallButton =
  "inline-flex items-center rounded-md border px-2 py-1 text-xs hover:bg-muted transition-colors disabled:opacity-40 disabled:cursor-not-allowed";

interface Props {
  initial: SkillsetOut;
  accessInstructionsUrl: string;
}

export function SkillsetDetail({ initial, accessInstructionsUrl }: Props) {
  const { user } = useAuth();
  const [skillset, setSkillset] = useState(initial);
  // One request at a time: a move must carry the version the previous change left behind.
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<Notice>(null);

  const isOwner = !!user && user.user_id === skillset.created_by;
  const canManage = isOwner || !!user?.is_admin;
  const internalCount = skillset.skills.filter((s) => s.visibility === "internal").length;
  const memberSlugs = new Set(skillset.skills.map((s) => s.slug));

  // Add and remove return 204 with no body, so the page reads the skillset again for its version.
  const reload = async () => {
    const fresh = await getSkillset(skillset.slug).catch(() => null);
    if (fresh) setSkillset(fresh);
  };

  const changeMember = async (op: "add" | "remove", skillSlug: string, at: string) => {
    setBusy(true);
    setNotice(null);
    const status =
      op === "add"
        ? await addSkillsetMember(skillset.slug, skillSlug)
        : await removeSkillsetMember(skillset.slug, skillSlug);
    const text = membershipMessage(op, status);
    if (text) setNotice({ at, text });
    else await reload();
    setBusy(false);
  };

  const move = async (index: number, delta: -1 | 1) => {
    const order = moveMember(
      skillset.skills.map((s) => s.slug),
      index,
      delta,
    );
    if (!order) return;
    setBusy(true);
    setNotice(null);
    const { data, status } = await reorderSkillset(skillset.slug, order, skillset.version);
    if (data) setSkillset(data);
    if (status === 409 || status === 422) await reload();
    const text = membershipMessage("order", status);
    if (text) setNotice({ at: "order", text });
    setBusy(false);
  };

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <div className="space-y-1">
        <h1 className="text-3xl font-bold">{skillset.name}</h1>
        {skillset.description && <p className="text-muted-foreground whitespace-pre-line">{skillset.description}</p>}
        <p className="text-sm text-muted-foreground">
          curated by{" "}
          <Link
            href={`/users/${encodeURIComponent(skillset.created_by)}`}
            className="hover:text-foreground hover:underline"
          >
            {skillset.created_by}
          </Link>{" "}
          · created {formatDate(skillset.created_at)}
        </p>
      </div>

      <CopyCommand command={`/agent-knowledge-hub install skillset ${skillset.slug}`} />

      {canManage && <ManageDetails skillset={skillset} onSaved={setSkillset} />}

      {canManage && (
        <div className="rounded-lg border p-4 space-y-2">
          <SkillSearchPicker
            skillsetSlug={skillset.slug}
            memberSlugs={memberSlugs}
            disabled={busy}
            showAddNew={isOwner}
            onAdd={(skillSlug) => changeMember("add", skillSlug, "picker")}
          />
          {notice?.at === "picker" && <p className="text-xs text-destructive">{notice.text}</p>}
          {isOwner && (
            <Link
              href={`/skills/submit?skillset=${encodeURIComponent(skillset.slug)}`}
              className="inline-block text-sm text-primary underline"
            >
              Add new skill →
            </Link>
          )}
        </div>
      )}

      <div className="space-y-2">
        <h2 className="text-lg font-semibold">
          {skillset.skills.length} skill{skillset.skills.length !== 1 ? "s" : ""}
        </h2>

        {internalCount > 0 && (
          <div className="rounded-md border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
            {internalCount === 1 ? "1 skill in this set requires" : `${internalCount} skills in this set require`} SLAC
            GitHub access.{" "}
            <a href={accessInstructionsUrl} className="underline">
              Learn how to get access.
            </a>
          </div>
        )}

        {notice?.at === "order" && <p className="text-sm text-destructive">{notice.text}</p>}

        {skillset.skills.length === 0 ? (
          <p className="text-sm text-muted-foreground">This skillset has no skills yet.</p>
        ) : (
          <ol className="rounded-lg border divide-y">
            {skillset.skills.map((s, i) => (
              <li key={s.slug} className="flex items-start gap-3 p-3">
                <span className="w-6 shrink-0 pt-0.5 text-right text-sm tabular-nums text-muted-foreground">{i + 1}</span>
                <div className={`min-w-0 flex-1 space-y-0.5 ${s.status !== "active" ? "opacity-60" : ""}`}>
                  <div className="flex flex-wrap items-center gap-2">
                    <Link href={`/skills/${s.slug}`} className="font-medium hover:underline">
                      {s.name}
                    </Link>
                    {s.visibility === "internal" && (
                      <span className="inline-flex items-center gap-1 rounded-full bg-amber-100 text-amber-800 px-2 py-0.5 text-xs font-medium">
                        <Lock className="h-3 w-3" />
                        SLAC Only
                      </span>
                    )}
                    {s.status !== "active" && (
                      <span className="inline-flex items-center rounded-full bg-destructive/10 text-destructive px-2 py-0.5 text-xs font-medium">
                        deactivated
                      </span>
                    )}
                  </div>
                  {s.description && <p className="text-sm text-muted-foreground line-clamp-2">{s.description}</p>}
                  {notice?.at === s.slug && <p className="text-xs text-destructive">{notice.text}</p>}
                </div>
                {canManage && (
                  <div className="flex shrink-0 items-center gap-1">
                    <button
                      type="button"
                      onClick={() => move(i, -1)}
                      disabled={busy || i === 0}
                      aria-label={`Move ${s.name} up`}
                      className={smallButton}
                    >
                      <ArrowUp className="h-3.5 w-3.5" />
                    </button>
                    <button
                      type="button"
                      onClick={() => move(i, 1)}
                      disabled={busy || i === skillset.skills.length - 1}
                      aria-label={`Move ${s.name} down`}
                      className={smallButton}
                    >
                      <ArrowDown className="h-3.5 w-3.5" />
                    </button>
                    <button
                      type="button"
                      onClick={() => changeMember("remove", s.slug, s.slug)}
                      disabled={busy}
                      aria-label={`Remove ${s.name} from ${skillset.name}`}
                      className={`${smallButton} text-destructive`}
                    >
                      Remove
                    </button>
                  </div>
                )}
              </li>
            ))}
          </ol>
        )}
      </div>
    </div>
  );
}

function CopyCommand({ command }: { command: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <div className="flex items-center gap-2 rounded-md border bg-muted px-3 py-2">
      <code className="flex-1 overflow-x-auto whitespace-nowrap font-mono text-sm">{command}</code>
      <button
        type="button"
        onClick={() =>
          navigator.clipboard
            .writeText(command)
            .then(() => {
              setCopied(true);
              setTimeout(() => setCopied(false), 2000);
            })
            .catch(() => {})
        }
        aria-label="Copy install command"
        className="inline-flex items-center gap-1 rounded-md border bg-background px-2 py-1 text-xs hover:bg-muted transition-colors"
      >
        {copied ? <Check className="h-3.5 w-3.5" /> : <Copy className="h-3.5 w-3.5" />}
        {copied ? "Copied" : "Copy"}
      </button>
    </div>
  );
}

/** Edit name and description, and delete the skillset: owner and admin (ADR-U19). */
function ManageDetails({ skillset, onSaved }: { skillset: SkillsetOut; onSaved: (s: SkillsetOut) => void }) {
  const router = useRouter();
  const [editing, setEditing] = useState(false);
  const [name, setName] = useState(skillset.name);
  const [description, setDescription] = useState(skillset.description);
  const [confirmingDelete, setConfirmingDelete] = useState(false);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const save = async (e: React.FormEvent) => {
    e.preventDefault();
    setPending(true);
    setError(null);
    const { data, error: err } = await updateSkillset(skillset.slug, { name: name.trim(), description }).catch(() => ({
      data: null,
      error: "Could not save the change. Try again.",
    }));
    setPending(false);
    if (!data) {
      setError(err);
      return;
    }
    onSaved(data);
    setEditing(false);
  };

  const remove = async () => {
    setPending(true);
    setError(null);
    const { error: err } = await deleteSkillset(skillset.slug).catch(() => ({
      error: "Could not delete the skillset. Try again.",
    }));
    if (err) {
      setPending(false);
      setConfirmingDelete(false);
      setError(err);
      return;
    }
    router.push("/skillsets");
  };

  if (editing) {
    return (
      <form onSubmit={save} className="rounded-lg border p-4 space-y-3">
        <div className="space-y-1">
          <label htmlFor="skillset-edit-name" className="text-sm font-medium">
            Name
          </label>
          <input
            id="skillset-edit-name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            required
            maxLength={200}
            className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
          />
        </div>
        <div className="space-y-1">
          <label htmlFor="skillset-edit-description" className="text-sm font-medium">
            Description
          </label>
          <textarea
            id="skillset-edit-description"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            maxLength={2000}
            rows={4}
            className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
          />
        </div>
        {error && <p className="text-xs text-destructive">{error}</p>}
        <div className="flex gap-2">
          <button
            type="submit"
            disabled={pending || !name.trim()}
            className="rounded-md bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50 transition-colors"
          >
            {pending ? "Saving…" : "Save"}
          </button>
          <button
            type="button"
            onClick={() => {
              setEditing(false);
              setName(skillset.name);
              setDescription(skillset.description);
              setError(null);
            }}
            className="rounded-md border px-3 py-1.5 text-sm hover:bg-muted transition-colors"
          >
            Cancel
          </button>
        </div>
      </form>
    );
  }

  return (
    <div className="flex flex-wrap items-center gap-2">
      <button
        type="button"
        onClick={() => setEditing(true)}
        className="inline-flex items-center rounded-md border px-3 py-1.5 text-sm hover:bg-muted transition-colors"
      >
        Edit details
      </button>
      {confirmingDelete ? (
        <>
          <button
            type="button"
            onClick={remove}
            disabled={pending}
            className="inline-flex items-center rounded-md border border-destructive/40 bg-destructive/10 px-3 py-1.5 text-sm text-destructive hover:bg-destructive/20 transition-colors disabled:opacity-50"
          >
            {pending ? "Deleting…" : "Confirm delete"}
          </button>
          <button
            type="button"
            onClick={() => setConfirmingDelete(false)}
            className="rounded-md border px-3 py-1.5 text-sm hover:bg-muted transition-colors"
          >
            Cancel
          </button>
          <span className="text-xs text-muted-foreground">
            Deleting the skillset removes it for everyone. The skills stay in the catalog.
          </span>
        </>
      ) : (
        <button
          type="button"
          onClick={() => setConfirmingDelete(true)}
          className="inline-flex items-center rounded-md border border-destructive/40 px-3 py-1.5 text-sm text-destructive hover:bg-destructive/10 transition-colors"
        >
          Delete skillset
        </button>
      )}
      {error && <p className="w-full text-xs text-destructive">{error}</p>}
    </div>
  );
}
