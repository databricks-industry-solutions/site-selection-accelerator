import { useState, useCallback } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { OpportunityMap } from "@/components/map/opportunity-map";
import { ConfigSidebar } from "@/components/sidebar/config-sidebar";
import { BrandProfileDialog } from "@/components/brand-profile/brand-profile-dialog";
import { FingerprintPanel } from "@/components/fingerprint/fingerprint-panel";
import { AssetsPopover } from "@/components/assets/assets-popover";
import { ShortlistDialog } from "@/components/shortlist/shortlist-dialog";
import { useAnalyze } from "@/lib/use-analyze";
import { useMapDraw } from "@/lib/use-map-draw";
import type { HexagonData, DrawingMode } from "@/lib/types";
import { MapPin } from "lucide-react";

export const Route = createFileRoute("/")({
  component: Index,
});

function Index() {
  const analyzer = useAnalyze();
  const [showBrandProfile, setShowBrandProfile] = useState(false);
  const [selectedHex, setSelectedHex] = useState<HexagonData | null>(null);

  const [brandMode, setBrandMode] = useState<string>("brand_name");
  const [drawingMode, setDrawingMode] = useState<DrawingMode>("point");
  const [mapInstance, setMapInstance] = useState<maplibregl.Map | null>(null);

  const drawingEnabled = brandMode === "map_selection";
  const { features, counts, clear, undo } = useMapDraw(
    mapInstance,
    drawingMode,
    drawingEnabled,
  );

  const handleHexClick = useCallback((hex: HexagonData) => {
    setSelectedHex(hex);
  }, []);

  const handleMapReady = useCallback((map: maplibregl.Map) => {
    setMapInstance(map);
  }, []);

  const sessionId = analyzer.result?.session_id ?? null;
  const hasResults = !!analyzer.result;

  return (
    <div className="relative h-screen w-screen overflow-hidden">
      <OpportunityMap
        hexagons={analyzer.result?.hexagons}
        brandLocations={analyzer.result?.brand_locations}
        existingTargetLocations={analyzer.result?.existing_target_locations}
        cityPolygonGeoJson={analyzer.result?.city_polygon_geojson}
        centerLat={analyzer.result?.center_lat}
        centerLon={analyzer.result?.center_lon}
        hasCompetition={analyzer.result?.has_competition}
        competitorBrand={analyzer.result?.competitor_brand}
        onHexClick={handleHexClick}
        onMapReady={handleMapReady}
        drawingEnabled={drawingEnabled}
        drawingMode={drawingMode}
        onDrawingModeChange={setDrawingMode}
        drawnFeatureCounts={counts}
        onClearDrawing={clear}
        onUndoDrawing={undo}
      />

      {!hasResults && !drawingEnabled && (
        <EmptyState isRunning={analyzer.isRunning} />
      )}

      <ConfigSidebar
        isRunning={analyzer.isRunning}
        progress={analyzer.progress}
        stepLabel={analyzer.stepLabel}
        error={analyzer.error}
        hasResult={hasResults}
        sessionId={sessionId}
        onRun={analyzer.run}
        onShowBrandProfile={() => setShowBrandProfile(true)}
        onBrandModeChange={setBrandMode}
        drawnFeatures={features}
        drawnFeatureCounts={counts}
        onClearDrawnFeatures={clear}
      />

      <div className="absolute bottom-4 right-4 z-20 flex gap-2">
        <ShortlistDialog />
        <AssetsPopover />
      </div>

      <BrandProfileDialog
        open={showBrandProfile}
        onOpenChange={setShowBrandProfile}
        sessionId={sessionId}
      />

      <FingerprintPanel
        hex={selectedHex}
        sessionId={sessionId}
        competitorBrand={analyzer.result?.competitor_brand}
        onClose={() => setSelectedHex(null)}
      />
    </div>
  );
}

function EmptyState({ isRunning }: { isRunning: boolean }) {
  return (
    <div className="absolute inset-0 z-10 flex items-center justify-center pointer-events-none">
      <div className="text-center space-y-4 max-w-md px-4 pointer-events-auto">
        <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-full bg-primary/10">
          <MapPin className="h-8 w-8 text-primary" />
        </div>
        <h1 className="text-2xl font-bold tracking-tight">
          Site Selection Accelerator
        </h1>
        <p className="text-muted-foreground">
          {isRunning
            ? "Analyzing opportunities..."
            : "Configure your brand and target market in the sidebar, then click \"Find Opportunities\" to discover whitespace expansion areas."}
        </p>
      </div>
    </div>
  );
}
