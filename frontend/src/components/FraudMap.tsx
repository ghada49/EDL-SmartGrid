// frontend/src/components/FraudMap.tsx
import React, { useEffect, useMemo, useState } from "react";
import {
  MapContainer,
  TileLayer,
  CircleMarker,
  Popup,
  Polyline,
  useMap,
} from "react-leaflet";
import L from "leaflet";
import "leaflet/dist/leaflet.css";

export type FraudPoint = {
  case_id: number;
  building_id?: number | null;
  lat: number;
  lng: number;
  status?: string;
  outcome?: string | null;
  feedback_label?: string | null;
};

type FraudMapProps = {
  points: FraudPoint[];
  loading: boolean;
  error: string | null;
  homeCoords?: { lat: number; lng: number } | null;
  showRoutes?: boolean;
  showHomeBase?: boolean;
};

// ---------------- FIT BOUNDS FIX --------------------

const FitBounds: React.FC<{ coords: [number, number][] }> = ({ coords }) => {
  const map = useMap();
  const hasFit = React.useRef(false);

  useEffect(() => {
    if (!coords.length) return;

    // NEW: wait for Leaflet to finish rendering
    map.whenReady(() => {
      if (hasFit.current) return;
      const bounds = L.latLngBounds(coords);
      map.fitBounds(bounds, { padding: [40, 40] });
      hasFit.current = true;
    });
  }, [coords, map]);

  return null;
};

// -----------------------------------------------------

const FraudMap: React.FC<FraudMapProps> = ({
  points,
  loading,
  error,
  homeCoords,
  showRoutes = true,
  showHomeBase = true,
}) => {
  const defaultCenter: [number, number] = [33.8938, 35.5018];
  const showEmpty = !loading && !error && points.length === 0;

  const [routeCoords, setRouteCoords] = useState<[number, number][][]>([]);
  const [routeError, setRouteError] = useState<string | null>(null);

  const routerBase =
    (import.meta as any)?.env?.VITE_OSRM_BASE_URL?.replace(/\/$/, "") ||
    "https://router.project-osrm.org";

  const orderedPoints = useMemo(() => {
    return [...points].sort((a, b) => a.case_id - b.case_id);
  }, [points]);

  const fitPoints = useMemo(() => {
    const coords: [number, number][] = orderedPoints.map((p) => [p.lat, p.lng]);
    if (homeCoords) coords.push([homeCoords.lat, homeCoords.lng]);
    return coords;
  }, [orderedPoints, homeCoords]);

  // ---------------- ROUTE FETCH --------------------

  useEffect(() => {
    if (!showRoutes) {
      setRouteCoords([]);
      setRouteError(null);
      return;
    }

    if (!homeCoords || !orderedPoints.length) {
      setRouteCoords([]);
      setRouteError(
        homeCoords ? null : "Set your Home Base to see driving paths."
      );
      return;
    }

    let cancelled = false;
    setRouteError(null);

    const fetchRoutes = async () => {
      const segments: [number, number][][] = [];

      for (const point of orderedPoints) {
        const url = `${routerBase}/route/v1/driving/${homeCoords.lng},${homeCoords.lat};${point.lng},${point.lat}?overview=full&geometries=geojson`;

        try {
          const res = await fetch(url);
          if (!res.ok) throw new Error(`OSRM ${res.status}`);
          const data = await res.json();

          const geom = data?.routes?.[0]?.geometry;

          if (!geom || geom.type !== "LineString")
            throw new Error("No route available");

          const coords = geom.coordinates.map(
            ([lng, lat]: [number, number]) => [lat, lng]
          ) as [number, number][];

          segments.push(coords);
        } catch {
          // fallback straight line
          segments.push([
            [homeCoords.lat, homeCoords.lng],
            [point.lat, point.lng],
          ]);
          setRouteError(
            "Route service unavailable; showing straight-line path."
          );
        }
      }

      if (!cancelled) setRouteCoords(segments);
    };

    fetchRoutes();
    return () => {
      cancelled = true;
    };
  }, [homeCoords, orderedPoints]);

  // -----------------------------------------------------

  return (
    <div style={{ width: "100%" }}>
      {loading && (
        <p className="eco-muted">Loading assigned cases on the map...</p>
      )}
      {error && (
        <div className="eco-alert warn" style={{ marginBottom: 12 }}>
          {error}
        </div>
      )}
      {showEmpty && <p className="eco-muted">No assigned cases to display yet.</p>}

      {routeError && (
        <p className="eco-alert warn" style={{ marginBottom: 8 }}>
          {routeError}
        </p>
      )}

      <div style={{ width: "100%", height: 420 }}>
        <MapContainer
          center={defaultCenter}
          zoom={12}
          style={{ width: "100%", height: "100%" }}
          scrollWheelZoom={true}
        >
          <TileLayer
            attribution="&copy; OpenStreetMap contributors"
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          />

          {fitPoints.length > 0 && <FitBounds coords={fitPoints} />}

          {/* POINTS */}
          {points.map((p) => (
            <CircleMarker
              key={`${p.case_id}-${p.building_id ?? "n/a"}`}
              center={[p.lat, p.lng]}
              radius={12}
              pathOptions={{
                color: "#7f1d1d",
                fillColor: "#ef4444",
                fillOpacity: 0.95,
                weight: 3,
              }}
            >
              <Popup>
                <strong>Case #{p.case_id}</strong>
                <br />
                {p.lat.toFixed(4)} , {p.lng.toFixed(4)}
              </Popup>
            </CircleMarker>
          ))}

          {/* ROUTES */}
          {showRoutes &&
            routeCoords.map((segment, idx) => (
              <Polyline
                key={`route-${idx}`}
                positions={segment}
                pathOptions={{
                  color: "#0f62fe",
                  weight: 5,
                  dashArray: "10 4",
                  opacity: 0.9,
                }}
              />
            ))}

          {/* HOME BASE */}
          {showHomeBase && homeCoords && (
            <CircleMarker
              center={[homeCoords.lat, homeCoords.lng]}
              radius={10}
              pathOptions={{
                color: "#065f46",
                fillColor: "#16a34a",
                fillOpacity: 0.95,
                weight: 3,
                dashArray: "6 3",
              }}
            >
              <Popup>
                <strong>Home Base</strong>
                <br />
                {homeCoords.lat.toFixed(4)}, {homeCoords.lng.toFixed(4)}
              </Popup>
            </CircleMarker>
          )}
        </MapContainer>
      </div>
    </div>
  );
};

export default FraudMap;
