import type { ShortlistItem, ShortlistStatus } from "@/lib/types";

// Shortlist lives in Lakebase (see backend lakebase.py). Components that
// change it fire this event so any open shortlist view refetches.
export const SHORTLIST_CHANGED = "shortlist:changed";

export const STATUS_LABELS: Record<ShortlistStatus, string> = {
  candidate: "Candidate",
  site_visit: "Site visit",
  negotiating: "Negotiating",
  rejected: "Rejected",
};

async function call<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!res.ok) {
    const detail = await res.json().then((b) => b?.detail).catch(() => "");
    throw new Error(detail || `API error: ${res.status}`);
  }
  return res.json();
}

function notify() {
  window.dispatchEvent(new Event(SHORTLIST_CHANGED));
}

export function listShortlist(): Promise<ShortlistItem[]> {
  return call<ShortlistItem[]>("/api/shortlist");
}

export async function addToShortlist(sessionId: string, hexId: string): Promise<ShortlistItem> {
  const item = await call<ShortlistItem>("/api/shortlist", {
    method: "POST",
    body: JSON.stringify({ session_id: sessionId, hex_id: hexId }),
  });
  notify();
  return item;
}

export async function updateShortlistItem(
  id: number,
  patch: { status?: ShortlistStatus; note?: string },
): Promise<ShortlistItem> {
  const item = await call<ShortlistItem>(`/api/shortlist/${id}`, {
    method: "PATCH",
    body: JSON.stringify(patch),
  });
  notify();
  return item;
}

export async function removeShortlistItem(id: number): Promise<void> {
  await call(`/api/shortlist/${id}`, { method: "DELETE" });
  notify();
}
