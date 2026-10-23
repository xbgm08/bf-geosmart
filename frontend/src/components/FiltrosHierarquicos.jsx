import React from 'react';

const FiltrosHierarquicos = ({
    hierarquia,
    sucomId, setSucomId,
    gecomId, setGecomId,
    gefinId, setGefinId,
    tier, setTier
}) => {
    const { sucoms = [], gecoms = [], gefins = [] } = hierarquia;

    const gecomsFiltrados = sucomId
        ? gecoms.filter(g => g.sucom_id === sucomId)
        : gecoms;

    const gefinsFiltrados = gefinId || gecomId
        ? gefins.filter(gf => (!gecomId || gf.gecom_id === gecomId) && (!sucomId || gf.sucom_id === sucomId))
        : sucomId
            ? gefins.filter(gf => gf.sucom_id === sucomId)
            : gefins;

    const handleSucomChange = (e) => {
        setSucomId(e.target.value);
        setGecomId("");
        setGefinId("");
    };

    const handleGecomChange = (e) => {
        setGecomId(e.target.value);
        setGefinId("");
    };

    const limparFiltros = () => {
        setSucomId("");
        setGecomId("");
        setGefinId("");
        setTier("");
    };

    return (
        <div className="bg-white px-4 py-2.5 rounded-xl shadow-sm border border-gray-200 flex flex-wrap items-end gap-3">
            <div className="flex-1 min-w-[180px]">
                <label className="block text-[11px] font-bold text-gray-600 uppercase tracking-wider mb-1">
                    1. Superintendência Comercial (SUCOM)
                </label>
                <select
                    className="w-full border-gray-300 rounded-lg p-1.5 bg-gray-50 border text-xs font-medium text-gray-800 outline-none focus:ring-2 focus:ring-[#CC092F]"
                    value={sucomId}
                    onChange={handleSucomChange}
                >
                    <option value="">Todas as SUCOMs ({sucoms.length})</option>
                    {sucoms.map(s => (
                        <option key={s.id} value={s.id}>{s.nome} ({s.id})</option>
                    ))}
                </select>
            </div>

            <div className="flex-1 min-w-[180px]">
                <label className="block text-[11px] font-bold text-gray-600 uppercase tracking-wider mb-1">
                    2. Gerência Comercial (GECOM)
                </label>
                <select
                    className="w-full border-gray-300 rounded-lg p-1.5 bg-gray-50 border text-xs font-medium text-gray-800 outline-none focus:ring-2 focus:ring-[#CC092F] disabled:opacity-50"
                    value={gecomId}
                    onChange={handleGecomChange}
                    disabled={!sucomId}
                >
                    <option value="">Todos os GECOMs ({gecomsFiltrados.length})</option>
                    {gecomsFiltrados.map(g => (
                        <option key={g.id} value={g.id}>{g.nome} ({g.id})</option>
                    ))}
                </select>
            </div>

            <div className="flex-1 min-w-[180px]">
                <label className="block text-[11px] font-bold text-gray-600 uppercase tracking-wider mb-1">
                    3. Gerência de Financiamento (GEFIN)
                </label>
                <select
                    className="w-full border-gray-300 rounded-lg p-1.5 bg-gray-50 border text-xs font-medium text-gray-800 outline-none focus:ring-2 focus:ring-[#CC092F] disabled:opacity-50"
                    value={gefinId}
                    onChange={(e) => setGefinId(e.target.value)}
                    disabled={!gecomId}
                >
                    <option value="">Todos os GEFINs ({gefinsFiltrados.length})</option>
                    {gefinsFiltrados.map(gf => (
                        <option key={gf.id} value={gf.id}>{gf.nome} - {gf.uf || "BR"}</option>
                    ))}
                </select>
            </div>

            <div className="w-40">
                <label className="block text-[11px] font-bold text-gray-600 uppercase tracking-wider mb-1">
                    Tier da Loja
                </label>
                <select
                    className="w-full border-gray-300 rounded-lg p-1.5 bg-gray-50 border text-xs font-medium text-gray-800 outline-none focus:ring-2 focus:ring-[#CC092F]"
                    value={tier}
                    onChange={(e) => setTier(e.target.value)}
                >
                    <option value="">Todos os Tiers</option>
                    <option value="OURO">Ouro</option>
                    <option value="PRATA">Prata</option>
                    <option value="BRONZE">Bronze</option>
                </select>
            </div>

            {(sucomId || gecomId || gefinId || tier) && (
                <button
                    onClick={limparFiltros}
                    className="px-3 py-1.5 text-xs font-semibold text-[#CC092F] bg-red-50 hover:bg-red-100 rounded-lg border border-red-200 transition-colors"
                >
                    Limpar Filtros
                </button>
            )}
        </div>
    );
};

export default FiltrosHierarquicos;