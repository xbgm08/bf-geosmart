import React from 'react';
import MapDashboard from './components/MapDashboard';

function App() {
  return (
    <div className="min-h-screen bg-gray-50 p-6">
      <div className="max-w-7xl mx-auto space-y-6">
        
        <header className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold text-gray-900">BF GeoSmart</h1>
            <p className="text-sm text-gray-500">Dashboard de Inteligência Territorial</p>
          </div>
        </header>

        <MapDashboard />

      </div>
    </div>
  );
}

export default App;