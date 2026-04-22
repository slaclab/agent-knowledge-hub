const LABEL_COLORS = [
  "bg-blue-100   text-blue-800   border-blue-200",
  "bg-violet-100 text-violet-800 border-violet-200",
  "bg-emerald-100 text-emerald-800 border-emerald-200",
  "bg-amber-100  text-amber-800  border-amber-200",
  "bg-rose-100   text-rose-800   border-rose-200",
  "bg-cyan-100   text-cyan-800   border-cyan-200",
  "bg-fuchsia-100 text-fuchsia-800 border-fuchsia-200",
  "bg-lime-100   text-lime-800   border-lime-200",
  "bg-orange-100 text-orange-800 border-orange-200",
  "bg-teal-100   text-teal-800   border-teal-200",
] as const;

export function labelColor(name: string): string {
  let hash = 0;
  for (let i = 0; i < name.length; i++) {
    hash = (hash * 31 + name.charCodeAt(i)) >>> 0;
  }
  return LABEL_COLORS[hash % LABEL_COLORS.length];
}
