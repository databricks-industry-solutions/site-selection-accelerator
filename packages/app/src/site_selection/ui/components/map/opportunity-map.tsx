import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Map, useControl, type MapRef } from "react-map-gl/maplibre";
import { MapboxOverlay } from "@deck.gl/mapbox";
import { H3HexagonLayer } from "@deck.gl/geo-layers";
import { ScatterplotLayer, GeoJsonLayer } from "@deck.gl/layers";
import type { PickingInfo, Layer } from "@deck.gl/core";
import type { HexagonData, BrandLocationData, DrawingMode } from "@/lib/types";
import { DrawToolbar } from "./draw-toolbar";
import { MapLegend } from "./map-legend";
import "maplibre-gl/dist/maplibre-gl.css";

const CARTO_BASEMAP =
  "https://basemaps.cartocdn.com/gl/positron-gl-style/style.json";

const DEFAULT_CENTER = { lat: 51.5074, lon: -0.1278 };
const DEFAULT_ZOOM = 5;

function scoreToColor(score: number): [number, number, number, number] {
  const r = Math.round(Math.min(score * 2, 1) * 255);
  const g = Math.round(Math.min(2 - score * 2, 1) * 150);
  const b = Math.round((1 - score) * 200);
  return [r, g, b, 140];
}

function radianceLabel(value: number): string {
  if (value <= 2) return "Rural / unlit";
  if (value <= 10) return "Suburban";
  if (value <= 30) return "Urban neighbourhood";
  if (value <= 80) return "City centre";
  return "Major commercial district";
}

function DeckGLOverlay(props: {
  layers: Layer[];
  onHover?: (info: PickingInfo) => void;
  onClick?: (info: PickingInfo) => void;
}) {
  const overlay = useControl(() => new MapboxOverlay({ interleaved: false }));
  overlay.setProps(props);
  return null;
}

interface OpportunityMapProps {
  hexagons?: HexagonData[];
  brandLocations?: BrandLocationData[];
  existingTargetLocations?: BrandLocationData[];
  cityPolygonGeoJson?: Record<string, unknown> | null;
  centerLat?: number;
  centerLon?: number;
  hasCompetition?: boolean;
  competitorBrand?: string;
  onHexClick?: (hex: HexagonData) => void;
  onMapReady?: (map: maplibregl.Map) => void;
  drawingEnabled?: boolean;
  drawingMode?: DrawingMode;
  onDrawingModeChange?: (mode: DrawingMode) => void;
  drawnFeatureCounts?: { points: number; polygons: number };
  onClearDrawing?: () => void;
  onUndoDrawing?: () => void;
}

