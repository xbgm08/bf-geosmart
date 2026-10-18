import React from 'react';

const hierarquiaMock = {
  "SUCOM São Paulo": {
    "GECOM Capital": ["GEFIN Centro", "GEFIN Paulista"],
    "GECOM Interior": ["GEFIN Campinas", "GEFIN Sorocaba"]
  },
  "SUCOM Rio de Janeiro": {
    "GECOM Litoral": ["GEFIN Copacabana", "GEFIN Barra"],
    "GECOM Interior": ["GEFIN Petrópolis", "GEFIN Volta Redonda"]
  }
};

const FiltrosHierarquicos = ({ 
  sucomSelecionada, setSucomSelecionada, 
  gecomSelecionada, setGecomSelecionada, 
  gefinSelecionada, setGefinSelecionada 
}) => {

  const sucoms = Object.keys(hierarquiaMock);
  const gecoms = sucomSelecionada ? Object.keys(hierarquiaMock[sucomSelecionada]) : [];
  const gefins = gecomSelecionada ? hierarquiaMock[sucomSelecionada][gecomSelecionada] : [];

  const handleSucomChange = (e) => {
    setSucomSelecionada(e.target.value);
    setGecomSelecionada(""); 
    setGefinSelecionada("");
  };

  const handleGecomChange = (e) => {
    setGecomSelecionada(e.target.value);
    setGefinSelecionada(""); 
  };

  return (
    <div className="bg-white p-3 rounded-xl shadow-sm border border-gray-200 flex gap-4">
      <div className="flex-1">
        <label className="block text-xs font-semibold text-gray-700 mb-1">SUCOM</label>
        <select
          className="w-full border-gray-300 rounded-md shadow-sm p-1.5 bg-gray-50 border outline-none text-sm"
          value={sucomSelecionada}
          onChange={handleSucomChange}
        >
          <option value="">Todas as SUCOMs</option>
          {sucoms.map(sucom => <option key={sucom} value={sucom}>{sucom}</option>)}
        </select>
      </div>

      <div className="flex-1">
        <label className="block text-xs font-semibold text-gray-700 mb-1">GECOM</label>
        <select
          className="w-full border-gray-300 rounded-md shadow-sm p-1.5 bg-gray-50 border outline-none text-sm disabled:opacity-50"
          value={gecomSelecionada}
          onChange={handleGecomChange}
          disabled={!sucomSelecionada}
        >
          <option value="">Todos os GECOMs</option>
          {gecoms.map(gecom => <option key={gecom} value={gecom}>{gecom}</option>)}
        </select>
      </div>

      <div className="flex-1">
        <label className="block text-xs font-semibold text-gray-700 mb-1">GEFIN</label>
        <select
          className="w-full border-gray-300 rounded-md shadow-sm p-1.5 bg-gray-50 border outline-none text-sm disabled:opacity-50"
          value={gefinSelecionada}
          onChange={(e) => setGefinSelecionada(e.target.value)}
          disabled={!gecomSelecionada}
        >
          <option value="">Todos os GEFINs</option>
          {gefins.map(gefin => <option key={gefin} value={gefin}>{gefin}</option>)}
        </select>
      </div>
    </div>
  );
};

export default FiltrosHierarquicos;