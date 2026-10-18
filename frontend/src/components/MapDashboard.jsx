import React from 'react';
import { MapContainer, TileLayer, CircleMarker, Popup } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';

// Dados simulandos
const lojasMock = [
  { id: 1, nome: "Loja A - Centro", lat: -23.5505, lng: -46.6333, cluster_id: 0, producao: "R$ 150.000" },
  { id: 2, nome: "Loja B - Zona Sul", lat: -23.6500, lng: -46.7000, cluster_id: 0, producao: "R$ 85.000" },
  { id: 3, nome: "Loja C - Campinas", lat: -22.9099, lng: -47.0626, cluster_id: 1, producao: "R$ 210.000" },
  { id: 4, nome: "Loja D - Jundiaí", lat: -23.1857, lng: -46.8978, cluster_id: 1, producao: "R$ 95.000" },
  { id: 5, nome: "Loja E - Rio de Janeiro", lat: -22.9068, lng: -43.1729, cluster_id: 2, producao: "R$ 300.000" }
];

// Função para atribuir uma cor a cada território
const getColorByCluster = (clusterId) => {
  // Se o ID for inválido ou nulo, retorna cinza
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

const MapDashboard = () => {
  // Coordenada central para o Brasil inteiro no mapa
  const centroBrasil = [-14.2350, -51.9253];

  return (
    <div className="w-full h-[600px] bg-white rounded-xl shadow-lg border border-gray-200 overflow-hidden">
      <MapContainer 
        center={centroBrasil} 
        zoom={5} 
        className="w-full h-full z-0"
      >
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        
        {/* Renderiza os pontos no mapa iterando sobre os dados simulados das lojas. */}
        {lojasMock.map((loja) => (
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
            {/* Tooltip interativo que exibe os KPIs da loja ao receber um clique do usuário. */}
            <Popup>
              <div className="font-sans">
                <h3 className="font-bold text-gray-800">{loja.nome}</h3>
                <p className="text-sm text-gray-600">Território (Cluster): {loja.cluster_id}</p>
                <p className="text-sm font-semibold text-green-600">Produção Paga: {loja.producao}</p>
              </div>
            </Popup>
          </CircleMarker>
        ))}
      </MapContainer>
    </div>
  );
};

export default MapDashboard;