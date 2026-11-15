"use client";

import React, { useEffect, useMemo, useRef, useState } from "react";
import maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import { Compass, Layers, Map as MapIcon, Satellite, ShieldAlert } from "lucide-react";

type FeatureCollection = { type: "FeatureCollection"; features: Array<Record<string, any>> };
type Basemap = "satellite" | "hybrid" | "streets";
type OverlayKey = "study" | "flood" | "predicted" | "risk" | "roads" | "routes" | "habitations" | "destinations";

interface MapViewerProps {
  layers: Record<string, FeatureCollection | undefined>;
  selectedEntity: any;
  onSelectEntity: (entity: any) => void;
  hideControls?: boolean;
}

const EMPTY_COLLECTION: FeatureCollection = { type: "FeatureCollection", features: [] };
const EMPTY_GEOJSON = EMPTY_COLLECTION as any;
const TILE_URLS = {
  satellite: process.env.NEXT_PUBLIC_MAP_SATELLITE_TILES || "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
  streets: process.env.NEXT_PUBLIC_MAP_STREETS_TILES || "https://tile.openstreetmap.org/{z}/{x}/{y}.png",
  labels: process.env.NEXT_PUBLIC_MAP_LABEL_TILES || "https://services.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}",
};
const BASEMAP_ATTRIBUTION = "Imagery: Esri, Maxar, Earthstar Geographics, and the GIS User Community · Streets: © OpenStreetMap contributors";
const LAYER_DEFINITIONS: Array<{ key: OverlayKey; label: string; color: string }> = [
  { key: "study", label: "Study boundary", color: "#67e8f9" },
  { key: "flood", label: "Current flood", color: "#38bdf8" },
  { key: "predicted", label: "Predicted flood", color: "#22d3ee" },
  { key: "risk", label: "High-risk zones", color: "#ef4444" },
  { key: "roads", label: "Roads & blocked bridges", color: "#f59e0b" },
  { key: "routes", label: "Evacuation routes", color: "#a78bfa" },
  { key: "habitations", label: "Habitations", color: "#fbbf24" },
  { key: "destinations", label: "Shelters", color: "#34d399" },
];
const CLICKABLE_LAYERS = [
  ["risk-fill", "RED_ZONE"], ["flood-fill", "FLOOD_EXTENT"], ["predicted-fill", "PREDICTED_FLOOD_EXTENT"],
  ["roads-line", "ROAD_SEGMENT"], ["routes-line", "ROUTE"], ["habitations-fill", "HABITATION"],
  ["habitation-points", "HABITATION"], ["destinations-point", "DESTINATION"],
] as const;

function collection(value: FeatureCollection | undefined): FeatureCollection {
  return value && value.type === "FeatureCollection" ? value : EMPTY_COLLECTION;
}

function geometryCoordinates(geometry: any, output: Array<[number, number]>) {
  if (!geometry?.coordinates) return;
  const walk = (coords: any): void => {
    if (Array.isArray(coords) && typeof coords[0] === "number" && typeof coords[1] === "number") {
      output.push([coords[0], coords[1]]);
    } else if (Array.isArray(coords)) coords.forEach(walk);
  };
  walk(geometry.coordinates);
}

function boundsForCollections(collections: FeatureCollection[]): maplibregl.LngLatBounds | null {
  const coordinates: Array<[number, number]> = [];
  collections.forEach((fc) => fc.features.forEach((feature) => geometryCoordinates(feature.geometry, coordinates)));
  if (!coordinates.length) return null;
  const bounds = new maplibregl.LngLatBounds(coordinates[0], coordinates[0]);
  coordinates.slice(1).forEach((coordinate) => bounds.extend(coordinate));
  return bounds;
}

function escapeHtml(value: unknown): string {
  return String(value ?? "").replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;").replaceAll('"', "&quot;").replaceAll("'", "&#039;");
}

