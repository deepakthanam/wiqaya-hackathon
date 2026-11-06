"use client";
import "leaflet/dist/leaflet.css";
import { CircleMarker, MapContainer, TileLayer, Tooltip } from "react-leaflet";
import { isSuppressed } from "@/lib/api";
import { colourFor, range } from "./colour";

export default function DistrictMap({ rows, onTileError }: { rows: any[]; onTileError: () => void }) {
  const [min, max] = range(rows);
  return (
    <MapContainer bounds={[[22.9, 51.9], [24.75, 55.95]]} scrollWheelZoom={false} style={{ height: 420, width: "100%", borderRadius: 8 }}>
      <TileLayer
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        eventHandlers={{ tileerror: onTileError }}
      />
      {rows.map((r) => {
        const sup = isSuppressed(r.unmet_need_per_1000);
        return (
          <CircleMarker
            key={r.district_id}
            center={[r.lat, r.lon]}
            radius={11}
            pathOptions={{ color: sup ? "#6B6259" : "#2E2A26", weight: 1, dashArray: sup ? "3 3" : undefined, fillColor: sup ? "#F7F4F0" : colourFor(r.unmet_need_per_1000, max, min), fillOpacity: 0.85 }}
          >
            <Tooltip>
              <strong>{r.name}</strong>
              <br />
              {sup ? "suppressed (n<11)" : `Unmet need ${r.unmet_need_per_1000} per 1,000 · n ${r.n}`}
              <br />
              Simulated cohort
            </Tooltip>
          </CircleMarker>
        );
      })}
    </MapContainer>
  );
}