export function OpportunityMap({
  hexagons = [],
  brandLocations = [],
  existingTargetLocations = [],
  cityPolygonGeoJson = null,
  centerLat,
  centerLon,
  hasCompetition = false,
  competitorBrand = "",
  onHexClick,
  onMapReady,
  drawingEnabled = false,
  drawingMode = "navigate",
  onDrawingModeChange,
  drawnFeatureCounts = { points: 0, polygons: 0 },
  onClearDrawing,
  onUndoDrawing,
}: OpportunityMapProps) {
  const mapRef = useRef<MapRef>(null);
  const [hoverInfo, setHoverInfo] = useState<{
    x: number;
    y: number;
    hex?: HexagonData;
    brand?: BrandLocationData;
  } | null>(null);

  const hasResults = hexagons.length > 0;

  const initialViewState = useMemo(
    () => ({
      latitude: DEFAULT_CENTER.lat,
      longitude: DEFAULT_CENTER.lon,
      zoom: DEFAULT_ZOOM,
      pitch: 0,
      bearing: 0,
    }),
    [],
  );

  useEffect(() => {
    if (!mapRef.current || !centerLat || !centerLon) return;
    mapRef.current.flyTo({
      center: [centerLon, centerLat],
      zoom: 11,
      duration: 1500,
    });
  }, [centerLat, centerLon]);

  const renderCells = useMemo(
    () => hexagons.filter((h) => !h.is_brand_cell),
    [hexagons],
  );

  const topOpps = useMemo(() => {
    const sorted = [...renderCells].sort((a, b) => {
      const aScore = hasCompetition ? (a.opportunity_score ?? a.similarity) : a.similarity;
      const bScore = hasCompetition ? (b.opportunity_score ?? b.similarity) : b.similarity;
      return bScore - aScore;
    });
    return sorted.slice(0, Math.max(1, Math.floor(renderCells.length * 0.02)));
  }, [renderCells, hasCompetition]);

  const hexById = useMemo(
    () => new globalThis.Map(hexagons.map((h) => [h.hex_id, h])),
    [hexagons],
  );
  const brandCountByHex = useMemo(
    () =>
      new globalThis.Map(brandLocations.map((b) => [b.hex_id, b.count])),
    [brandLocations],
  );

  const handleHover = useCallback((info: PickingInfo) => {
    if (info.object && info.x !== undefined && info.y !== undefined) {
      if (info.layer?.id === "brand-locations" || info.layer?.id === "existing-target-locations") {
        setHoverInfo({ x: info.x, y: info.y, brand: info.object as BrandLocationData });
      } else {
        setHoverInfo({ x: info.x, y: info.y, hex: info.object as HexagonData });
      }
    } else {
      setHoverInfo(null);
    }
  }, []);

  const handleClick = useCallback(
    (info: PickingInfo) => {
      if (!info.object || !onHexClick) return;
      if (info.layer?.id === "h3-heatmap") {
        onHexClick(info.object as HexagonData);
      } else if (info.layer?.id === "brand-locations" || info.layer?.id === "existing-target-locations") {
        const brand = info.object as BrandLocationData;
        const matched = hexById.get(brand.hex_id);
        if (matched) onHexClick(matched);
      }
    },
    [onHexClick, hexById],
  );

  const handleMapLoad = useCallback(() => {
    if (mapRef.current && onMapReady) {
      onMapReady(mapRef.current.getMap() as unknown as maplibregl.Map);
    }
  }, [onMapReady]);

  const layers = useMemo((): Layer[] => {
    if (!hasResults) return [];
    const result: Layer[] = [];

    if (cityPolygonGeoJson) {
      result.push(
        new GeoJsonLayer({
          id: "city-boundary",
          data: {
            type: "FeatureCollection",
            features: [cityPolygonGeoJson],
          } as unknown as GeoJSON.FeatureCollection,
          getLineColor: [80, 80, 80, 200],
          getFillColor: [0, 0, 0, 0],
          lineWidthMinPixels: 2,
          pickable: false,
          stroked: true,
          filled: false,
        }),
      );
    }

    result.push(
      new H3HexagonLayer<HexagonData>({
        id: "h3-heatmap",
          data: renderCells,
        getHexagon: (d) => d.hex_id,
        getFillColor: (d) => scoreToColor(d.similarity),
        getLineColor: [255, 255, 255, 60],
        lineWidthMinPixels: 1,
        extruded: false,
        pickable: true,
        opacity: 0.7,
      }),
    );

    result.push(
      new ScatterplotLayer<BrandLocationData>({
        id: "brand-locations",
        data: brandLocations,
        getPosition: (d) => [d.lon, d.lat],
        getFillColor: (d) => {
          const maxCount = Math.max(...brandLocations.map((b) => b.count), 1);
          const t = (d.count - 1) / Math.max(maxCount - 1, 1);
          const lightness = Math.round(255 - t * 200);
          return [30, 50, lightness, 220];
        },
        getRadius: 120,
        pickable: true,
        radiusMinPixels: 4,
        radiusMaxPixels: 20,
      }),
    );

    if (existingTargetLocations.length > 0) {
      result.push(
        new ScatterplotLayer<BrandLocationData>({
          id: "existing-target-locations",
          data: existingTargetLocations,
          getPosition: (d) => [d.lon, d.lat],
          getFillColor: [100, 140, 255, 160],
          getLineColor: [30, 50, 200, 255],
          getRadius: 130,
          lineWidthMinPixels: 2,
          stroked: true,
          pickable: true,
          radiusMinPixels: 5,
          radiusMaxPixels: 22,
        }),
      );
    }

    const showCompetitorRing = Boolean(competitorBrand);
    result.push(
      new ScatterplotLayer<HexagonData>({
        id: "top-opps",
        data: topOpps,
        getPosition: (d) => [d.lon, d.lat],
        getFillColor: [0, 200, 80, 220],
        getLineColor: (d) =>
          showCompetitorRing && (d.competitor_count ?? 0) > 0
            ? [255, 255, 255, 255]
            : [0, 0, 0, 0],
        getLineWidth: (d) =>
          showCompetitorRing && (d.competitor_count ?? 0) > 0 ? 4 : 0,
        getRadius: 140,
        stroked: true,
        pickable: false,
        radiusMinPixels: 5,
        radiusMaxPixels: 20,
        lineWidthMinPixels: 3,
      }),
    );

    return result;
  }, [hasResults, renderCells, brandLocations, existingTargetLocations, topOpps, cityPolygonGeoJson]);

  const isActivelyDrawing = drawingEnabled && drawingMode !== "navigate";

  const cursorStyle = useMemo(() => {
    if (isActivelyDrawing) return "crosshair";
    return "";
  }, [isActivelyDrawing]);

  useEffect(() => {
    if (!mapRef.current) return;
    const canvas = mapRef.current.getCanvas();
    if (cursorStyle) {
      canvas.style.cursor = cursorStyle;
    } else {
      canvas.style.cursor = "";
    }
  }, [cursorStyle]);

  return (
    <div className="relative w-full h-full">
      <Map
        ref={mapRef}
        initialViewState={initialViewState}
        mapStyle={CARTO_BASEMAP}
        onLoad={handleMapLoad}
        cursor={isActivelyDrawing ? "crosshair" : undefined}
      >
        <DeckGLOverlay
          layers={layers}
          onHover={handleHover}
          onClick={handleClick}
        />
      </Map>

      {hoverInfo && (
        <div
          className="pointer-events-none absolute z-50 rounded-lg border bg-popover px-3 py-2 text-xs text-popover-foreground shadow-lg max-w-xs"
          style={{
            left: hoverInfo.x + 12,
            top: hoverInfo.y + 12,
          }}
        >
          {hoverInfo.hex && (
            <TooltipContent
              hex={hoverInfo.hex}
              hasCompetition={hasCompetition}
              competitorBrand={competitorBrand}
              existingCount={brandCountByHex.get(hoverInfo.hex.hex_id)}
            />
          )}
          {hoverInfo.brand && (
            <BrandTooltipContent
              brand={hoverInfo.brand}
              hex={hexById.get(hoverInfo.brand.hex_id)}
            />
          )}
        </div>
      )}

      {drawingEnabled && onDrawingModeChange && onClearDrawing && onUndoDrawing && (
        <DrawToolbar
          mode={drawingMode}
          onModeChange={onDrawingModeChange}
          pointCount={drawnFeatureCounts.points}
          polygonCount={drawnFeatureCounts.polygons}
          onClear={onClearDrawing}
          onUndo={onUndoDrawing}
        />
      )}

      {hasResults && (
        <MapLegend
          hasCompetition={hasCompetition}
          competitorBrand={competitorBrand}
          hasExistingTarget={existingTargetLocations.length > 0}
        />
      )}
    </div>
  );
}