function popupMarkup(type: string, properties: Record<string, any>) {
  const title = properties.name || properties.code || properties.segment_code || properties.id || type;
  const rows = Object.entries(properties).filter(([key]) => !["geom", "geometry"].includes(key)).slice(0, 7)
    .map(([key, value]) => `<div class="prism-popup-row"><span>${escapeHtml(key.replaceAll("_", " "))}</span><strong>${escapeHtml(typeof value === "object" ? JSON.stringify(value) : value)}</strong></div>`).join("");
  return `<div class="prism-popup"><div class="prism-popup-type">${escapeHtml(type.replaceAll("_", " "))}</div><div class="prism-popup-title">${escapeHtml(title)}</div>${rows}</div>`;
}

function mapStyle(): maplibregl.StyleSpecification {
  return {
    version: 8,
    name: "PRISM disaster intelligence",
    sources: {
      "basemap-satellite": { type: "raster", tiles: [TILE_URLS.satellite], tileSize: 256, maxzoom: 19 },
      "basemap-streets": { type: "raster", tiles: [TILE_URLS.streets], tileSize: 256, maxzoom: 19 },
      "basemap-labels": { type: "raster", tiles: [TILE_URLS.labels], tileSize: 256, maxzoom: 19 },
      "study-area": { type: "geojson", data: EMPTY_GEOJSON }, flood: { type: "geojson", data: EMPTY_GEOJSON },
      predicted: { type: "geojson", data: EMPTY_GEOJSON }, risk: { type: "geojson", data: EMPTY_GEOJSON },
      roads: { type: "geojson", data: EMPTY_GEOJSON }, routes: { type: "geojson", data: EMPTY_GEOJSON },
      habitations: { type: "geojson", data: EMPTY_GEOJSON }, "habitation-points": { type: "geojson", data: EMPTY_GEOJSON },
      destinations: { type: "geojson", data: EMPTY_GEOJSON },
    },
    layers: [
      { id: "basemap-satellite", type: "raster", source: "basemap-satellite", layout: { visibility: "visible" } },
      { id: "basemap-streets", type: "raster", source: "basemap-streets", layout: { visibility: "none" } },
      { id: "basemap-labels", type: "raster", source: "basemap-labels", layout: { visibility: "none" }, paint: { "raster-opacity": 0.9 } },
      { id: "study-boundary", type: "line", source: "study-area", paint: { "line-color": "#67e8f9", "line-width": 2, "line-dasharray": [2, 2], "line-opacity": 0.9 } },
      { id: "flood-fill", type: "fill", source: "flood", paint: { "fill-color": "#0284c7", "fill-opacity": 0.28 } },
      { id: "flood-outline", type: "line", source: "flood", paint: { "line-color": "#38bdf8", "line-width": 1.5, "line-opacity": 0.95 } },
      { id: "predicted-fill", type: "fill", source: "predicted", paint: { "fill-color": "#22d3ee", "fill-opacity": 0.16 } },
      { id: "predicted-outline", type: "line", source: "predicted", paint: { "line-color": "#22d3ee", "line-width": 2, "line-dasharray": [2, 2], "line-opacity": 0.95 } },
      { id: "risk-fill", type: "fill", source: "risk", paint: { "fill-color": "#ef4444", "fill-opacity": 0.2 } },
      { id: "risk-outline", type: "line", source: "risk", paint: { "line-color": "#ef4444", "line-width": 2, "line-dasharray": [1.5, 1.5], "line-opacity": 0.95 } },
      { id: "roads-line", type: "line", source: "roads", filter: ["!=", ["get", "operational_status"], "CLOSED"], paint: { "line-color": ["case", ["==", ["get", "is_bridge"], true], "#f59e0b", "#e5e7eb"], "line-width": ["case", ["==", ["get", "is_bridge"], true], 3.5, 1.8], "line-opacity": 0.86 } },
      { id: "roads-closed-line", type: "line", source: "roads", filter: ["==", ["get", "operational_status"], "CLOSED"], paint: { "line-color": "#ef4444", "line-width": 4, "line-opacity": 0.95, "line-dasharray": [1, 1] } },
      { id: "routes-line", type: "line", source: "routes", paint: { "line-color": ["case", ["==", ["get", "is_viable"], false], "#f97316", "#a78bfa"], "line-width": 3, "line-opacity": 0.9, "line-dasharray": [2, 1.2] } },
      { id: "habitations-fill", type: "fill", source: "habitations", paint: { "fill-color": ["case", ["==", ["get", "highest_priority"], "IMMEDIATE"], "#f97316", "#fbbf24"], "fill-opacity": 0.24 } },
      { id: "habitations-outline", type: "line", source: "habitations", paint: { "line-color": ["case", ["==", ["get", "highest_priority"], "IMMEDIATE"], "#ef4444", "#fbbf24"], "line-width": 1.5 } },
      { id: "habitation-points", type: "circle", source: "habitation-points", paint: { "circle-color": ["case", ["==", ["get", "highest_priority"], "IMMEDIATE"], "#ef4444", "#f59e0b"], "circle-radius": 7, "circle-stroke-color": "#ffffff", "circle-stroke-width": 1.5 } },
      { id: "habitation-labels", type: "symbol", source: "habitation-points", layout: { "text-field": ["get", "name"], "text-size": 11, "text-offset": [0.8, 0], "text-anchor": "left", "text-allow-overlap": false }, paint: { "text-color": "#ffffff", "text-halo-color": "#111827", "text-halo-width": 1.5 } },
      { id: "destinations-point", type: "circle", source: "destinations", paint: { "circle-color": ["case", ["==", ["get", "is_safe"], true], "#10b981", "#64748b"], "circle-radius": 9, "circle-stroke-color": "#ffffff", "circle-stroke-width": 2 } },
      { id: "destination-labels", type: "symbol", source: "destinations", layout: { "text-field": ["get", "code"], "text-size": 11, "text-offset": [0, 1.5], "text-anchor": "top", "text-allow-overlap": false }, paint: { "text-color": "#d1fae5", "text-halo-color": "#064e3b", "text-halo-width": 1.5 } },
    ],
  };
}

