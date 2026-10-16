import { useCallback, useEffect, useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Textarea } from "@/components/ui/textarea";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Star, Trash2 } from "lucide-react";
import type { ShortlistItem, ShortlistStatus } from "@/lib/types";
import {
  SHORTLIST_CHANGED,
  STATUS_LABELS,
  listShortlist,
  removeShortlistItem,
  updateShortlistItem,
} from "@/lib/shortlist";

function pct(v: number | null): string {
  return v == null ? "—" : `${(v * 100).toFixed(0)}%`;
}

function ShortlistRow({ item }: { item: ShortlistItem }) {
  const [note, setNote] = useState(item.note);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => setNote(item.note), [item.note]);

  const run = (p: Promise<unknown>) =>
    p.catch((e) => setError(e instanceof Error ? e.message : "Update failed"));

  return (
    <div className="rounded-md border p-3 space-y-2 text-sm">
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <div className="font-medium truncate">{item.address || item.hex_id}</div>
          <div className="text-xs text-muted-foreground">
            {[item.brand, item.city, item.country].filter(Boolean).join(" · ")}
          </div>
        </div>
        <Button
          variant="ghost"
          size="icon"
          className="h-7 w-7 shrink-0"
          aria-label="Remove from shortlist"
          onClick={() => run(removeShortlistItem(item.id))}
        >
          <Trash2 className="h-4 w-4" />
        </Button>
      </div>

      <div className="flex flex-wrap gap-1.5">
        <Badge variant="outline" className="text-xs">Similarity {pct(item.similarity)}</Badge>
        {item.opportunity_score != null && (
          <Badge variant="outline" className="text-xs">Opportunity {pct(item.opportunity_score)}</Badge>
        )}
        <Badge variant="secondary" className="text-xs">
          Cannibalization {pct(item.cannibalization_risk)}
          {item.nearest_store_km != null && ` · ${item.nearest_store_km.toFixed(1)} km`}
        </Badge>
      </div>

      <Select
        value={item.status}
        onValueChange={(v) => run(updateShortlistItem(item.id, { status: v as ShortlistStatus }))}
      >
        <SelectTrigger className="h-8 text-xs">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          {(Object.keys(STATUS_LABELS) as ShortlistStatus[]).map((s) => (
            <SelectItem key={s} value={s} className="text-xs">
              {STATUS_LABELS[s]}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>

      <Textarea
        value={note}
        placeholder="Notes (lease terms, footfall, site-visit findings…)"
        className="min-h-[56px] text-xs"
        onChange={(e) => setNote(e.target.value)}
        onBlur={() => {
          if (note !== item.note) run(updateShortlistItem(item.id, { note }));
        }}
      />
      {error && <p className="text-xs text-destructive">{error}</p>}
    </div>
  );
}

export function ShortlistDialog() {
  const [open, setOpen] = useState(false);
  const [items, setItems] = useState<ShortlistItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setItems(await listShortlist());
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load shortlist");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (open) refresh();
  }, [open, refresh]);

  useEffect(() => {
    const onChange = () => { if (open) refresh(); };
    window.addEventListener(SHORTLIST_CHANGED, onChange);
    return () => window.removeEventListener(SHORTLIST_CHANGED, onChange);
  }, [open, refresh]);

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button variant="outline" size="sm" className="gap-2 bg-card/95 backdrop-blur shadow-lg">
          <Star className="h-4 w-4" />
          Shortlist
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Star className="h-5 w-5" />
            Site Shortlist
          </DialogTitle>
        </DialogHeader>
        <ScrollArea className="max-h-[65vh]">
          <div className="space-y-3 pr-2">
            {loading && items.length === 0 && (
              <p className="text-sm text-muted-foreground text-center py-4">Loading shortlist...</p>
            )}
            {error && <p className="text-sm text-destructive text-center py-4">{error}</p>}
            {!loading && !error && items.length === 0 && (
              <p className="text-sm text-muted-foreground text-center py-4">
                No sites yet — open a hexagon and click "Add to shortlist".
              </p>
            )}
            {items.map((item) => (
              <ShortlistRow key={item.id} item={item} />
            ))}
          </div>
        </ScrollArea>
      </DialogContent>
    </Dialog>
  );
}
