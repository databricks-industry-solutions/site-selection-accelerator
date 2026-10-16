import { useEffect, useMemo, useState } from "react";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Separator } from "@/components/ui/separator";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import {
  BarChart,
  Bar,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";
import { Button } from "@/components/ui/button";
import { ChevronDown, Star } from "lucide-react";
import { addToShortlist } from "@/lib/shortlist";
import type { HexagonData, HexagonDetail, GenieDebug } from "@/lib/types";

interface FingerprintPanelProps {
  hex: HexagonData | null;
  sessionId: string | null;
  competitorBrand?: string;
  onClose: () => void;
}

export function FingerprintPanel({
  hex,
  sessionId,
  competitorBrand = "",
  onClose,
}: FingerprintPanelProps) {
  const [detail, setDetail] = useState<HexagonDetail | null>(null);
  const [genieDebug, setGenieDebug] = useState<GenieDebug | null>(null);
  const [loading, setLoading] = useState(false);
  const [chartStyle, setChartStyle] = useState<"bar" | "line">("bar");
  const [metric, setMetric] = useState<"counts" | "pct">("pct");

  const [error, setError] = useState<string | null>(null);
  const [shortlistState, setShortlistState] = useState<"idle" | "saving" | "saved" | string>("idle");

  useEffect(() => setShortlistState("idle"), [hex]);

  const handleShortlist = () => {
    if (!hex || !sessionId) return;
    setShortlistState("saving");
    addToShortlist(sessionId, hex.hex_id)
      .then(() => setShortlistState("saved"))
      .catch((e) => setShortlistState(e instanceof Error ? e.message : "Failed to save"));
  };

  const cellCompetitorStores = useMemo(() => {
    if (!detail?.competitor_pois?.length) return [];
    return detail.competitor_pois.map((poi) => ({
      name: cleanText(poi.name) || cleanText(poi.brand) || "—",
      brand: cleanText(poi.brand) || cleanText(poi.name) || "—",
      address: cleanText(poi.address) || "—",
    }));
  }, [detail]);

  useEffect(() => {
    if (!hex || !sessionId) {
      setDetail(null);
      setError(null);
      return;
    }
    setLoading(true);
    setError(null);

    const detailP = fetch(`/api/results/${sessionId}/hexagon/${hex.hex_id}`)
      .then((r) => {
        if (!r.ok) throw new Error(`API error: ${r.status}`);
        return r.json();
      });

    const debugP = fetch(`/api/results/${sessionId}/debug`)
      .then((r) => (r.ok ? r.json() : null))
      .catch(() => null);

    Promise.all([detailP, debugP])
      .then(([detailData, debugData]: [HexagonDetail, GenieDebug | null]) => {
        setDetail(detailData);
        setGenieDebug(debugData);
        setLoading(false);
      })
      .catch((e) => {
        setError(e instanceof Error ? e.message : "Failed to load detail");
        setLoading(false);
      });
  }, [hex, sessionId]);

  const open = hex !== null;

  return (
    <Sheet open={open} onOpenChange={(isOpen) => { if (!isOpen) onClose(); }}>
      <SheetContent side="right" className="w-[480px] sm:max-w-lg overflow-auto">
        <SheetHeader>
          <SheetTitle className="text-base">
            {detail?.address || hex?.address || hex?.hex_id || "Hexagon Detail"}
          </SheetTitle>
        </SheetHeader>

        {loading ? (
          <div className="space-y-3 mt-4">
            <Skeleton className="h-4 w-48" />
            <Skeleton className="h-4 w-32" />
            <Skeleton className="h-64 w-full" />
          </div>
        ) : error ? (
          <p className="text-sm text-destructive mt-4">{error}</p>
        ) : detail ? (
          <div className="mt-4 space-y-4">
            {/* Score badges */}
            <div className="flex flex-wrap gap-2">
              <Badge variant="outline" className="text-xs">
                Similarity: {(detail.similarity * 100).toFixed(1)}%
              </Badge>
              <Badge variant="secondary" className="text-xs">
                POI Density: {detail.poi_density}
              </Badge>
              {hex?.radiance != null && Number.isFinite(hex.radiance) && (
                <Badge variant="secondary" className="text-xs">
                  Economic Activity: {hex.radiance.toFixed(1)} nW/cm²/sr
                </Badge>
              )}
              {detail.competition && detail.competition.competitor_count > 0 && (
                <Badge variant="secondary" className="text-xs">
                  Competition: {detail.competition.competitor_count}
                </Badge>
              )}
              {detail.cannibalization_risk != null && detail.nearest_store_km != null && (
                <Badge
                  variant={detail.cannibalization_risk >= 0.5 ? "destructive" : "secondary"}
                  className="text-xs"
                  title="Share of this site's catchment already covered by one of the brand's existing stores"
                >
                  Cannibalization: {(detail.cannibalization_risk * 100).toFixed(0)}% ·{" "}
                  {detail.nearest_store_km.toFixed(1)} km to own store
                </Badge>
              )}
            </div>

            {!hex?.is_brand_cell && (
              <div className="flex items-center gap-2">
                <Button
                  size="sm"
                  variant={shortlistState === "saved" ? "secondary" : "default"}
                  className="gap-2"
                  disabled={shortlistState === "saving" || shortlistState === "saved"}
                  onClick={handleShortlist}
                >
                  <Star className="h-4 w-4" />
                  {shortlistState === "saved" ? "On shortlist" : "Add to shortlist"}
                </Button>
                {!["idle", "saving", "saved"].includes(shortlistState) && (
                  <span className="text-xs text-destructive">{shortlistState}</span>
                )}
              </div>
            )}

            {/* Explanation summary (above fingerprint) */}
            {detail.explanation_summary && (
              <div className="rounded-md border bg-muted/50 px-3 py-2 text-xs">
                {detail.explanation_summary}
              </div>
            )}

            {/* Chart controls */}
            <div className="flex items-center justify-between">
              <h4 className="text-sm font-medium">Category Fingerprint</h4>
              <div className="flex items-center gap-2">
                <ToggleGroup
                  type="single"
                  value={chartStyle}
                  onValueChange={(v) => v && setChartStyle(v as "bar" | "line")}
                  size="sm"
                >
                  <ToggleGroupItem value="bar" className="text-xs px-2 h-7">Bar</ToggleGroupItem>
                  <ToggleGroupItem value="line" className="text-xs px-2 h-7">Line</ToggleGroupItem>
                </ToggleGroup>
                <ToggleGroup
                  type="single"
                  value={metric}
                  onValueChange={(v) => v && setMetric(v as "counts" | "pct")}
                  size="sm"
                >
                  <ToggleGroupItem value="counts" className="text-xs px-2 h-7">Counts</ToggleGroupItem>
                  <ToggleGroupItem value="pct" className="text-xs px-2 h-7">% Type</ToggleGroupItem>
                </ToggleGroup>
              </div>
            </div>

            <FingerprintChart
              detail={detail}
              chartStyle={chartStyle}
              metric={metric}
            />

            {/* Competitor store details with addresses */}
            {cellCompetitorStores.length > 0 && (
              <details className="group" open>
                <summary className="flex cursor-pointer items-center justify-between text-xs font-medium hover:underline list-none">
                  <span>Competitor: {competitorBrand || "Stores"} ({cellCompetitorStores.length})</span>
                  <ChevronDown className="h-3.5 w-3.5 transition-transform group-open:rotate-180" />
                </summary>
                <div className="mt-1 max-h-48 overflow-auto rounded border">
                  <table className="w-full text-xs">
                    <thead className="bg-muted/50 sticky top-0">
                      <tr>
                        <th className="px-2 py-1 text-left font-medium">#</th>
                        <th className="px-2 py-1 text-left font-medium">Name</th>
                        <th className="px-2 py-1 text-left font-medium">Address</th>
                      </tr>
                    </thead>
                    <tbody>
                      {cellCompetitorStores.map((row, i) => (
                        <tr key={`${row.name}-${i}`} className="border-t">
                          <td className="px-2 py-1 text-muted-foreground">{i + 1}</td>
                          <td className="px-2 py-1">{row.name}</td>
                          <td className="px-2 py-1 text-muted-foreground">{row.address}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </details>
            )}

            {/* Cell POI breakdown (near bottom) */}
            {detail.cell_pois && detail.cell_pois.length > 0 && (
              <details className="group" open>
                <summary className="flex cursor-pointer items-center justify-between text-xs font-medium hover:underline list-none">
                  <span>{detail.cell_pois_title || "Cell POI Breakdown"} ({detail.cell_pois.length})</span>
                  <ChevronDown className="h-3.5 w-3.5 transition-transform group-open:rotate-180" />
                </summary>
                <div className="mt-1 max-h-56 overflow-auto rounded border">
                  <table className="w-full text-xs">
                    <thead className="bg-muted/50 sticky top-0">
                      <tr>
                        <th className="px-2 py-1 text-left font-medium">POI Name</th>
                        <th className="px-2 py-1 text-left font-medium">Brand</th>
                        <th className="px-2 py-1 text-left font-medium">Address</th>
                      </tr>
                    </thead>
                    <tbody>
                      {detail.cell_pois.map((poi, i) => (
                        <tr key={`${poi.name}-${i}`} className="border-t">
                          <td className="px-2 py-1">{cleanText(poi.name) || "—"}</td>
                          <td className="px-2 py-1 text-muted-foreground">
                            {cleanText(poi.brand) || cleanText(poi.name) || "—"}
                          </td>
                          <td className="px-2 py-1 text-muted-foreground">
                            {cleanText(poi.address) || "—"}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </details>
            )}

            <Separator />

            {/* Genie Debug (last) */}
            {genieDebug && genieDebug.brand_pois.length > 0 && (
              <details className="group">
                <summary className="flex cursor-pointer items-center justify-between text-xs font-medium hover:underline list-none">
                  <span>
                    Genie Results ({genieDebug.total_brand_pois} brand POIs, {genieDebug.competitor_pois_total} competitors)
                  </span>
                  <ChevronDown className="h-3.5 w-3.5 transition-transform group-open:rotate-180" />
                </summary>
                <div className="mt-1 max-h-48 overflow-auto rounded border">
                  <table className="w-full text-xs">
                    <thead className="bg-muted/50 sticky top-0">
                      <tr>
                        <th className="px-2 py-1 text-left font-medium">Name</th>
                        <th className="px-2 py-1 text-left font-medium">Category</th>
                        <th className="px-2 py-1 text-left font-medium">Brand</th>
                        <th className="px-2 py-1 text-left font-medium">H3</th>
                      </tr>
                    </thead>
                    <tbody>
                      {genieDebug.brand_pois.map((poi, i) => (
                        <tr key={i} className="border-t">
                          <td className="px-2 py-1">{poi.name}</td>
                          <td className="px-2 py-1 text-muted-foreground">{poi.category}</td>
                          <td className="px-2 py-1 text-muted-foreground">{cleanText(poi.brand) || cleanText(poi.name)}</td>
                          <td className="px-2 py-1 text-muted-foreground font-mono text-[10px]">
                            {poi.h3_cell ? poi.h3_cell.slice(-6) : "—"}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </details>
            )}
          </div>
        ) : (
          <p className="text-sm text-muted-foreground mt-4">
            Click a hexagon on the map to see its analysis.
          </p>
        )}
      </SheetContent>
    </Sheet>
  );
}

function FingerprintChart({
  detail,
  chartStyle,
  metric,
}: {
  detail: HexagonDetail;
  chartStyle: "bar" | "line";
  metric: "counts" | "pct";
}) {
  const fp = detail.fingerprint ?? [];
  if (fp.length === 0) {
    return <p className="text-xs text-muted-foreground">No categories to compare.</p>;
  }

  const nonEmpty = fp.filter(
    (r) =>
      (metric === "pct" ? r.this_location_pct : r.this_location) > 0 ||
      (metric === "pct" ? r.brand_average_pct : r.brand_average) > 0,
  );

  const chartData = nonEmpty.map((r) => ({
    category: r.category,
    "This Location": metric === "pct" ? r.this_location_pct : r.this_location,
    "Brand Average": metric === "pct" ? r.brand_average_pct : r.brand_average,
  }));

  const yLabel = metric === "pct" ? "% within Type" : "Count";
  const height = Math.max(300, Math.min(chartData.length * 20, 500));

  if (chartStyle === "line") {
    return (
      <ResponsiveContainer width="100%" height={height}>
        <LineChart data={chartData} margin={{ left: 10, right: 10, bottom: 60 }}>
          <CartesianGrid strokeDasharray="3 3" opacity={0.3} />
          <XAxis
            dataKey="category"
            tick={{ fontSize: 10 }}
            angle={-45}
            textAnchor="end"
            interval={0}
            height={80}
          />
          <YAxis tick={{ fontSize: 10 }} label={{ value: yLabel, angle: -90, position: "insideLeft", style: { fontSize: 10 } }} />
          <Tooltip contentStyle={{ fontSize: 11 }} />
          <Legend wrapperStyle={{ fontSize: 11 }} />
          <Line
            type="monotone"
            dataKey="This Location"
            stroke="#2ecc71"
            strokeWidth={2}
            dot={{ r: 3 }}
          />
          <Line
            type="monotone"
            dataKey="Brand Average"
            stroke="#3498db"
            strokeWidth={2}
            dot={{ r: 3 }}
          />
        </LineChart>
      </ResponsiveContainer>
    );
  }

  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={chartData} margin={{ left: 10, right: 10, bottom: 60 }}>
        <CartesianGrid strokeDasharray="3 3" opacity={0.3} />
        <XAxis
          dataKey="category"
          tick={{ fontSize: 10 }}
          angle={-45}
          textAnchor="end"
          interval={0}
          height={80}
        />
        <YAxis tick={{ fontSize: 10 }} label={{ value: yLabel, angle: -90, position: "insideLeft", style: { fontSize: 10 } }} />
        <Tooltip contentStyle={{ fontSize: 11 }} />
        <Legend wrapperStyle={{ fontSize: 11 }} />
        <Bar dataKey="This Location" fill="#2ecc71" opacity={0.85} radius={[4, 4, 0, 0]} />
        <Bar dataKey="Brand Average" fill="#3498db" opacity={0.85} radius={[4, 4, 0, 0]} />
      </BarChart>
    </ResponsiveContainer>
  );
}

function cleanText(value: string | null | undefined): string {
  const text = (value ?? "").trim();
  if (!text) return "";
  const lower = text.toLowerCase();
  if (lower === "nan" || lower === "null" || lower === "none") return "";
  return text;
}

function competitorLabel(poi: { name: string; brand: string }): string {
  return cleanText(poi.brand) || cleanText(poi.name);
}