function BrandTooltipContent({
  brand,
  hex,
}: {
  brand: BrandLocationData;
  hex?: HexagonData;
}) {
  const isSource = brand.is_source !== false;
  return (
    <div className="space-y-1">
      <div className="text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
        {isSource ? "Source location" : "Existing in target"}
      </div>
      {brand.address && <div className="font-medium">{brand.address}</div>}
      <div className="text-muted-foreground">{brand.hex_id}</div>
      <div className="grid grid-cols-2 gap-x-3 gap-y-0.5 pt-1">
        <span className="text-muted-foreground">Stores in cell</span>
        <span className="font-medium">{brand.count}</span>
        {hex && Number.isFinite(hex.poi_density) && (
          <>
            <span className="text-muted-foreground">POI Density</span>
            <span className="font-medium">{hex.poi_density}</span>
          </>
        )}
        {hex?.radiance != null && Number.isFinite(hex.radiance) && (
          <>
            <span className="text-muted-foreground">Economic Activity</span>
            <span className="font-medium">
              {hex.radiance.toFixed(2)} nW/cm²/sr
              <span className="ml-1 text-xs text-muted-foreground">
                ({radianceLabel(hex.radiance)})
              </span>
            </span>
          </>
        )}
      </div>
      {hex?.cat_detail && (
        <div
          className="pt-1 border-t text-muted-foreground"
          dangerouslySetInnerHTML={{ __html: hex.cat_detail }}
        />
      )}
    </div>
  );
}

