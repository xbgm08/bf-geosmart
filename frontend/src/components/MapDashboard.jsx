import React from 'react';
import { MapContainer, TileLayer, CircleMarker, Popup } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';

const lojasMock = [
  { id: 1, nome: "Loja A - Centro", lat: -23.5505, lng: -46.6333, cluster_id: 0, producao: "R$ 150.000", sucom: "SUCOM São Paulo", gecom: "GECOM Capital", gefin: "GEFIN Centro" },
  { id: 2, nome: "Loja B - Zona Sul", lat: -23.6500, lng: -46.7000, cluster_id: 0, producao: "R$ 85.000", sucom: "SUCOM São Paulo", gecom: "GECOM Capital", gefin: "GEFIN Paulista" },
  { id: 3, nome: "Loja C - Campinas", lat: -22.9099, lng: -47.0626, cluster_id: 1, producao: "R$ 210.000", sucom: "SUCOM São Paulo", gecom: "GECOM Interior", gefin: "GEFIN Campinas" },
  { id: 4, nome: "Loja D - Sorocaba", lat: -23.5015, lng: -47.4581, cluster_id: 1, producao: "R$ 95.000", sucom: "SUCOM São Paulo", gecom: "GECOM Interior", gefin: "GEFIN Sorocaba" },
  { id: 5, nome: "Loja E - Rio de Janeiro", lat: -22.9068, lng: -43.1729, cluster_id: 2, producao: "R$ 300.000", sucom: "SUCOM Rio de Janeiro", gecom: "GECOM Litoral", gefin: "GEFIN Copacabana" }
];

const getColorByCluster = (clusterId) => {
  if (clusterId === null || clusterId === undefined) return "#6b7280";
  const goldenRatioConjugate = 0.618033988749895;
  let h = (clusterId * goldenRatioConjugate) % 1;
  let s = 0.7;
  let l = 0.5;

  const hue2rgb = (p, q, t) => {
    if (t < 0) t += 1;
    if (t > 1) t -= 1;
    if (t < 1/6) return p + (q - p) * 6 * t;
    if (t < 1/2) return q;
    if (t < 2/3) return p + (q - p) * (2/3 - t) * 6;
    return p;
  };

  const q = l < 0.5 ? l * (1 + s) : l + s - l * s;
  const p = 2 * l - q;
  const r = Math.round(hue2rgb(p, q, h + 1/3) * 255);
  const g = Math.round(hue2rgb(p, q, h) * 255);
  const b = Math.round(hue2rgb(p, q, h - 1/3) * 255);

  const toHex = x => {
    const hex = x.toString(16);
    return hex.length === 1 ? '0' + hex : hex;
  };

  return `#${toHex(r)}${toHex(g)}${toHex(b)}`;
};

const MapDashboard = ({ sucomSelecionada, gecomSelecionada, gefinSelecionada }) => {
  const centroBrasil = [-14.2350, -51.9253];

  const lojasFiltradas = lojasMock.filter(loja => {
    const matchSucom = sucomSelecionada ? loja.sucom === sucomSelecionada : true;
    const matchGecom = gecomSelecionada ? loja.gecom === gecomSelecionada : true;
    const matchGefin = gefinSelecionada ? loja.gefin === gefinSelecionada : true;

    return matchSucom && matchGecom && matchGefin;
  });

  return (
    <div className="w-full h-full bg-white rounded-xl shadow-lg border border-gray-200 overflow-hidden">
      <MapContainer 
        center={centroBrasil} 
        zoom={5} 
        className="w-full h-full z-0"
      >
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        
        {lojasFiltradas.map((loja) => (
          <CircleMarker
            key={loja.id}
            center={[loja.lat, loja.lng]}
            radius={8}
            pathOptions={{ 
              color: getColorByCluster(loja.cluster_id), 
              fillColor: getColorByCluster(loja.cluster_id), 
              fillOpacity: 0.7 
            }}
          >
            <Popup>
              <div className="font-sans">
                <h3 className="font-bold text-gray-800">{loja.nome}</h3>
                <p className="text-xs text-gray-500 mb-1">{loja.sucom} | {loja.gecom} | {loja.gefin}</p>
                <p className="text-sm text-gray-700">Território (Cluster): <strong>{loja.cluster_id}</strong></p>
                <p className="text-sm font-semibold text-green-600 mt-1">Produção: {loja.producao}</p>
              </div>
            </Popup>
          </CircleMarker>
        ))}
      </MapContainer>
    </div>
  );
};

export default MapDashboard;