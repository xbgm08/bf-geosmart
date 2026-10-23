import React from 'react';
import {
    BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer
} from 'recharts';

const formatarAbreviado = (valor) => {
    if (valor >= 1_000_000) return `${(valor / 1_000_000).toFixed(1)}M`;
    if (valor >= 1_000) return `${(valor / 1_000).toFixed(0)}k`;
    return valor;
};

const GraficosAnaliticos = ({ evolucaoMensal = [], funil = {} }) => {
    const {
        propostas = 0,
        contratos = 0,
        contratos_pagos = 0,
        taxa_aprovacao_pct = 0,
        taxa_efetivacao_pct = 0,
        taxa_conversao_global_pct = 0
    } = funil;

    return (
        <div className="flex flex-col gap-3 h-full min-h-0">
            <div className="bg-white p-3.5 rounded-xl shadow-sm border border-gray-200 flex-1 flex flex-col min-h-0">
                <div className="flex items-center justify-between mb-2 shrink-0">
                    <div>
                        <h2 className="text-xs font-bold text-gray-800 uppercase tracking-wider">
                            Evolução Mensal: Meta vs. Produção Paga
                        </h2>
                        <p className="text-[11px] text-gray-500">Comparativo histórico mês a mês (2026)</p>
                    </div>
                </div>

                <div className="flex-1 min-h-0 w-full">
                    <ResponsiveContainer width="100%" height="100%">
                        <BarChart data={evolucaoMensal} margin={{ top: 5, right: 10, left: -10, bottom: 0 }}>
                            <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f3f4f6" />
                            <XAxis dataKey="mes" tick={{ fontSize: 10 }} />
                            <YAxis tickFormatter={formatarAbreviado} tick={{ fontSize: 10 }} />
                            <Tooltip
                                formatter={(value) =>
                                    Number(value).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL', maximumFractionDigits: 0 })
                                }
                                contentStyle={{ fontSize: '12px', borderRadius: '8px' }}
                            />
                            <Legend wrapperStyle={{ fontSize: '11px' }} />
                            <Bar dataKey="meta" name="Meta Estabelecida" fill="#9ca3af" radius={[3, 3, 0, 0]} />
                            <Bar dataKey="realizado" name="Produção Paga" fill="#CC092F" radius={[3, 3, 0, 0]} />
                        </BarChart>
                    </ResponsiveContainer>
                </div>
            </div>

            <div className="bg-white p-3.5 rounded-xl shadow-sm border border-gray-200 shrink-0">
                <div className="flex items-center justify-between mb-2.5">
                    <div>
                        <h2 className="text-xs font-bold text-gray-800 uppercase tracking-wider">
                            Funil Comercial de Financiamentos
                        </h2>
                        <p className="text-[11px] text-gray-500">Fluxo Propostas → Contratos → Pagos</p>
                    </div>
                    <div className="bg-red-50 border border-red-200 px-2.5 py-1 rounded-lg text-right">
                        <span className="text-[10px] text-gray-600 block uppercase font-semibold">Conversão Final</span>
                        <span className="text-sm font-extrabold text-[#CC092F]">{taxa_conversao_global_pct}%</span>
                    </div>
                </div>

                <div className="space-y-2">
                    <div>
                        <div className="flex justify-between text-xs font-semibold text-gray-700 mb-0.5">
                            <span>1. Propostas Submetidas</span>
                            <span>{propostas.toLocaleString('pt-BR')} (100%)</span>
                        </div>
                        <div className="w-full bg-gray-100 rounded-full h-3 overflow-hidden">
                            <div className="bg-gray-700 h-3 rounded-full" style={{ width: '100%' }}></div>
                        </div>
                    </div>

                    <div>
                        <div className="flex justify-between text-xs font-semibold text-gray-700 mb-0.5">
                            <span>2. Contratos Formalizados</span>
                            <span>{contratos.toLocaleString('pt-BR')} ({taxa_aprovacao_pct}% das propostas)</span>
                        </div>
                        <div className="w-full bg-gray-100 rounded-full h-3 overflow-hidden">
                            <div
                                className="bg-amber-500 h-3 rounded-full transition-all duration-500"
                                style={{ width: `${Math.min(taxa_aprovacao_pct, 100)}%` }}
                            ></div>
                        </div>
                    </div>

                    <div>
                        <div className="flex justify-between text-xs font-semibold text-gray-700 mb-0.5">
                            <span>3. Contratos Pagos (Produção Efetiva)</span>
                            <span className="text-[#CC092F] font-bold">
                                {contratos_pagos.toLocaleString('pt-BR')} ({taxa_efetivacao_pct}% dos contratos)
                            </span>
                        </div>
                        <div className="w-full bg-gray-100 rounded-full h-3 overflow-hidden">
                            <div
                                className="bg-[#CC092F] h-3 rounded-full transition-all duration-500"
                                style={{ width: `${Math.min(taxa_conversao_global_pct, 100)}%` }}
                            ></div>
                        </div>
                    </div>
                </div>
            </div>

        </div>
    );
};

export default GraficosAnaliticos;