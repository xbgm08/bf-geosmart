import React, { useState, useEffect } from 'react';
import MapDashboard from './components/MapDashboard';
import FiltrosHierarquicos from './components/FiltrosHierarquicos';
import KpiCards from './components/KpiCards';
import GraficosAnaliticos from './components/GraficosAnaliticos';

const API_BASE_URL = "http://localhost:8000";

function App() {
  const [hierarquia, setHierarquia] = useState({ sucoms: [], gecoms: [], gefins: [] });
  const [sucomId, setSucomId] = useState("");
  const [gecomId, setGecomId] = useState("");
  const [gefinId, setGefinId] = useState("");
  const [tier, setTier] = useState("");

  const [dadosPainel, setDadosPainel] = useState({
    kpis: {},
    evolucao_mensal: [],
    funil: {},
    lojas: []
  });
  const [carregando, setCarregando] = useState(true);

  useEffect(() => {
    fetch(`${API_BASE_URL}/painel/hierarquia`)
      .then(res => res.json())
      .then(data => setHierarquia(data))
      .catch(err => console.error("Erro ao carregar hierarquia:", err));
  }, []);

  useEffect(() => {
    setCarregando(true);
    const params = new URLSearchParams();
    if (sucomId) params.append("sucom_id", sucomId);
    if (gecomId) params.append("gecom_id", gecomId);
    if (gefinId) params.append("gefin_id", gefinId);
    if (tier) params.append("tier", tier);

    fetch(`${API_BASE_URL}/painel/dados?${params.toString()}`)
      .then(res => res.json())
      .then(data => {
        setDadosPainel(data);
        setCarregando(false);
      })
      .catch(err => {
        console.error("Erro ao consultar dados do painel:", err);
        setCarregando(false);
      });
  }, [sucomId, gecomId, gefinId, tier]);

  return (
    <div className="h-screen bg-gray-100 p-3 flex flex-col overflow-hidden font-sans">
      <div className="max-w-[1600px] mx-auto w-full flex flex-col h-full space-y-2.5">

        <header className="bg-gradient-to-r from-[#CC092F] to-[#990022] text-white px-5 py-2.5 rounded-xl shadow-md flex items-center justify-between shrink-0">
          <div className="flex items-center gap-4">
            <div className="bg-white text-[#CC092F] font-black text-sm px-3 py-1 rounded-lg tracking-tight shadow-sm">
              bradesco <span className="font-normal">financiamentos</span>
            </div>
            <div className="h-6 w-px bg-white/30"></div>
            <div>
              <h1 className="text-lg font-extrabold tracking-tight leading-none">BF GeoSmart</h1>
            </div>
          </div>

          <div className="flex items-center gap-3">
            <div className="text-right hidden sm:block">
              <p className="text-[11px] font-bold uppercase tracking-wider text-red-100">Projeto Integrador IV</p>
              <p className="text-[10px] text-red-200">Big Data para Negócios</p>
            </div>
            <div className="bg-white/15 border border-white/25 px-3 py-1 rounded-lg text-xs font-bold tracking-wider">
              FATEC IPIRANGA
            </div>
          </div>
        </header>

        <div className="shrink-0">
          <FiltrosHierarquicos
            hierarquia={hierarquia}
            sucomId={sucomId} setSucomId={setSucomId}
            gecomId={gecomId} setGecomId={setGecomId}
            gefinId={gefinId} setGefinId={setGefinId}
            tier={tier} setTier={setTier}
          />
        </div>

        <KpiCards kpis={dadosPainel.kpis} />

        <div className="flex-1 min-h-0 grid grid-cols-12 gap-3">
          <div className="col-span-7 h-full min-h-0">
            <MapDashboard lojas={dadosPainel.lojas} carregando={carregando} />
          </div>
          <div className="col-span-5 h-full min-h-0">
            <GraficosAnaliticos
              evolucaoMensal={dadosPainel.evolucao_mensal}
              funil={dadosPainel.funil}
            />
          </div>
        </div>

      </div>
    </div>
  );
}

export default App;