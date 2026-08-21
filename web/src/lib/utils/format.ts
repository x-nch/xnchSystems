export function formatRelativeTime(iso: string | number | null): string {
  if (iso == null) return "";
  const t = typeof iso === "number" ? iso : new Date(iso).getTime();
  if (Number.isNaN(t)) return "";
  const diffMs = Date.now() - t;
  const abs = Math.abs(diffMs);
  const mins = Math.floor(abs / 60_000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  if (days < 7) return `${days}d ago`;
  return new Date(t).toLocaleDateString();
}

export function formatFullTime(iso: string | number | null): string {
  if (iso == null) return "";
  const t = typeof iso === "number" ? iso : new Date(iso).getTime();
  if (Number.isNaN(t)) return "";
  return new Date(t).toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function formatPercent(value: number): string {
  return `${Math.round(value * 100)}%`;
}

export function truncate(value: string, max = 120): string {
  if (value.length <= max) return value;
  return `${value.slice(0, max)}…`;
}

export function slugify(value: string): string {
  return value
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/(^-|-$)/g, "");
}