export default function MapViewer({ layers, selectedEntity, onSelectEntity, hideControls = false }: MapViewerProps) {
  const mapContainer = useRef<HTMLDivElement>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const popupRef = useRef<maplibregl.Popup | null>(null);
  const onSelectEntityRef = useRef(onSelectEntity);
  const [mapReady, setMapReady] = useState(false);
  const [mapError, setMapError] = useState<string | null>(null);
  const [basemap, setBasemap] = useState<Basemap>("satellite");
  const [visible, setVisible] = useState<Record<OverlayKey, boolean>>({ study: true, flood: true, predicted: true, risk: true, roads: true, routes: true, habitations: true, destinations: true });

  const sourceData = useMemo(() => ({
    "study-area": collection(layers.study_area_boundary), flood: collection(layers.flood_polygons), predicted: collection(layers.predicted_flood_polygons),
    risk: collection(layers.red_zones), roads: collection(layers.road_segments), routes: collection(layers.active_routes), habitations: collection(layers.habitations),
    "habitation-points": collection(layers.habitation_points), destinations: collection(layers.destinations),
  }), [layers]);

  useEffect(() => {
    onSelectEntityRef.current = onSelectEntity;
  }, [onSelectEntity]);

  useEffect(() => {
    if (!mapContainer.current || mapRef.current) return;
    const map = new maplibregl.Map({ container: mapContainer.current, style: mapStyle(), center: [0, 0], zoom: 2, attributionControl: false, dragRotate: false, touchPitch: false });
    mapRef.current = map;
    map.addControl(new maplibregl.NavigationControl({ showCompass: true }), "top-right");
    map.addControl(new maplibregl.FullscreenControl(), "top-right");
    map.addControl(new maplibregl.ScaleControl({ maxWidth: 120, unit: "metric" }), "bottom-right");
    map.addControl(new maplibregl.AttributionControl({ compact: true, customAttribution: BASEMAP_ATTRIBUTION }), "bottom-right");
    map.on("error", (event) => { const message = event.error?.message || "Map tiles or style could not be loaded."; if (!message.toLowerCase().includes("tile")) setMapError(message); });
    map.on("load", () => setMapReady(true));
    const clickHandlers = CLICKABLE_LAYERS.map(([layerId, type]) => {
      const handler = (event: maplibregl.MapLayerMouseEvent) => {
        const feature = event.features?.[0];
        if (!feature) return;
        const properties = (feature.properties || {}) as Record<string, any>;
        onSelectEntityRef.current({ type, id: properties.id || feature.id, properties, data: properties });
        popupRef.current?.remove();
        popupRef.current = new maplibregl.Popup({ closeButton: true, closeOnClick: true, maxWidth: "300px", className: "prism-map-popup" }).setLngLat(event.lngLat).setHTML(popupMarkup(type, properties)).addTo(map);
      };
      map.on("click", layerId, handler);
      return [layerId, handler] as const;
    });
    const cursorHandlers = CLICKABLE_LAYERS.map(([layerId]) => {
      const enter = () => { map.getCanvas().style.cursor = "pointer"; };
      const leave = () => { map.getCanvas().style.cursor = ""; };
      map.on("mouseenter", layerId, enter); map.on("mouseleave", layerId, leave);
      return [layerId, enter, leave] as const;
    });
    return () => {
      clickHandlers.forEach(([layerId, handler]) => map.off("click", layerId, handler));
      cursorHandlers.forEach(([layerId, enter, leave]) => { map.off("mouseenter", layerId, enter); map.off("mouseleave", layerId, leave); });
      popupRef.current?.remove(); popupRef.current = null; map.remove(); mapRef.current = null;
    };
  }, []);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !mapReady) return;
    Object.entries(sourceData).forEach(([sourceId, data]) => (map.getSource(sourceId) as maplibregl.GeoJSONSource | undefined)?.setData(data as any));
    const bounds = boundsForCollections(Object.values(sourceData));
    if (bounds) map.fitBounds(bounds, { padding: { top: 90, right: 70, bottom: 70, left: 70 }, maxZoom: 14, duration: 0 });
  }, [sourceData, mapReady]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !mapReady) return;
    const visibleBaseLayers: Record<Basemap, string[]> = { satellite: ["basemap-satellite"], hybrid: ["basemap-satellite", "basemap-labels"], streets: ["basemap-streets"] };
    ["basemap-satellite", "basemap-streets", "basemap-labels"].forEach((layerId) => map.setLayoutProperty(layerId, "visibility", visibleBaseLayers[basemap].includes(layerId) ? "visible" : "none"));
  }, [basemap, mapReady]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !mapReady) return;
    const layerMap: Record<OverlayKey, string[]> = {
      study: ["study-boundary"], flood: ["flood-fill", "flood-outline"], predicted: ["predicted-fill", "predicted-outline"], risk: ["risk-fill", "risk-outline"], roads: ["roads-line", "roads-closed-line"], routes: ["routes-line"],
      habitations: ["habitations-fill", "habitations-outline", "habitation-points", "habitation-labels"], destinations: ["destinations-point", "destination-labels"],
    };
    Object.entries(layerMap).forEach(([key, layerIds]) => layerIds.forEach((layerId) => map.setLayoutProperty(layerId, "visibility", visible[key as OverlayKey] ? "visible" : "none")));
  }, [visible, mapReady]);

  const toggle = (key: OverlayKey) => setVisible((current) => ({ ...current, [key]: !current[key] }));

  return (
    <div className="relative h-[580px] w-full overflow-hidden rounded-xl border border-slate-700 bg-slate-950 shadow-2xl lg:h-[720px]">
      <div ref={mapContainer} className="h-full w-full" aria-label="Interactive PRISM geographic disaster map" />
      <div className="absolute left-4 top-4 z-10 w-[min(440px,calc(100%-2rem))] rounded-xl border border-slate-200/30 bg-slate-950/85 p-3 text-xs text-white shadow-xl backdrop-blur-md">
        <div className="flex items-center justify-between gap-3 border-b border-white/15 pb-2"><div className="flex items-center gap-2 font-semibold"><MapIcon className="h-4 w-4 text-cyan-300" /> PRISM geographic intelligence</div><span className="font-mono text-[10px] text-cyan-200">WGS84 / EPSG:4326</span></div>
        <div className="mt-2 flex flex-wrap gap-1.5" aria-label="Basemap selection">{(["satellite", "hybrid", "streets"] as Basemap[]).map((option) => <button key={option} type="button" aria-pressed={basemap === option} onClick={() => setBasemap(option)} className={`rounded-md px-2.5 py-1 font-mono text-[10px] capitalize transition ${basemap === option ? "bg-cyan-500/80 text-slate-950" : "bg-white/10 text-slate-200 hover:bg-white/20"}`}>{option === "satellite" ? <Satellite className="mr-1 inline h-3 w-3" /> : null}{option}</button>)}</div>
        {!hideControls && <div className="mt-2 grid grid-cols-2 gap-1.5" aria-label="Disaster intelligence layers">{LAYER_DEFINITIONS.map((layer) => <button key={layer.key} type="button" aria-pressed={visible[layer.key]} onClick={() => toggle(layer.key)} className={`flex items-center gap-2 rounded-md px-2 py-1.5 text-left font-mono text-[10px] transition ${visible[layer.key] ? "bg-white/10 text-white" : "text-slate-500 line-through"}`}><span className="h-2.5 w-2.5 shrink-0 rounded-full" style={{ backgroundColor: layer.color, opacity: visible[layer.key] ? 1 : 0.35 }} />{layer.label}</button>)}</div>}
      </div>
      <div className="pointer-events-none absolute right-4 top-4 z-10 flex items-center gap-2 rounded-lg border border-slate-200/30 bg-slate-950/75 px-2.5 py-2 text-[10px] font-mono text-slate-100 backdrop-blur-md"><Compass className="h-4 w-4 text-cyan-300" /> N</div>
      <div className="pointer-events-none absolute bottom-4 left-4 z-10 max-w-[270px] rounded-xl border border-slate-200/25 bg-slate-950/85 p-3 text-[10px] text-slate-100 shadow-xl backdrop-blur-md"><div className="mb-2 flex items-center gap-2 font-semibold uppercase tracking-wider text-slate-200"><Layers className="h-3.5 w-3.5 text-cyan-300" /> Map legend</div><div className="grid grid-cols-2 gap-x-3 gap-y-1.5"><span><i className="mr-1 inline-block h-2.5 w-2.5 rounded bg-sky-500/70" />Current flood</span><span><i className="mr-1 inline-block h-2.5 w-2.5 rounded bg-cyan-300/60" />Prediction</span><span><i className="mr-1 inline-block h-2.5 w-2.5 rounded bg-red-500/70" />High risk</span><span><i className="mr-1 inline-block h-2.5 w-2.5 rounded-full bg-amber-400" />Habitation</span><span><i className="mr-1 inline-block h-2.5 w-2.5 rounded-full bg-emerald-400" />Shelter</span><span><i className="mr-1 inline-block h-0.5 w-3 bg-red-500" />Blocked road</span></div><div className="mt-2 border-t border-white/15 pt-2 text-slate-400">Click a feature for details · {basemap === "streets" ? "© OpenStreetMap contributors" : "Imagery © Esri and partners"}</div></div>
      {mapError && <div className="absolute bottom-4 right-4 z-10 flex max-w-xs items-center gap-2 rounded-lg border border-amber-500/50 bg-slate-950/90 px-3 py-2 text-[10px] text-amber-100 shadow-xl"><ShieldAlert className="h-4 w-4 shrink-0 text-amber-300" /> Basemap unavailable. Use Streets fallback.</div>}
    </div>
  );
}
