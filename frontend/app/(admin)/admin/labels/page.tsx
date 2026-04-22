"use client";

import { useState, useEffect, useCallback } from "react";
import * as AlertDialog from "@radix-ui/react-alert-dialog";
import type { AdminLabelOut } from "@/types/skill";

async function fetchAdminLabels(): Promise<AdminLabelOut[]> {
  const r = await fetch("/api/admin/labels");
  if (!r.ok) return [];
  return r.json();
}

async function renameLabel(id: string, name: string): Promise<{ error: string | null }> {
  const r = await fetch(`/api/admin/labels/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name }),
  });
  if (!r.ok) {
    const j = await r.json().catch(() => ({}));
    return { error: (j as { detail?: string }).detail ?? "Rename failed" };
  }
  return { error: null };
}

async function mergeLabel(sourceId: string, intoId: string): Promise<{ error: string | null }> {
  const r = await fetch(`/api/admin/labels/${sourceId}/merge`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ into_id: intoId }),
  });
  if (!r.ok) {
    const j = await r.json().catch(() => ({}));
    return { error: (j as { detail?: string }).detail ?? "Merge failed" };
  }
  return { error: null };
}

async function deleteLabel(id: string): Promise<{ error: string | null }> {
  const r = await fetch(`/api/admin/labels/${id}`, { method: "DELETE" });
  if (r.status === 204 || r.ok) return { error: null };
  const j = await r.json().catch(() => ({}));
  return { error: (j as { detail?: string }).detail ?? "Delete failed" };
}

export default function AdminLabelsPage() {
  const [labels, setLabels] = useState<AdminLabelOut[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [renaming, setRenaming] = useState<{ id: string; name: string } | null>(null);
  const [renameValue, setRenameValue] = useState("");
  const [mergeSource, setMergeSource] = useState<AdminLabelOut | null>(null);
  const [mergeTarget, setMergeTarget] = useState<string>("");
  const [actionError, setActionError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    const r = await fetch("/api/admin/labels");
    if (!r.ok) {
      setError("Failed to load labels.");
      setLoading(false);
      return;
    }
    const data = await r.json();
    setLabels(data);
    setLoading(false);
  }, []);

  useEffect(() => { load(); }, [load]);

  const handleRename = async () => {
    if (!renaming || !renameValue.trim()) return;
    setActionError(null);
    const { error: err } = await renameLabel(renaming.id, renameValue.trim());
    if (err) { setActionError(err); return; }
    setRenaming(null);
    setRenameValue("");
    load();
  };

  const handleMerge = async () => {
    if (!mergeSource || !mergeTarget) return;
    setActionError(null);
    const { error: err } = await mergeLabel(mergeSource.id, mergeTarget);
    if (err) { setActionError(err); return; }
    setMergeSource(null);
    setMergeTarget("");
    load();
  };

  const handleDelete = async (label: AdminLabelOut) => {
    setActionError(null);
    const { error: err } = await deleteLabel(label.id);
    if (err) { setActionError(err); return; }
    load();
  };

  if (loading) return <div className="text-sm text-muted-foreground py-8">Loading…</div>;
  if (error) return <div className="text-sm text-destructive py-8">{error}</div>;

  return (
    <div className="space-y-6 max-w-3xl">
      <div>
        <h1 className="text-2xl font-bold">Label Management</h1>
        <p className="text-sm text-muted-foreground mt-1">
          Rename, merge, or delete community labels.
        </p>
      </div>

      {actionError && (
        <div className="rounded-md border border-destructive/50 bg-destructive/10 px-4 py-2 text-sm text-destructive">
          {actionError}
        </div>
      )}

      <div className="rounded-lg border overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-muted/50">
            <tr>
              <th className="text-left px-4 py-2 font-medium">Label</th>
              <th className="text-right px-4 py-2 font-medium">Skills</th>
              <th className="text-right px-4 py-2 font-medium">Actions</th>
            </tr>
          </thead>
          <tbody>
            {labels.map((label) => (
              <tr key={label.id} className="border-t hover:bg-muted/30 transition-colors">
                <td className="px-4 py-2 font-mono">{label.name}</td>
                <td className="px-4 py-2 text-right tabular-nums text-muted-foreground">
                  {label.usage_count}
                </td>
                <td className="px-4 py-2 text-right">
                  <div className="inline-flex items-center gap-2">
                    {/* Rename */}
                    <AlertDialog.Root
                      open={renaming?.id === label.id}
                      onOpenChange={(open) => {
                        if (!open) { setRenaming(null); setRenameValue(""); setActionError(null); }
                      }}
                    >
                      <AlertDialog.Trigger asChild>
                        <button
                          onClick={() => { setRenaming({ id: label.id, name: label.name }); setRenameValue(label.name); }}
                          className="text-xs text-muted-foreground hover:text-foreground transition-colors"
                        >
                          Rename
                        </button>
                      </AlertDialog.Trigger>
                      <AlertDialog.Portal>
                        <AlertDialog.Overlay className="fixed inset-0 bg-black/40 z-40" />
                        <AlertDialog.Content className="fixed left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 z-50 w-full max-w-sm rounded-lg border bg-background p-6 shadow-lg space-y-4">
                          <AlertDialog.Title className="font-semibold">
                            Rename &ldquo;{renaming?.name}&rdquo;
                          </AlertDialog.Title>
                          <input
                            value={renameValue}
                            onChange={(e) => setRenameValue(e.target.value)}
                            className="w-full rounded-md border border-input bg-background px-3 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-ring"
                            autoFocus
                          />
                          {actionError && (
                            <p className="text-xs text-destructive">{actionError}</p>
                          )}
                          <div className="flex justify-end gap-2">
                            <AlertDialog.Cancel className="rounded-md border px-3 py-1.5 text-sm hover:bg-muted transition-colors">
                              Cancel
                            </AlertDialog.Cancel>
                            <button
                              onClick={handleRename}
                              className="rounded-md bg-primary px-3 py-1.5 text-sm text-primary-foreground hover:bg-primary/90 transition-colors"
                            >
                              Save
                            </button>
                          </div>
                        </AlertDialog.Content>
                      </AlertDialog.Portal>
                    </AlertDialog.Root>

                    {/* Merge */}
                    <AlertDialog.Root
                      open={mergeSource?.id === label.id}
                      onOpenChange={(open) => {
                        if (!open) { setMergeSource(null); setMergeTarget(""); setActionError(null); }
                      }}
                    >
                      <AlertDialog.Trigger asChild>
                        <button
                          onClick={() => setMergeSource(label)}
                          className="text-xs text-muted-foreground hover:text-foreground transition-colors"
                        >
                          Merge
                        </button>
                      </AlertDialog.Trigger>
                      <AlertDialog.Portal>
                        <AlertDialog.Overlay className="fixed inset-0 bg-black/40 z-40" />
                        <AlertDialog.Content className="fixed left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 z-50 w-full max-w-sm rounded-lg border bg-background p-6 shadow-lg space-y-4">
                          <AlertDialog.Title className="font-semibold">
                            Merge &ldquo;{mergeSource?.name}&rdquo; into…
                          </AlertDialog.Title>
                          <AlertDialog.Description className="text-sm text-muted-foreground">
                            All {mergeSource?.usage_count} skill association{mergeSource?.usage_count !== 1 ? "s" : ""} will move to the target label.
                            &ldquo;{mergeSource?.name}&rdquo; will be permanently deleted. This is irreversible.
                          </AlertDialog.Description>
                          <select
                            value={mergeTarget}
                            onChange={(e) => setMergeTarget(e.target.value)}
                            className="w-full rounded-md border border-input bg-background px-3 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-ring"
                          >
                            <option value="">Select target label…</option>
                            {labels.filter((l) => l.id !== label.id).map((l) => (
                              <option key={l.id} value={l.id}>{l.name} ({l.usage_count})</option>
                            ))}
                          </select>
                          {actionError && <p className="text-xs text-destructive">{actionError}</p>}
                          <div className="flex justify-end gap-2">
                            <AlertDialog.Cancel className="rounded-md border px-3 py-1.5 text-sm hover:bg-muted transition-colors">
                              Cancel
                            </AlertDialog.Cancel>
                            <AlertDialog.Action
                              onClick={handleMerge}
                              disabled={!mergeTarget}
                              className="rounded-md bg-destructive px-3 py-1.5 text-sm text-destructive-foreground hover:bg-destructive/90 transition-colors disabled:opacity-50"
                            >
                              Merge
                            </AlertDialog.Action>
                          </div>
                        </AlertDialog.Content>
                      </AlertDialog.Portal>
                    </AlertDialog.Root>

                    {/* Delete */}
                    <AlertDialog.Root>
                      <AlertDialog.Trigger asChild>
                        <button className="text-xs text-destructive/70 hover:text-destructive transition-colors">
                          Delete
                        </button>
                      </AlertDialog.Trigger>
                      <AlertDialog.Portal>
                        <AlertDialog.Overlay className="fixed inset-0 bg-black/40 z-40" />
                        <AlertDialog.Content className="fixed left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 z-50 w-full max-w-sm rounded-lg border bg-background p-6 shadow-lg space-y-4">
                          <AlertDialog.Title className="font-semibold">
                            Delete &ldquo;{label.name}&rdquo;?
                          </AlertDialog.Title>
                          <AlertDialog.Description className="text-sm text-muted-foreground">
                            This will remove &ldquo;{label.name}&rdquo; from all {label.usage_count} skill{label.usage_count !== 1 ? "s" : ""} and delete the label permanently. This is irreversible.
                          </AlertDialog.Description>
                          {actionError && <p className="text-xs text-destructive">{actionError}</p>}
                          <div className="flex justify-end gap-2">
                            <AlertDialog.Cancel className="rounded-md border px-3 py-1.5 text-sm hover:bg-muted transition-colors">
                              Cancel
                            </AlertDialog.Cancel>
                            <AlertDialog.Action
                              onClick={() => handleDelete(label)}
                              className="rounded-md bg-destructive px-3 py-1.5 text-sm text-destructive-foreground hover:bg-destructive/90 transition-colors"
                            >
                              Delete
                            </AlertDialog.Action>
                          </div>
                        </AlertDialog.Content>
                      </AlertDialog.Portal>
                    </AlertDialog.Root>
                  </div>
                </td>
              </tr>
            ))}
            {labels.length === 0 && (
              <tr>
                <td colSpan={3} className="px-4 py-8 text-center text-muted-foreground text-sm">
                  No labels yet.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
