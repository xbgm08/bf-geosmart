import React, { useEffect, useMemo } from 'react';
import { MapContainer, TileLayer, CircleMarker, Popup, useMap } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';

// Paleta GIS de 32 cores de máximo contraste (Glasbey / Kelly) - zero cores repetidas ou confusas
const PALETA_ALTO_CONTRASTE = [
    "#E6194B", // 1. Vermelho Vivo
    "#3CB44B", // 2. Verde Esmeralda
    "#FFE119", // 3. Amarelo Ouro
    "#0082C8", // 4. Azul Royal
    "#F58231", // 5. Laranja Forte
    "#911EB4", // 6. Roxo Intenso
    "#46F0F0", // 7. Ciano Brilhante
    "#F032E6", // 8. Magenta
    "#D2F53C", // 9. Lima Neon
    "#008080", // 10. Verde-Petroleo (Teal)
    "#AA6E28", // 11. Marrom Terra
    "#800000", // 12. Bordô / Vinho
    "#808000", // 13. Verde Oliva
    "#000080", // 14. Azul Marinho Profundo
    "#FF6B6B", // 15. Coral
    "#00FF7F", // 16. Verde Primavera
    "#FFD700", // 17. Dourado Escuro
    "#FF1493", // 18. Rosa Choque (Deep Pink)
    "#1E90FF", // 19. Azul Celeste
    "#FF4500", // 20. Laranja Avermelhado
    "#2E8B57", // 21. Verde Floresta
    "#DA70D6", // 22. Orquídea
    "#B8860B", // 23. Ocre Escuro
    "#40E0D0", // 24. Turquesa
    "#DC143C", // 25. Carmesim
    "#7CFC00", // 26. Verde Grama
    "#9932CC", // 27. Violeta Escuro
    "#FF8C00", // 28. Âmbar
    "#20B2AA", // 29. Verde Mar Claro
    "#C71585", // 30. Violeta Médio
    "#556B2F", // 31. Musgo Escuro
    "#CD853F"  // 32. Bronze / Peru
];

// Subcomponente para centralizar o mapa automaticamente quando o usuário aplica um filtro
const AjustarVisaoMapa = ({ lojas }) => {
    const map = useMap();

    useEffect(() => {
        if (!lojas || lojas.length === 0) return;
        if (lojas.length > 15000) {
            map.setView([-14.2350, -51.9253], 4);
            return;
        }
        const lats = lojas.map(l => l.lat);
        const lngs = lojas.map(l => l.lng);
        const minLat = Math.min(...lats);
        const maxLat = Math.max(...lats);
        const minLng = Math.min(...lngs);
        const maxLng = Math.max(...lngs);

        map.fitBounds([[minLat, minLng], [maxLat, maxLng]], { padding: [30, 30], maxZoom: 12 });
    }, [lojas, map]);

    return null;
};

