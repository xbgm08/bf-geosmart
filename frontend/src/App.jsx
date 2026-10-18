import React, { useState } from 'react';
import MapDashboard from './components/MapDashboard';
import FiltrosHierarquicos from './components/FiltrosHierarquicos';

function App() {
  const [sucomSelecionada, setSucomSelecionada] = useState("");
  const [gecomSelecionada, setGecomSelecionada] = useState("");
  const [gefinSelecionada, setGefinSelecionada] = useState("");

  return (
    <div className="h-screen bg-gray-50 p-4 flex flex-col">
      <div className="max-w-7xl mx-auto w-full flex flex-col h-full space-y-4">
        
        <header className="flex items-center justify-between shrink-0">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">BF GeoSmart</h1>
            <p className="text-xs text-gray-500">Dashboard de Inteligência Territorial</p>
          </div>
        </header>

        <div className="shrink-0">
          <FiltrosHierarquicos 
            sucomSelecionada={sucomSelecionada} 
            setSucomSelecionada={setSucomSelecionada} 
            gecomSelecionada={gecomSelecionada}
            setGecomSelecionada={setGecomSelecionada}
            gefinSelecionada={gefinSelecionada}
            setGefinSelecionada={setGefinSelecionada}
          />
        </div>

        <div className="flex-1 min-h-0">
          <MapDashboard 
            sucomSelecionada={sucomSelecionada}
            gecomSelecionada={gecomSelecionada}
            gefinSelecionada={gefinSelecionada}
          />
        </div>

      </div>
    </div>
  );
}

export default App;