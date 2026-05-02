import React from 'react';
import { Camera, Activity, Maximize2 } from 'lucide-react';

const API_BASE = import.meta.env.DEV ? 'http://localhost:8000' : '';

const StreamGrid = ({ telemetry, onSnapshot }) => {
  const nodes = Object.keys(telemetry || {});

  const handleSnapshot = (e, nodeName) => {
    e.preventDefault();
    const imgElement = document.getElementById(`stream-${nodeName}`);
    if (imgElement && onSnapshot) {
      const canvas = document.createElement('canvas');
      canvas.width = imgElement.naturalWidth || 640;
      canvas.height = imgElement.naturalHeight || 480;
      canvas.getContext('2d').drawImage(imgElement, 0, 0);
      onSnapshot(canvas.toDataURL('image/jpeg', 0.9));
    }
  };

  if (nodes.length === 0) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center text-slate-700 gap-4">
        <Camera size={48} className="opacity-20" />
        <p className="text-[10px] font-black uppercase tracking-[0.3em]">Waiting for node handshakes...</p>
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-6 p-2">
      {nodes.map((nodeName) => {
        const node = telemetry[nodeName];
        const isOnline = node.status === 'Online';
        const isConnecting = node.status === 'Connecting';
        const isFailed = node.status === 'Failed';

        return (
          <div key={nodeName} className="glass-panel overflow-hidden border-white/5 bg-black/40 group relative aspect-video">
            {/* Header Overlay */}
            <div className="absolute top-4 left-4 z-20 flex items-center gap-3">
               <div className="bg-black/60 backdrop-blur-md px-3 py-1.5 rounded-lg border border-white/10 flex items-center gap-2">
                  <div className={`w-1.5 h-1.5 rounded-full ${isOnline ? 'bg-emerald-500 animate-pulse' : isConnecting ? 'bg-amber-500 animate-bounce' : 'bg-red-500'}`} />
                  <span className="text-[9px] font-black text-white uppercase tracking-widest">
                    {nodeName} {isConnecting ? '(Connecting...)' : isFailed ? '(Link Failed)' : ''}
                  </span>
               </div>
               {isOnline && (
                 <div className="bg-blue-600/20 backdrop-blur-md px-3 py-1.5 rounded-lg border border-blue-500/20 text-blue-400 text-[8px] font-black uppercase tracking-widest">
                    {node.fps} FPS
                 </div>
               )}
            </div>

            {/* Action Overlay */}
            <div className="absolute top-4 right-4 z-20 opacity-0 group-hover:opacity-100 transition-opacity flex gap-2">
               {isOnline && onSnapshot && (
                 <button onClick={(e) => handleSnapshot(e, nodeName)} className="p-2 rounded-lg bg-blue-600/80 hover:bg-blue-500 border border-blue-500/50 text-white transition-all shadow-lg active:scale-95" title="Capture Snapshot">
                    <Camera size={14} />
                 </button>
               )}
               <button className="p-2 rounded-lg bg-white/5 hover:bg-white/10 border border-white/10 text-white transition-all">
                  <Maximize2 size={14} />
               </button>
            </div>

            {/* Actual Stream or Status Message */}
            {isOnline ? (
              <img 
                id={`stream-${nodeName}`}
                crossOrigin="anonymous"
                src={`${API_BASE}/api/stream/${nodeName}`} 
                alt={nodeName}
                className="w-full h-full object-cover transition-transform duration-700 group-hover:scale-105"
                onError={(e) => {
                   e.target.src = 'https://images.unsplash.com/photo-1550751827-4bd374c3f58b?q=80&w=1000&auto=format&fit=crop';
                }}
              />
            ) : (
              <div className="w-full h-full flex flex-col items-center justify-center bg-slate-900/50 gap-3">
                {isConnecting ? (
                  <>
                    <div className="w-8 h-8 border-2 border-blue-500/20 border-t-blue-500 rounded-full animate-spin" />
                    <p className="text-[8px] font-black uppercase tracking-widest text-blue-400">Verifying Protocol Handshake...</p>
                  </>
                ) : (
                  <>
                    <Camera size={32} className="text-red-500/30" />
                    <p className="text-[8px] font-black uppercase tracking-widest text-red-400">Camera Source Unreachable</p>
                    <p className="text-[7px] text-slate-500 max-w-[200px] text-center">Please verify the RTSP link and ensure it is publicly accessible.</p>
                  </>
                )}
              </div>
            )}

            {/* Footer Stats */}
            {isOnline && (
              <div className="absolute bottom-4 left-4 z-20 opacity-0 group-hover:opacity-100 transition-all transform translate-y-2 group-hover:translate-y-0">
                 <div className="bg-black/60 backdrop-blur-md px-3 py-2 rounded-xl border border-white/10 flex items-center gap-4">
                    <div className="flex items-center gap-2">
                       <Activity size={12} className="text-blue-500" />
                       <span className="text-[9px] font-black text-slate-300 uppercase tracking-widest">{node.active_tracks} Active Tracks</span>
                    </div>
                 </div>
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
};

export default StreamGrid;
