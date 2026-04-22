import React from 'react';
import { Cpu, Zap, Database, Shield } from 'lucide-react';

const TelemetryPanel = ({ telemetry }) => {
  const nodes = Object.keys(telemetry || {});
  
  // Aggregate stats
  const totalTracks = nodes.reduce((acc, name) => acc + telemetry[name].active_tracks, 0);
  const avgFps = nodes.length > 0 
    ? Math.round(nodes.reduce((acc, name) => acc + telemetry[name].fps, 0) / nodes.length) 
    : 0;

  return (
    <div className="glass-panel p-10 flex flex-col gap-8 rounded-[40px] bg-white/[0.01] border-white/5 shadow-2xl">
      <h4 className="heading-font font-black text-[10px] text-slate-600 tracking-[0.4em] uppercase border-b border-white/5 pb-4">Engine_Telemetry</h4>
      <div className="space-y-6">
        {[
          { label: 'Neural Throughput', value: `${avgFps} FPS`, status: avgFps > 20 ? 'High' : 'Normal', icon: Zap, color: 'text-yellow-500' },
          { label: 'Track Density', value: totalTracks, status: totalTracks > 0 ? 'Active' : 'Idle', icon: Cpu, color: 'text-blue-500' },
          { label: 'Cloud Latency', value: '14ms', status: 'Secure', icon: Shield, color: 'text-emerald-500' }
        ].map((t, idx) => (
          <div key={idx} className="bg-white/5 p-6 border-white/5 rounded-[28px] border flex flex-col gap-3 relative overflow-hidden group hover:border-white/10 transition-all">
             <div className="text-[9px] font-black uppercase tracking-widest text-slate-600 flex justify-between items-center">
                {t.label}
                <t.icon size={12} className={t.color} />
             </div>
             <div className="flex items-end justify-between leading-none">
                <div className="text-2xl font-black text-white heading-font">{t.value}</div>
                <div className="px-3 py-1 rounded-full bg-emerald-500/10 text-emerald-500 text-[8px] font-black uppercase tracking-widest border border-emerald-500/10">
                   {t.status}
                </div>
             </div>
          </div>
        ))}
      </div>
    </div>
  );
};

export default TelemetryPanel;