const MapDashboard = ({ lojas = [], carregando }) => {
    const centroBrasil = [-14.2350, -51.9253];

    // Distribui as cores espacialmente entre os clusters visíveis para que vizinhos tenham cores opostas
    const mapaCoresClusters = useMemo(() => {
        const somaCoords = {};
        lojas.forEach(l => {
            const cid = l.cluster_id;
            if (cid === null || cid === undefined) return;
            if (!somaCoords[cid]) {
                somaCoords[cid] = { lat: 0, lng: 0, count: 0 };
            }
            somaCoords[cid].lat += l.lat;
            somaCoords[cid].lng += l.lng;
            somaCoords[cid].count += 1;
        });

        const clusters = Object.keys(somaCoords).map(cid => ({
            id: Number(cid),
            lat: somaCoords[cid].lat / somaCoords[cid].count,
            lng: somaCoords[cid].lng / somaCoords[cid].count
        }));

        if (clusters.length === 0) return {};

        // Calcula o centroide geral da visão atual e ordena os clusters por ângulo + distância
        const mediaLat = clusters.reduce((acc, c) => acc + c.lat, 0) / clusters.length;
        const mediaLng = clusters.reduce((acc, c) => acc + c.lng, 0) / clusters.length;

        clusters.sort((a, b) => {
            const angA = Math.atan2(a.lat - mediaLat, a.lng - mediaLng);
            const angB = Math.atan2(b.lat - mediaLat, b.lng - mediaLng);
            return angA - angB;
        });

        // Atribui cores dando saltos primos (passo 7) na paleta para afastar ainda mais clusters adjacentes
        const dicionarioCores = {};
        const totalPaleta = PALETA_ALTO_CONTRASTE.length;
        clusters.forEach((c, idx) => {
            const indiceCor = (idx * 7) % totalPaleta;
            dicionarioCores[c.id] = PALETA_ALTO_CONTRASTE[indiceCor];
        });

        return dicionarioCores;
    }, [lojas]);

    const obterCorCluster = (clusterId) => {
        if (clusterId === null || clusterId === undefined) return "#6b7280";
        return mapaCoresClusters[clusterId] || PALETA_ALTO_CONTRASTE[Number(clusterId) % PALETA_ALTO_CONTRASTE.length];
    };

    return (
        <div className="w-full h-full bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden relative">
            {carregando && (
                <div className="absolute inset-0 bg-white/80 z-[1000] flex items-center justify-center">
                    <div className="text-center">
                        <div className="w-8 h-8 border-4 border-[#CC092F] border-t-transparent rounded-full animate-spin mx-auto mb-2"></div>
                        <p className="text-xs font-bold text-gray-700">Consultando Azure Cosmos DB...</p>
                    </div>
                </div>
            )}

            <MapContainer
                center={centroBrasil}
                zoom={4}
                preferCanvas={true}
                className="w-full h-full z-0"
            >
               <TileLayer
                    attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
                    url="https://tile.openstreetmap.org/{z}/{x}/{y}.png"
                />

                <AjustarVisaoMapa lojas={lojas} />

                {lojas.map((loja) => {
                    const cor = obterCorCluster(loja.cluster_id);
                    return (
                        <CircleMarker
                            key={loja.cnpj}
                            center={[loja.lat, loja.lng]}
                            radius={5.5}
                            pathOptions={{
                                color: "#1f2937",      // Contorno escuro fino destaca cores claras (amarelo, lima, ciano) no mapa claro
                                fillColor: cor,
                                fillOpacity: 0.92,
                                weight: 0.8
                            }}
                        >
                            <Popup>
                                <div className="font-sans min-w-[200px]">
                                    <span className="text-[10px] font-bold px-2 py-0.5 rounded bg-gray-100 text-gray-700 float-right">
                                        {loja.tier_loja}
                                    </span>
                                    <h3 className="font-bold text-gray-900 text-sm pr-12">{loja.nome}</h3>
                                    <p className="text-[11px] text-gray-500 mb-2">
                                        CNPJ: {loja.cnpj} | {loja.municipio} - {loja.uf}
                                    </p>
                                    <div className="border-t border-gray-100 pt-1.5 space-y-1 text-xs">
                                        <p className="text-gray-700 flex items-center gap-1.5">
                                            Cluster K-Means:
                                            <span
                                                className="inline-block w-3 h-3 rounded-full border border-gray-400"
                                                style={{ backgroundColor: cor }}
                                            ></span>
                                            <strong>#{loja.cluster_id}</strong>
                                        </p>
                                        <p className="text-gray-700">
                                            Carteira GEFIN: <strong>{loja.gefin_id}</strong>
                                        </p>
                                        <p className="font-bold text-emerald-700">
                                            Produção Média: {Number(loja.producao_media || 0).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' })}
                                        </p>
                                    </div>
                                </div>
                            </Popup>
                        </CircleMarker>
                    );
                })}
            </MapContainer>
        </div>
    );
};

export default MapDashboard;