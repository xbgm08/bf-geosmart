import React from 'react';

const formatarMoedaCompacta = (valor) => {
    if (!valor) return "R$ 0";
    if (valor >= 1_000_000_000) return `R$ ${(valor / 1_000_000_000).toFixed(2)} Bi`;
    if (valor >= 1_000_000) return `R$ ${(valor / 1_000_000).toFixed(2)} Mi`;
    return valor.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL', maximumFractionDigits: 0 });
};

const KpiCards = ({ kpis }) => {
    const atingimento = kpis?.atingimento_pct || 0;
    const corAtingimento = atingimento >= 100
        ? "text-emerald-600 bg-emerald-50 border-emerald-200"
        : atingimento >= 85
            ? "text-amber-600 bg-amber-50 border-amber-200"
            : "text-red-600 bg-red-50 border-red-200";

    return (
        <div className="grid grid-cols-4 gap-3 shrink-0">
            <div className="bg-white p-3 rounded-xl shadow-sm border border-gray-200 border-l-4 border-l-[#CC092F]">
                <p className="text-[11px] font-bold text-gray-500 uppercase">Produção Paga Total</p>
                <p className="text-xl font-extrabold text-gray-900 mt-0.5">
                    {formatarMoedaCompacta(kpis?.producao_paga_total)}
                </p>
                <p className="text-[10px] text-gray-400">Acumulado das lojas filtradas</p>
            </div>

            <div className="bg-white p-3 rounded-xl shadow-sm border border-gray-200 border-l-4 border-l-gray-700">
                <p className="text-[11px] font-bold text-gray-500 uppercase">Meta Total Estabelecida</p>
                <p className="text-xl font-extrabold text-gray-900 mt-0.5">
                    {formatarMoedaCompacta(kpis?.meta_total)}
                </p>
                <p className="text-[10px] text-gray-400">Objetivo comercial da carteira</p>
            </div>

            <div className="bg-white p-3 rounded-xl shadow-sm border border-gray-200 border-l-4 border-l-emerald-600 flex items-center justify-between">
                <div>
                    <p className="text-[11px] font-bold text-gray-500 uppercase">Atingimento Global</p>
                    <p className="text-xl font-extrabold text-gray-900 mt-0.5">{atingimento}%</p>
                    <p className="text-[10px] text-gray-400">Soma Realizado / Soma Meta</p>
                </div>
                <span className={`text-xs font-bold px-2.5 py-1 rounded-full border ${corAtingimento}`}>
                    {atingimento >= 100 ? "Meta Batida" : "Em Curso"}
                </span>
            </div>

            <div className="bg-white p-3 rounded-xl shadow-sm border border-gray-200 border-l-4 border-l-blue-600">
                <p className="text-[11px] font-bold text-gray-500 uppercase">Malha & Territórios K-Means</p>
                <div className="flex items-baseline gap-2 mt-0.5">
                    <p className="text-xl font-extrabold text-gray-900">
                        {(kpis?.total_lojas || 0).toLocaleString('pt-BR')} <span className="text-xs font-normal text-gray-500">lojas</span>
                    </p>
                    <span className="text-xs font-semibold text-blue-600">
                        ({kpis?.total_clusters || 0} clusters)
                    </span>
                </div>
                <p className="text-[10px] text-gray-400">Agrupamento espacial ativo</p>
            </div>
        </div>
    );
};

export default KpiCards;