function TooltipContent({
  hex,
  hasCompetition,
  competitorBrand,
  existingCount,
}: {
  hex: HexagonData;
  hasCompetition: boolean;
  competitorBrand?: string;
  existingCount?: number;
}) {
  const isExistingCell = Boolean(hex.is_brand_cell);
  const hasPoiDensity = Number.isFinite(hex.poi_density);
  const hasSimilarity = Number.isFinite(hex.similarity);
  const opportunityScore =
    typeof hex.opportunity_score === "number" ? hex.opportunity_score : null;
  const hasOpportunity = opportunityScore !== null && Number.isFinite(opportunityScore);

  return (
    <div className="space-y-1">
      {hex.address && <div className="font-medium">{hex.address}</div>}
      <div className="text-muted-foreground">{hex.hex_id}</div>
      <div className="grid grid-cols-2 gap-x-3 gap-y-0.5 pt-1">
        {isExistingCell ? (
          <>
            <span className="text-muted-foreground">Existing locations</span>
            <span className="font-medium">{existingCount ?? 0}</span>
            {hasPoiDensity && (
              <>
                <span className="text-muted-foreground">POI Density</span>
                <span className="font-medium">{hex.poi_density}</span>
              </>
            )}
            {hex.radiance != null && Number.isFinite(hex.radiance) && (
              <>
                <span className="text-muted-foreground">Economic Activity</span>
                <span className="font-medium">
                  {hex.radiance.toFixed(2)} nW/cm²/sr
                  <span className="ml-1 text-xs text-muted-foreground">
                    ({radianceLabel(hex.radiance)})
                  </span>
                </span>
              </>
            )}
          </>
        ) : (
          <>
            {hasSimilarity && (
              <>
                <span className="text-muted-foreground">Similarity</span>
                <span className="font-medium">{(hex.similarity * 100).toFixed(1)}%</span>
              </>
            )}
            {hasPoiDensity && (
              <>
                <span className="text-muted-foreground">POI Density</span>
                <span className="font-medium">{hex.poi_density}</span>
              </>
            )}
            {hex.radiance != null && Number.isFinite(hex.radiance) && (
              <>
                <span className="text-muted-foreground">Economic Activity</span>
                <span className="font-medium">
                  {hex.radiance.toFixed(2)} nW/cm²/sr
                  <span className="ml-1 text-xs text-muted-foreground">
                    ({radianceLabel(hex.radiance)})
                  </span>
                </span>
              </>
            )}
            {hasCompetition && (hex.competitor_count ?? 0) > 0 && (
              <>
                <span className="text-muted-foreground">Competition</span>
                <span className="font-medium">{hex.competitor_count}</span>
              </>
            )}
            {hex.cannibalization_risk != null && hex.nearest_store_km != null && (
              <>
                <span className="text-muted-foreground">Cannibalization</span>
                <span className="font-medium">
                  {(hex.cannibalization_risk * 100).toFixed(0)}%
                  <span className="ml-1 text-xs text-muted-foreground">
                    ({hex.nearest_store_km.toFixed(1)} km to own store)
                  </span>
                </span>
              </>
            )}
          </>
        )}
      </div>
      {!isExistingCell && (hex.competitor_count ?? 0) > 0 && hex.top_competitors && (
        <div className="pt-1 border-t text-muted-foreground">
          <span className="font-medium text-foreground">
            {competitorBrand || "Top Competitors"}: </span>
          {hex.top_competitors}
        </div>
      )}
      {hex.cat_detail && (
        <div
          className="pt-1 border-t text-muted-foreground"
          dangerouslySetInnerHTML={{ __html: hex.cat_detail }}
        />
      )}
    </div>
  );
}
