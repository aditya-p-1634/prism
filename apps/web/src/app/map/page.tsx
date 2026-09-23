"use client";

import React, { useState, useEffect } from "react";
import MapViewer from "@/components/MapViewer";
import { getDashboardOverview } from "@/lib/api";
import { useSnapshot } from "@/lib/snapshot-context";
import {
  Map as MapIcon,
  Layers,
  Info,
  CheckCircle2,
  AlertTriangle,
  Building2,
  Users,
  Navigation,
  Eye,
  EyeOff
} from "lucide-react";

export default function GISWorkspacePage() {
  const { snapshotId, activeSnapshot, isBaseline } = useSnapshot();
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedEntity, setSelectedEntity] = useState<any>(null);

  // Layer Visibility
  const [visibleLayers, setVisibleLayers] = useState({
    flood: true,
    redZones: true,
    habitations: true,
    destinations: true,
    roads: true,
    routes: true
  });

  const toggleLayer = (layerKey: keyof typeof visibleLayers) => {
    setVisibleLayers((prev) => ({ ...prev, [layerKey]: !prev[layerKey] }));
  };

  useEffect(() => {
    const fetchMapData = async () => {
      try {
        setLoading(true);
        setError(null);
        const res = await getDashboardOverview(snapshotId);
        setData(res.data);
      } catch (err: any) {
        setError(err.message || "Failed to load GIS spatial layers");
      } finally {
        setLoading(false);
      }
    };
    fetchMapData();
  }, [snapshotId]);

  if (loading && !data) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center min-h-[500px] space-y-3">
        <div className="w-10 h-10 border-4 border-cyan-500 border-t-transparent rounded-full animate-spin" />
        <div className="text-slate-400 font-mono text-xs">
          LOADING GIS SPATIAL VECTOR LAYERS...
        </div>
      </div>
    );
  }

  if (error && !data) {
    return (
      <div className="p-6 rounded-2xl bg-rose-950/30 border border-rose-800/60 max-w-lg mx-auto text-center space-y-3">
        <AlertTriangle className="w-8 h-8 text-rose-400 mx-auto" />
        <h3 className="text-sm font-bold text-rose-200">GIS Layers Unavailable</h3>
        <p className="text-xs text-rose-300 font-mono">{error}</p>
      </div>
    );
  }

  const rawLayers = data?.layers || {};
  // Filter layers by visibility toggles
  const activeLayers = {
    flood_polygons: visibleLayers.flood ? rawLayers.flood_polygons : { type: "FeatureCollection", features: [] },
    red_zones: visibleLayers.redZones ? rawLayers.red_zones : { type: "FeatureCollection", features: [] },
    habitations: visibleLayers.habitations ? rawLayers.habitations : { type: "FeatureCollection", features: [] },
    destinations: visibleLayers.destinations ? rawLayers.destinations : { type: "FeatureCollection", features: [] },
    road_segments: visibleLayers.roads ? rawLayers.road_segments : { type: "FeatureCollection", features: [] },
    active_routes: visibleLayers.routes ? rawLayers.active_routes : { type: "FeatureCollection", features: [] }
  };

  return (
    <div className="flex flex-col gap-4 flex-1 h-full max-w-[1900px] mx-auto w-full">
      {/* Top Header & Layer Toggles Bar */}
      <div className="p-3.5 rounded-2xl bg-[#0c121d] border border-slate-800 shadow-xl flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center space-x-3">
          <div className="w-9 h-9 rounded-xl bg-cyan-950/80 border border-cyan-800/60 flex items-center justify-center">
            <MapIcon className="w-4 h-4 text-cyan-400" />
          </div>
          <div>
            <h1 className="text-sm font-bold text-white tracking-wide">
              Dedicated GIS Spatial Workspace
            </h1>
            <div className="text-[11px] text-slate-400 font-mono">
              Vayu River Basin (EPSG:4326) | Active Snapshot:{" "}
              <span className="text-cyan-400 font-semibold">{snapshotId}</span>
            </div>
          </div>
        </div>

        {/* Quick Layer Switchers */}
        <div className="flex items-center flex-wrap gap-2 text-xs font-mono">
          <button
            onClick={() => toggleLayer("flood")}
            className={`px-2.5 py-1 rounded-lg border transition-all flex items-center space-x-1.5 ${
              visibleLayers.flood
                ? "bg-blue-950/70 border-blue-600 text-blue-300 font-semibold"
                : "bg-slate-900 border-slate-800 text-slate-500 opacity-60"
            }`}
          >
            {visibleLayers.flood ? <Eye className="w-3.5 h-3.5" /> : <EyeOff className="w-3.5 h-3.5" />}
            <span>Flood Extent</span>
          </button>

          <button
            onClick={() => toggleLayer("redZones")}
            className={`px-2.5 py-1 rounded-lg border transition-all flex items-center space-x-1.5 ${
              visibleLayers.redZones
                ? "bg-red-950/70 border-red-600 text-red-300 font-semibold"
                : "bg-slate-900 border-slate-800 text-slate-500 opacity-60"
            }`}
          >
            {visibleLayers.redZones ? <Eye className="w-3.5 h-3.5" /> : <EyeOff className="w-3.5 h-3.5" />}
            <span>Red Zones</span>
          </button>

          <button
            onClick={() => toggleLayer("habitations")}
            className={`px-2.5 py-1 rounded-lg border transition-all flex items-center space-x-1.5 ${
              visibleLayers.habitations
                ? "bg-amber-950/70 border-amber-600 text-amber-300 font-semibold"
                : "bg-slate-900 border-slate-800 text-slate-500 opacity-60"
            }`}
          >
            {visibleLayers.habitations ? <Eye className="w-3.5 h-3.5" /> : <EyeOff className="w-3.5 h-3.5" />}
            <span>Habitations</span>
          </button>

          <button
            onClick={() => toggleLayer("destinations")}
            className={`px-2.5 py-1 rounded-lg border transition-all flex items-center space-x-1.5 ${
              visibleLayers.destinations
                ? "bg-emerald-950/70 border-emerald-600 text-emerald-300 font-semibold"
                : "bg-slate-900 border-slate-800 text-slate-500 opacity-60"
            }`}
          >
            {visibleLayers.destinations ? <Eye className="w-3.5 h-3.5" /> : <EyeOff className="w-3.5 h-3.5" />}
            <span>Destinations</span>
          </button>

          <button
            onClick={() => toggleLayer("roads")}
            className={`px-2.5 py-1 rounded-lg border transition-all flex items-center space-x-1.5 ${
              visibleLayers.roads
                ? "bg-slate-800 border-slate-600 text-slate-200 font-semibold"
                : "bg-slate-900 border-slate-800 text-slate-500 opacity-60"
            }`}
          >
            {visibleLayers.roads ? <Eye className="w-3.5 h-3.5" /> : <EyeOff className="w-3.5 h-3.5" />}
            <span>Roads & Bridges</span>
          </button>

          <button
            onClick={() => toggleLayer("routes")}
            className={`px-2.5 py-1 rounded-lg border transition-all flex items-center space-x-1.5 ${
              visibleLayers.routes
                ? "bg-cyan-950/70 border-cyan-600 text-cyan-300 font-semibold"
                : "bg-slate-900 border-slate-800 text-slate-500 opacity-60"
            }`}
          >
            {visibleLayers.routes ? <Eye className="w-3.5 h-3.5" /> : <EyeOff className="w-3.5 h-3.5" />}
            <span>Evac Routes</span>
          </button>
        </div>
      </div>

      {/* Main Map Canvas + Right Inspector Drawer */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-4 flex-1 min-h-[640px]">
        {/* Dominant GIS Canvas */}
        <div className="lg:col-span-8 xl:col-span-9 flex flex-col rounded-2xl border border-slate-800 bg-[#0c121d] overflow-hidden shadow-2xl p-2 relative">
          <MapViewer
            layers={activeLayers}
            selectedEntity={selectedEntity}
            onSelectEntity={(entity) => setSelectedEntity(entity)}
          />

          {/* Map Symbology Floating Overlay */}
          <div className="absolute bottom-4 left-4 bg-slate-950/85 backdrop-blur-md border border-slate-800 rounded-xl p-3 text-[11px] font-mono space-y-1.5 shadow-xl pointer-events-none">
            <div className="font-semibold text-slate-300 border-b border-slate-800 pb-1">
              CARTOGRAPHIC SYMBOLOGY
            </div>
            <div className="flex items-center space-x-2">
              <span className="w-3 h-3 rounded bg-blue-500/50 border border-blue-400" />
              <span className="text-slate-300">Active River/Flood Extent</span>
            </div>
            <div className="flex items-center space-x-2">
              <span className="w-3 h-3 rounded bg-rose-500/40 border border-rose-500" />
              <span className="text-slate-300">Hazard Red Zone</span>
            </div>
            <div className="flex items-center space-x-2">
              <span className="w-3 h-3 rounded-full bg-amber-400" />
              <span className="text-slate-300">Habitation Centroid</span>
            </div>
            <div className="flex items-center space-x-2">
              <span className="w-3 h-3 rounded-full bg-emerald-400" />
              <span className="text-slate-300">Candidate Destination / Shelter</span>
            </div>
            <div className="flex items-center space-x-2">
              <span className="w-3 h-1 bg-cyan-400" />
              <span className="text-slate-300">Viable Evacuation Route</span>
            </div>
          </div>
        </div>

        {/* Right Tactical Entity Inspector Drawer */}
        <div className="lg:col-span-4 xl:col-span-3 flex flex-col rounded-2xl border border-slate-800 bg-[#0c121d] shadow-xl p-4 space-y-4">
          <div className="flex items-center space-x-2 border-b border-slate-800 pb-2">
            <Info className="w-4 h-4 text-cyan-400" />
            <h2 className="text-xs font-bold uppercase tracking-wider text-slate-200">
              Spatial Entity Inspector
            </h2>
          </div>

          {selectedEntity ? (
            <div className="space-y-3 flex-1 overflow-y-auto pr-1">
              <div className="p-3 rounded-xl bg-slate-900 border border-slate-800 space-y-1">
                <span className="text-[10px] font-mono text-cyan-400 uppercase font-semibold">
                  {selectedEntity.type || "ENTITY"}
                </span>
                <div className="text-sm font-bold text-white">
                  {selectedEntity.properties?.name || selectedEntity.properties?.code || selectedEntity.id}
                </div>
                <div className="text-xs text-slate-400 font-mono">
                  ID: {selectedEntity.properties?.id || selectedEntity.id}
                </div>
              </div>

              {/* Entity Property List */}
              <div className="p-3 rounded-xl bg-slate-950/60 border border-slate-800/80 space-y-2 text-xs font-mono">
                {Object.entries(selectedEntity.properties || {})
                  .filter(([k]) => !["id", "geom", "location_geojson"].includes(k))
                  .map(([k, v]) => (
                    <div key={k} className="flex items-start justify-between border-b border-slate-900 pb-1">
                      <span className="text-slate-400 capitalize">{k.replace(/_/g, " ")}:</span>
                      <span className="text-slate-200 font-semibold text-right max-w-[60%] truncate">
                        {typeof v === "object" ? JSON.stringify(v) : String(v)}
                      </span>
                    </div>
                  ))}
              </div>
            </div>
          ) : (
            <div className="flex-1 flex flex-col items-center justify-center text-center p-6 space-y-2 text-slate-500">
              <MapIcon className="w-8 h-8 opacity-40" />
              <p className="text-xs font-mono">
                Click on any Habitation, Destination, Red Zone, or Route on the map to inspect its real-time topological properties.
              </p>
            </div>
          )}

          {/* Quick Context Summary */}
          <div className="p-3 rounded-xl bg-slate-900/60 border border-slate-800 text-[11px] font-mono text-slate-400">
            <div>Study Area: Vayu River Basin</div>
            <div>CRS: EPSG:4326 (WGS 84)</div>
            <div>Mode: Planar Topological Network</div>
          </div>
        </div>
      </div>
    </div>
  );
}
