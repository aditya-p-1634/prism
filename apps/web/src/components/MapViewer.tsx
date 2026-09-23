"use client";

import React, { useState } from "react";
import { Shield, AlertTriangle, Home, Building2, Navigation, Layers, Info } from "lucide-react";

interface MapViewerProps {
  layers: any;
  selectedEntity: any;
  onSelectEntity: (entity: any) => void;
}

export default function MapViewer({ layers, selectedEntity, onSelectEntity }: MapViewerProps) {
  const [showFlood, setShowFlood] = useState(true);
  const [showRedZones, setShowRedZones] = useState(true);
  const [showHabitations, setShowHabitations] = useState(true);
  const [showDestinations, setShowDestinations] = useState(true);
  const [showRoads, setShowRoads] = useState(true);
  const [showRoutes, setShowRoutes] = useState(true);

  // Coordinate normalizer for Vayu River Basin (77.10 - 77.30 lon, 28.50 - 28.70 lat)
  // Mapping into SVG viewport (viewBox 0 0 1000 800)
  const minLon = 77.12;
  const maxLon = 77.28;
  const minLat = 28.53;
  const maxLat = 28.69;

  const toSvgX = (lon: number) => {
    return ((lon - minLon) / (maxLon - minLon)) * 900 + 50;
  };

  const toSvgY = (lat: number) => {
    // Invert Y for latitude
    return 750 - ((lat - minLat) / (maxLat - minLat)) * 700;
  };

  const polyToSvgPoints = (coords: number[][]) => {
    return coords.map(([lon, lat]) => `${toSvgX(lon)},${toSvgY(lat)}`).join(" ");
  };

  return (
    <div className="relative w-full h-[580px] lg:h-[720px] rounded-xl overflow-hidden border border-slate-800 bg-[#060910] shadow-2xl flex flex-col">
      {/* Top Map Toolbar */}
      <div className="absolute top-4 left-4 z-20 flex flex-wrap gap-2">
        <div className="flex items-center space-x-1 p-1 bg-slate-900/90 backdrop-blur-md rounded-lg border border-slate-700/60 shadow-lg text-xs">
          <button
            onClick={() => setShowFlood(!showFlood)}
            className={`px-2.5 py-1 rounded transition-all font-mono flex items-center space-x-1.5 ${
              showFlood ? "bg-blue-600/30 text-blue-300 border border-blue-500/40" : "text-slate-400 hover:text-slate-200"
            }`}
          >
            <span className="w-2 h-2 rounded-full bg-blue-400"></span>
            <span>Flood Extent</span>
          </button>

          <button
            onClick={() => setShowRedZones(!showRedZones)}
            className={`px-2.5 py-1 rounded transition-all font-mono flex items-center space-x-1.5 ${
              showRedZones ? "bg-red-600/30 text-red-300 border border-red-500/40" : "text-slate-400 hover:text-slate-200"
            }`}
          >
            <span className="w-2 h-2 rounded-full bg-red-500 animate-ping"></span>
            <span>Red Zones</span>
          </button>

          <button
            onClick={() => setShowHabitations(!showHabitations)}
            className={`px-2.5 py-1 rounded transition-all font-mono flex items-center space-x-1.5 ${
              showHabitations ? "bg-amber-600/30 text-amber-300 border border-amber-500/40" : "text-slate-400 hover:text-slate-200"
            }`}
          >
            <Home className="w-3 h-3 text-amber-400" />
            <span>Habitations</span>
          </button>

          <button
            onClick={() => setShowDestinations(!showDestinations)}
            className={`px-2.5 py-1 rounded transition-all font-mono flex items-center space-x-1.5 ${
              showDestinations ? "bg-emerald-600/30 text-emerald-300 border border-emerald-500/40" : "text-slate-400 hover:text-slate-200"
            }`}
          >
            <Building2 className="w-3 h-3 text-emerald-400" />
            <span>Destinations</span>
          </button>

          <button
            onClick={() => setShowRoutes(!showRoutes)}
            className={`px-2.5 py-1 rounded transition-all font-mono flex items-center space-x-1.5 ${
              showRoutes ? "bg-indigo-600/30 text-indigo-300 border border-indigo-500/40" : "text-slate-400 hover:text-slate-200"
            }`}
          >
            <Navigation className="w-3 h-3 text-indigo-400" />
            <span>Convoy Routes</span>
          </button>
        </div>
      </div>

      {/* Map Legend / Scale */}
      <div className="absolute bottom-4 left-4 z-20 p-2.5 bg-slate-900/90 backdrop-blur-md rounded-lg border border-slate-700/60 shadow-lg text-[11px] font-mono space-y-1.5 hidden md:block">
        <div className="text-slate-400 font-semibold mb-1 flex items-center space-x-1">
          <Layers className="w-3 h-3 text-cyan-400" />
          <span>VAYU BASIN OPERATIONAL MAP</span>
        </div>
        <div className="flex items-center space-x-2">
          <span className="w-3 h-3 rounded bg-red-600/60 border border-red-500"></span>
          <span className="text-slate-300">Active Red Zone (Immediate Hazard)</span>
        </div>
        <div className="flex items-center space-x-2">
          <span className="w-3 h-3 rounded bg-blue-600/40 border border-blue-400"></span>
          <span className="text-slate-300">River Inundation Corridor</span>
        </div>
        <div className="flex items-center space-x-2">
          <span className="w-3 h-0.5 bg-emerald-500"></span>
          <span className="text-slate-300">Open Safe Road Corridor</span>
        </div>
        <div className="flex items-center space-x-2">
          <span className="w-3 h-0.5 bg-red-500 border-dashed"></span>
          <span className="text-slate-300">Closed / Submerged Bridge (BRIDGE_01)</span>
        </div>
        <div className="text-slate-500 pt-1 border-t border-slate-800 text-[10px]">
          CRS: WGS84 (4326) / Metric: UTM 43N
        </div>
      </div>

      {/* Interactive Vector GIS Canvas */}
      <div className="flex-1 w-full h-full relative cursor-crosshair">
        <svg viewBox="0 0 1000 800" className="w-full h-full select-none">
          <defs>
            {/* Grid Pattern for Command Center feel */}
            <pattern id="grid" width="40" height="40" patternUnits="userSpaceOnUse">
              <path d="M 40 0 L 0 0 0 40" fill="none" stroke="rgba(30, 41, 59, 0.4)" strokeWidth="0.8" />
            </pattern>
            {/* Red Zone Hatching */}
            <pattern id="redHatch" width="8" height="8" patternTransform="rotate(45 0 0)" patternUnits="userSpaceOnUse">
              <line x1="0" y1="0" x2="0" y2="8" stroke="#ef4444" strokeWidth="2.5" strokeOpacity="0.4" />
            </pattern>
          </defs>

          {/* Background Grid */}
          <rect width="1000" height="800" fill="#070b12" />
          <rect width="1000" height="800" fill="url(#grid)" />

          {/* 1. Flood Extents */}
          {showFlood && layers?.flood_polygons?.features?.map((f: any, idx: number) => {
            const coords = f.geometry.coordinates[0];
            return (
              <g key={`flood-${idx}`}>
                <polygon
                  points={polyToSvgPoints(coords)}
                  fill="rgba(37, 99, 235, 0.35)"
                  stroke="#3b82f6"
                  strokeWidth="2"
                  className="transition-all duration-700"
                />
              </g>
            );
          })}

          {/* 2. Red Zones */}
          {showRedZones && layers?.red_zones?.features?.map((f: any, idx: number) => {
            const coords = f.geometry.coordinates[0];
            return (
              <g key={`rz-${idx}`}>
                <polygon
                  points={polyToSvgPoints(coords)}
                  fill="url(#redHatch)"
                  stroke="#ef4444"
                  strokeWidth="2.5"
                  className="animate-pulse"
                />
              </g>
            );
          })}

          {/* 3. Road Network Segments */}
          {showRoads && layers?.road_segments?.features?.map((s: any, idx: number) => {
            const coords = s.geometry.coordinates;
            const x1 = toSvgX(coords[0][0]);
            const y1 = toSvgY(coords[0][1]);
            const x2 = toSvgX(coords[1][0]);
            const y2 = toSvgY(coords[1][1]);
            const isClosed = s.properties.operational_status === "CLOSED";
            const isBridge = s.properties.is_bridge;

            return (
              <g key={`road-${idx}`}>
                <line
                  x1={x1}
                  y1={y1}
                  x2={x2}
                  y2={y2}
                  stroke={isClosed ? "#ef4444" : (isBridge ? "#f59e0b" : "#10b981")}
                  strokeWidth={isBridge ? "4" : "2.5"}
                  strokeDasharray={isClosed ? "6,4" : "none"}
                  strokeOpacity="0.85"
                />
                {isBridge && (
                  <circle cx={(x1+x2)/2} cy={(y1+y2)/2} r="4" fill={isClosed ? "#ef4444" : "#f59e0b"} />
                )}
              </g>
            );
          })}

          {/* 4. Active Convoy Routes */}
          {showRoutes && layers?.active_routes?.features?.map((r: any, idx: number) => {
            const coords = r.geometry.coordinates;
            const pts = coords.map(([lon, lat]: [number, number]) => `${toSvgX(lon)},${toSvgY(lat)}`).join(" ");
            return (
              <g key={`route-${idx}`}>
                <polyline
                  points={pts}
                  fill="none"
                  stroke="#60a5fa"
                  strokeWidth="3.5"
                  strokeOpacity="0.75"
                  strokeDasharray="8,6"
                  className="animate-pulse"
                />
              </g>
            );
          })}

          {/* 5. Habitations */}
          {showHabitations && layers?.habitations?.features?.map((h: any, idx: number) => {
            const coords = h.geometry.coordinates[0];
            const centroidX = coords.reduce((acc: number, c: number[]) => acc + toSvgX(c[0]), 0) / coords.length;
            const centroidY = coords.reduce((acc: number, c: number[]) => acc + toSvgY(c[1]), 0) / coords.length;
            const isImmediate = h.properties.immediate_priority_count > 0;
            const isSelected = selectedEntity?.id === h.properties.id;

            return (
              <g
                key={`hab-${idx}`}
                onClick={() => onSelectEntity({ type: "HABITATION", data: h.properties })}
                className="cursor-pointer group"
              >
                <polygon
                  points={polyToSvgPoints(coords)}
                  fill={isImmediate ? "rgba(239, 68, 68, 0.4)" : "rgba(245, 158, 11, 0.3)"}
                  stroke={isImmediate ? "#ef4444" : "#f59e0b"}
                  strokeWidth={isSelected ? "3" : "1.5"}
                  className="transition-all group-hover:fill-opacity-70"
                />
                {/* Habitation Pin Marker */}
                <circle
                  cx={centroidX}
                  cy={centroidY}
                  r={isSelected ? "9" : "7"}
                  fill={isImmediate ? "#ef4444" : "#f59e0b"}
                  stroke="#ffffff"
                  strokeWidth="2"
                  className="shadow-md"
                />
                <text
                  x={centroidX + 12}
                  y={centroidY + 4}
                  fill="#f1f5f9"
                  fontSize="12"
                  fontWeight="bold"
                  fontFamily="monospace"
                  className="pointer-events-none drop-shadow-md"
                >
                  {h.properties.name}
                </text>
                <text
                  x={centroidX + 12}
                  y={centroidY + 18}
                  fill="#94a3b8"
                  fontSize="10"
                  fontFamily="monospace"
                  className="pointer-events-none"
                >
                  Pop: {h.properties.population} | Imm: {h.properties.immediate_priority_count}
                </text>
              </g>
            );
          })}

          {/* 6. Candidate Destinations */}
          {showDestinations && layers?.destinations?.features?.map((d: any, idx: number) => {
            const [lon, lat] = d.geometry.coordinates;
            const cx = toSvgX(lon);
            const cy = toSvgY(lat);
            const isSelected = selectedEntity?.id === d.properties.id;
            const isSafe = d.properties.is_safe;

            return (
              <g
                key={`dest-${idx}`}
                onClick={() => onSelectEntity({ type: "DESTINATION", data: d.properties })}
                className="cursor-pointer group"
              >
                <circle
                  cx={cx}
                  cy={cy}
                  r={isSelected ? "14" : "11"}
                  fill={isSafe ? "#10b981" : "#64748b"}
                  stroke="#ffffff"
                  strokeWidth="2.5"
                  className="shadow-lg transition-transform group-hover:scale-110"
                />
                <text
                  x={cx}
                  y={cy + 4}
                  textAnchor="middle"
                  fill="#ffffff"
                  fontSize="10"
                  fontWeight="bold"
                  fontFamily="monospace"
                  className="pointer-events-none"
                >
                  {d.properties.code.replace("DEST_", "D")}
                </text>
                <text
                  x={cx}
                  y={cy - 16}
                  textAnchor="middle"
                  fill="#34d399"
                  fontSize="11"
                  fontWeight="bold"
                  fontFamily="monospace"
                  className="pointer-events-none drop-shadow-md"
                >
                  {d.properties.name}
                </text>
                <text
                  x={cx}
                  y={cy + 24}
                  textAnchor="middle"
                  fill="#94a3b8"
                  fontSize="9.5"
                  fontFamily="monospace"
                  className="pointer-events-none"
                >
                  Cap: {d.properties.effective_capacity} | Rem: {d.properties.remaining_capacity}
                </text>
                {d.properties.bottleneck_resource === "WATER" && (
                  <text
                    x={cx}
                    y={cy + 36}
                    textAnchor="middle"
                    fill="#38bdf8"
                    fontSize="9"
                    fontWeight="bold"
                    fontFamily="monospace"
                  >
                    ⚠️ Limit: WATER
                  </text>
                )}
              </g>
            );
          })}
        </svg>
      </div>
    </div>
  );
}
