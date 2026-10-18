import React from 'react';
import { MapContainer, TileLayer } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';

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
      </MapContainer>
    </div>
  );
};

export default MapDashboard;