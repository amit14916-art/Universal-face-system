import { useState, useEffect, useRef } from 'react';
import { 
  Shield, LayoutList, User, ShieldOff, Trash2, X, Activity, 
  Users, Clock, Edit2, Settings, History, MapPin, 
  ChevronRight, Bell, Search, Info, Camera, LogIn, Lock, Mail, ArrowRight, LogOut, CheckCircle
} from 'lucide-react';
import './index.css';

const ScannerIcon = ({ size = 24, className = "" }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" className={className}>
    <path d="M3 7V5a2 2 0 0 1 2-2h2" />
    <path d="M17 3h2a2 2 0 0 1 2 2v2" />
    <path d="M21 17v2a2 2 0 0 1-2 2h-2" />
    <path d="M7 21H5a2 2 0 0 1-2-2v-2" />
    <line x1="7" y1="12" x2="17" y2="12" />
  </svg>
);

function App() {
  const [isLoggedIn, setIsLoggedIn] = useState(false);
  const [authMode, setAuthMode] = useState('login');
  const [logs, setLogs] = useState([]);
  const [users, setUsers] = useState([]);
  const [isRegisterOpen, setIsRegisterOpen] = useState(false);
  const [editingUser, setEditingUser] = useState(null);
  const [newName, setNewName] = useState('');
  const videoRef = useRef(null);
  const [regName, setRegName] = useState('');
  const [regRole, setRegRole] = useState('member');
  const [activeTab, setActiveTab] = useState('dashboard');

  useEffect(() => {
    if (isLoggedIn) {
      fetchData();
      const interval = setInterval(fetchData, 3000);
      return () => clearInterval(interval);
    }
  }, [isLoggedIn]);

  const fetchData = async () => {
    try {
      const baseUrl = 'http://localhost:8000';
      const cacheBuster = `?t=${Date.now()}`;
      const [lRes, uRes] = await Promise.all([
        fetch(`${baseUrl}/api/logs${cacheBuster}`),
        fetch(`${baseUrl}/api/users${cacheBuster}`)
      ]).catch(() => [null, null]);

      if (lRes && lRes.ok) setLogs(await lRes.json());
      if (uRes && uRes.ok) setUsers(await uRes.json());
    } catch (error) {
      console.error("Sync Error:", error);
    }
  };

  const toggleBlacklist = async (id, status) => {
    await fetch(`http://localhost:8000/api/users/${id}/blacklist`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ is_blacklisted: status })
    });
    fetchData();
  };

  const handleRename = async () => {
    if (!editingUser || !newName.trim()) return;
    await fetch(`http://localhost:8000/api/users/${editingUser.id}/rename`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name: newName })
    });
    setEditingUser(null);
    setNewName('');
    fetchData();
  };

  const deleteUser = async (id) => {
    if (confirm("Permanently delete this biometric profile?")) {
      await fetch(`http://localhost:8000/api/users/${id}`, { method: 'DELETE' });
      fetchData();
    }
  };

  const openWebcam = async () => {
    setIsRegisterOpen(true);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ video: true });
      if (videoRef.current) videoRef.current.srcObject = stream;
    } catch (e) {
      console.error("Webcam Error:", e);
    }
  };

  const closeWebcam = () => {
    setIsRegisterOpen(false);
    if (videoRef.current && videoRef.current.srcObject) {
      videoRef.current.srcObject.getTracks().forEach(t => t.stop());
    }
  };

  const captureAndRegister = async () => {
    const canvas = document.createElement('canvas');
    canvas.width = videoRef.current.videoWidth;
    canvas.height = videoRef.current.videoHeight;
    canvas.getContext('2d').drawImage(videoRef.current, 0, 0);
    
    await fetch('http://localhost:8000/api/register', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        name: regName,
        role: regRole,
        image_base64: canvas.toDataURL('image/jpeg')
      })
    });
    closeWebcam();
    setRegName('');
    fetchData();
  };

  if (!isLoggedIn) {
    return (
      <div className="min-h-screen w-full bg-[#020617] flex items-center justify-center p-6 relative">
        <div className="glass-panel w-full max-w-sm p-12 border-white/10 rounded-[40px] shadow-2xl relative z-20 flex flex-col items-center">
            <div className="w-16 h-16 bg-blue-600 rounded-2xl flex items-center justify-center shadow-2xl shadow-blue-600/30 mb-8">
              <Shield size={32} className="text-white" />
            </div>
            <h1 className="text-3xl font-black heading-font text-white tracking-tighter mb-2">SENTINEL AI</h1>
            <p className="text-slate-500 text-[9px] font-black uppercase tracking-[0.3em] mb-10">Cyber access node</p>
            
            <div className="w-full space-y-6">
               <div className="space-y-3">
                  <span className="text-[10px] font-black text-slate-500 uppercase tracking-widest block ml-2">MASTER ID</span>
                  <div className="relative">
                    <Mail className="absolute left-5 top-1/2 -translate-y-1/2 text-slate-700" size={16} />
                    <input type="text" placeholder="admin@sentinel.ai" className="w-full bg-[#020617] border-2 border-white/5 rounded-2xl py-4 pl-14 pr-6 text-sm text-white font-bold focus:outline-none focus:border-blue-600 transition-all placeholder:text-slate-800" />
                  </div>
               </div>
               <div className="space-y-3">
                  <span className="text-[10px] font-black text-slate-500 uppercase tracking-widest block ml-2">ACCESS KEY</span>
                  <div className="relative">
                    <Lock className="absolute left-5 top-1/2 -translate-y-1/2 text-slate-700" size={16} />
                    <input type="password" placeholder="••••••••" className="w-full bg-[#020617] border-2 border-white/5 rounded-2xl py-4 pl-14 pr-6 text-sm text-white font-bold focus:outline-none focus:border-blue-600 transition-all placeholder:text-slate-800" />
                  </div>
               </div>
            </div>

            <button onClick={() => setIsLoggedIn(true)} className="w-full bg-white text-black py-4.5 rounded-2xl font-black heading-font text-base flex items-center justify-center gap-3 mt-10 hover:bg-slate-200 transition-all shadow-xl">
               INITIALIZE <ArrowRight size={18} />
            </button>

            <button onClick={() => setAuthMode('signup')} className="mt-8 text-[9px] font-black text-slate-600 uppercase tracking-widest hover:text-blue-500 transition-colors">
               Create node protocol?
            </button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen w-full bg-[#020617] text-slate-100 font-sans selection:bg-blue-500/30 overflow-x-hidden p-0 m-0">
      
      <div className="max-w-[1200px] mx-auto flex flex-col relative z-20">
        
        {/* POLISHED NAVBAR */}
        <nav className="flex items-center justify-between py-5 px-6 border-b border-white/5 bg-[#020617]/50 backdrop-blur-3xl sticky top-0 z-50">
          <div className="flex items-center gap-4 shrink-0">
            <div className="w-9 h-9 bg-blue-600 rounded-lg flex items-center justify-center shadow-xl shadow-blue-600/30">
              <Shield size={18} className="text-white" />
            </div>
            <h1 className="text-sm font-black heading-font text-white leading-none tracking-tighter uppercase">Sentinel_AI</h1>
          </div>

          <div className="flex items-center gap-1 bg-white/5 p-1 rounded-xl border border-white/10 shrink-0">
            <button onClick={() => setActiveTab('dashboard')} className={`px-5 py-2 rounded-lg text-[9px] font-black uppercase tracking-widest transition-all ${activeTab === 'dashboard' ? 'bg-blue-600 text-white shadow-lg' : 'text-slate-500 hover:text-white'}`}>Terminal</button>
            <button onClick={() => setActiveTab('registry')} className={`px-5 py-2 rounded-lg text-[9px] font-black uppercase tracking-widest transition-all ${activeTab === 'registry' ? 'bg-blue-600 text-white shadow-lg' : 'text-slate-500 hover:text-white'}`}>Registry</button>
            <button onClick={() => setActiveTab('logs')} className={`px-5 py-2 rounded-lg text-[9px] font-black uppercase tracking-widest transition-all ${activeTab === 'logs' ? 'bg-blue-600 text-white shadow-lg' : 'text-slate-500 hover:text-white'}`}>Logs</button>
          </div>

          <div className="flex items-center gap-3">
            <button onClick={openWebcam} className="py-2.5 px-6 rounded-xl flex items-center gap-2 bg-blue-600 text-white hover:bg-blue-500 font-black text-[9px] uppercase tracking-widest transition-all shadow-xl shadow-blue-900/20 active:scale-95 shrink-0">
               <Camera size={14} /> Master Enroll
            </button>
            <button onClick={() => setIsLoggedIn(false)} className="w-9 h-9 rounded-xl flex items-center justify-center bg-white/5 border border-white/10 text-slate-500 hover:text-red-500 transition-all shrink-0">
                <LogOut size={16} />
            </button>
          </div>
        </nav>

        <main className="p-8 md:p-10 flex-1 flex flex-col gap-10">
          
          <header className="flex justify-between items-end border-b-2 border-white/5 pb-6 text-left">
            <div>
              <h2 className="text-3xl font-black heading-font text-white tracking-widest uppercase mb-2">
                {activeTab === 'dashboard' ? 'Security Node_01' : activeTab === 'registry' ? 'Identity Hub' : 'System Logs'}
              </h2>
              <div className="flex items-center gap-2">
                 <div className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
                 <p className="text-slate-600 text-[9px] font-black uppercase tracking-widest">Active surveillance stream ready</p>
              </div>
            </div>
            <div className="text-right">
              <span className="text-[10px] font-black text-slate-600 uppercase tracking-widest block">System Latency</span>
              <span className="text-md font-black text-emerald-500">18ms Optimized</span>
            </div>
          </header>

          {/* DYNAMIC STATS - FIXED OVERLAP */}
          {activeTab === 'dashboard' && (
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-8">
               <div className="glass-panel p-6 pr-20 border-white/5 rounded-[32px] flex flex-col gap-3 relative overflow-hidden group hover:border-blue-500/30 transition-all bg-white/[0.015]">
                  <dt className="text-[10px] font-black text-slate-500 uppercase tracking-widest">Master Database</dt>
                  <dd className="text-5xl font-black heading-font text-white">{users.length}</dd>
                  <div className="absolute right-4 bottom-4 opacity-5 group-hover:opacity-10 transition-opacity"><Users size={60} className="text-blue-500" /></div>
               </div>
               <div className="glass-panel p-6 pr-20 border-white/5 rounded-[32px] flex flex-col gap-3 relative overflow-hidden group hover:border-purple-500/30 transition-all bg-white/[0.015]">
                  <dt className="text-[10px] font-black text-slate-500 uppercase tracking-widest">Detection Stream</dt>
                  <dd className="text-5xl font-black heading-font text-white">{logs.length}</dd>
                  <div className="absolute right-4 bottom-4 opacity-5 group-hover:opacity-10 transition-opacity"><Activity size={60} className="text-purple-500" /></div>
               </div>
               <div className="glass-panel p-6 border-white/5 rounded-[32px] flex flex-col gap-3 relative overflow-hidden bg-blue-600/[0.03]">
                  <dt className="text-[10px] font-black text-blue-400 uppercase tracking-widest">Security Health</dt>
                  <dd className="text-5xl font-black heading-font text-emerald-400">100%</dd>
                  <div className="absolute right-4 bottom-4 opacity-5"><Shield size={60} className="text-emerald-500" /></div>
               </div>
            </div>
          )}

          <div className="grid grid-cols-1 lg:grid-cols-12 gap-10">
             
             {/* DATA LIST AREA */}
             <div className="lg:col-span-8 flex flex-col">
                <div className="glass-panel bg-white/[0.01] border-white/5 rounded-[40px] overflow-hidden flex flex-col min-h-[550px] shadow-2xl">
                   <div className="p-8 pb-4 flex flex-wrap justify-between items-center gap-6">
                      <h3 className="heading-font font-black text-[10px] text-slate-500 tracking-[0.4em] uppercase">
                        {activeTab === 'registry' ? 'Database_Registry' : activeTab === 'dashboard' ? 'Recent_Hits' : 'Full_History'}
                      </h3>
                      {(activeTab === 'registry' || activeTab === 'logs') && (
                        <div className="relative">
                           <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-700" size={14} />
                           <input placeholder="SEARCH PROTOCOL..." className="bg-[#020617] border border-white/10 rounded-xl py-2 pl-9 pr-6 text-[9px] w-64 focus:outline-none focus:border-blue-600/50 transition-all font-black uppercase tracking-widest" />
                        </div>
                      )}
                   </div>

                   <div className="flex-1 overflow-y-auto custom-scroll p-4">
                      {activeTab === 'registry' ? (
                         <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 h-fit">
                            {users.map(u => (
                               <div key={u.id} className="glass-panel p-4 flex items-center justify-between border-white/5 hover:border-blue-600/30 transition-all bg-white/[0.015] rounded-[24px] group">
                                  <div className="flex items-center gap-4 text-left">
                                     <div className="w-14 h-14 rounded-2xl overflow-hidden border-2 border-white/5 relative shadow-xl group-hover:scale-105 transition-transform duration-500">
                                        <img src={`http://localhost:8000/${u.image_path}`} className="w-full h-full object-cover" alt="" />
                                        {u.is_blacklisted && <div className="absolute inset-0 bg-red-600/40 backdrop-blur-[1px] flex items-center justify-center"><ShieldOff size={20} className="text-white" /></div>}
                                     </div>
                                     <div className="flex flex-col">
                                        <div className="text-sm font-black text-white leading-tight tracking-tight">{u.name}</div>
                                        <div className="text-[7px] font-black text-slate-600 uppercase tracking-widest mt-1.5 px-1.5 py-0.5 border border-white/5 rounded bg-white/5">{u.role}</div>
                                     </div>
                                  </div>
                                  <div className="flex gap-1.5">
                                     <button onClick={() => {setEditingUser(u); setNewName(u.name);}} className="w-9 h-9 flex items-center justify-center rounded-xl bg-white/5 text-slate-600 hover:bg-blue-600 hover:text-white transition-all"><Edit2 size={15} /></button>
                                     <button onClick={() => deleteUser(u.id)} className="w-9 h-9 flex items-center justify-center rounded-xl bg-white/5 text-slate-600 hover:bg-red-600 hover:text-white transition-all"><Trash2 size={15} /></button>
                                  </div>
                               </div>
                            ))}
                         </div>
                      ) : (
                         <div className="divide-y divide-white/5">
                            {(activeTab === 'dashboard' ? logs.slice(0, 5) : logs).map((l, i) => (
                               <div key={l.id} className="p-6 px-8 flex items-center justify-between hover:bg-white/[0.015] transition-all group animate-in slide-in-from-bottom-2 duration-500">
                                  <div className="flex items-center gap-6 text-left">
                                     <div className="w-16 h-16 rounded-[22px] overflow-hidden border-2 border-white/5 shadow-2xl shrink-0 group-hover:border-blue-600/20 transition-all duration-500">
                                        <img src={`http://localhost:8000/${l.image_path}`} className="w-full h-full object-cover" alt="" />
                                     </div>
                                     <div>
                                        <div className="text-xl font-black text-white tracking-tighter leading-none">{l.name}</div>
                                        <div className={`mt-2 inline-flex items-center px-3 py-1 rounded-lg border text-[8px] font-black uppercase tracking-widest ${l.role === 'vip' ? 'bg-yellow-500/10 text-yellow-500 border-yellow-500/10' : 'bg-blue-500/10 text-blue-400 border-blue-500/10'}`}>{l.role}</div>
                                     </div>
                                  </div>
                                  <div className="flex flex-col items-end gap-2 text-right">
                                     <div className="text-2xl font-black text-blue-500 heading-font leading-none tracking-tighter">{new Date(l.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</div>
                                     <div className="text-[9px] font-black text-slate-700 uppercase flex items-center gap-2">
                                        <MapPin size={10} /> NODE_01 HUB
                                     </div>
                                  </div>
                               </div>
                            ))}
                         </div>
                      )}
                      {activeTab === 'dashboard' && logs.length > 5 && (
                        <button onClick={() => setActiveTab('logs')} className="w-full py-6 text-[9px] font-black text-blue-500 uppercase tracking-[0.4em] hover:bg-blue-500/5 transition-all text-center">Open activity archives</button>
                      )}
                   </div>
                </div>
             </div>

             {/* FIXED TELEMETRY TIER */}
             <div className="lg:col-span-4 flex flex-col gap-10">
                <div className="glass-panel p-10 flex flex-col gap-8 rounded-[40px] bg-white/[0.01] border-white/5 shadow-2xl">
                   <h4 className="heading-font font-black text-[10px] text-slate-600 tracking-[0.4em] uppercase border-b border-white/5 pb-4">Global_Status</h4>
                   <div className="space-y-6">
                      {[
                        { label: 'Precision Node', value: '512D', status: 'Optimal' },
                        { label: 'Sync State', value: 'Live', status: 'Active' },
                        { label: 'Cloud Link', value: '14ms', status: 'Secure' }
                      ].map((t, idx) => (
                        <div key={idx} className="bg-white/5 p-6 border-white/5 rounded-[28px] border flex flex-col gap-3 relative overflow-hidden group">
                           <div className="text-[9px] font-black uppercase tracking-widest text-slate-600">{t.label}</div>
                           <div className="flex items-end justify-between leading-none">
                              <div className="text-2xl font-black text-white heading-font">{t.value}</div>
                              <div className="px-3 py-1 rounded-full bg-emerald-500/10 text-emerald-500 text-[8px] font-black uppercase tracking-widest border border-emerald-500/10">{t.status}</div>
                           </div>
                        </div>
                      ))}
                   </div>
                </div>

                <div className="glass-panel p-8 bg-blue-600/[0.03] border-blue-500/10 rounded-[40px] flex items-center gap-5">
                  <div className="w-12 h-12 rounded-2xl bg-blue-600 flex items-center justify-center shrink-0 shadow-lg shadow-blue-600/20">
                     <Info size={24} className="text-white" />
                  </div>
                  <p className="text-[10px] text-slate-500 font-bold leading-relaxed">Neural identity traffic is secured via enterprise PG-Guard protocols.</p>
                </div>
             </div>
          </div>
        </main>
      </div>

      {/* FIXED RENAME MODAL - NOW ADDED CORRECTLY */}
      {editingUser && (
        <div className="fixed inset-0 bg-[#020617]/95 backdrop-blur-3xl z-[200] flex items-center justify-center p-12">
          <div className="glass-panel w-full max-w-xl p-16 border-4 border-white/10 rounded-[48px] shadow-[0_0_100px_rgba(0,0,0,0.8)] relative overflow-hidden bg-[#020617] animate-in zoom-in-95 duration-300">
             <div className="absolute top-0 right-0 w-40 h-40 bg-blue-600/10 blur-[80px] rounded-full" />
             <h2 className="text-4xl font-black heading-font text-white mb-10 tracking-tighter leading-none">MOD_PROTOCOL</h2>
             <div className="space-y-10">
                <div className="space-y-3">
                   <label className="text-[10px] font-black text-slate-600 uppercase tracking-[0.4em] block ml-4">UPDATED IDENTITY LABEL</label>
                   <input 
                     value={newName} 
                     onChange={e => setNewName(e.target.value)} 
                     className="w-full bg-white/[0.03] border-4 border-white/5 rounded-[28px] py-6 px-10 text-2xl text-white font-black focus:outline-none focus:border-blue-600 transition-all shadow-inner" 
                   />
                </div>
                <div className="flex gap-4">
                   <button onClick={handleRename} className="py-6 px-10 bg-blue-600 text-white font-black rounded-2xl flex-1 text-lg transition-all shadow-2xl active:scale-95 leading-none">SAVE SIGNATURE</button>
                   <button onClick={() => setEditingUser(null)} className="py-6 px-10 bg-white/5 text-slate-500 font-black rounded-2xl flex-1 text-lg transition-all border-2 border-white/5 leading-none">DISCARD</button>
                </div>
             </div>
          </div>
        </div>
      )}

      {/* FULL SCREEN SCANNER */}
      {isRegisterOpen && (
        <div className="fixed inset-0 bg-[#020617]/98 backdrop-blur-3xl z-[100] flex items-center justify-center p-16">
          <div className="glass-panel w-full max-w-5xl overflow-hidden flex flex-col md:flex-row border-white/10 rounded-[64px] shadow-2xl animate-in zoom-in-95 duration-500 border-2 relative">
             
             <button onClick={closeWebcam} className="absolute top-10 right-10 z-[110] w-14 h-14 rounded-2xl flex items-center justify-center bg-white/5 hover:bg-white/10 text-white transition-all border border-white/10 shadow-2xl">
                <X size={32} />
             </button>

             <div className="flex-1 p-16 flex flex-col gap-12 bg-white/[0.015] text-left">
                <div>
                   <h2 className="text-4xl font-black heading-font text-white tracking-widest uppercase">ENROLLMENT</h2>
                   <p className="text-slate-600 text-lg mt-4 font-medium leading-relaxed">Neural identity master path sync active.</p>
                </div>
                <div className="space-y-8">
                   <div className="space-y-3">
                      <label className="text-[10px] font-black text-slate-600 uppercase tracking-widest pl-3">Official Subject Name</label>
                      <input 
                        value={regName} 
                        onChange={e => setRegName(e.target.value)} 
                        placeholder="Ex: Marcus Vane" 
                        className="w-full bg-[#020617] border-4 border-white/5 rounded-[32px] py-6 px-10 text-2xl text-white font-black focus:outline-none focus:border-blue-600 transition-all placeholder:text-slate-900 shadow-inner"
                      />
                   </div>
                   <div className="space-y-3">
                      <label className="text-[10px] font-black text-slate-600 uppercase tracking-widest pl-3">Security Ops Role</label>
                      <select 
                        value={regRole} 
                        onChange={e => setRegRole(e.target.value)}
                        className="w-full bg-[#020617] border-4 border-white/5 rounded-[32px] py-6 px-10 text-2xl text-white font-black focus:outline-none focus:border-blue-600 transition-all shadow-inner appearance-none"
                      >
                        <option value="member">MEMBER</option>
                        <option value="government">GOV_VIP</option>
                      </select>
                   </div>
                </div>
                <button onClick={captureAndRegister} disabled={!regName} className={`w-full py-8 rounded-[40px] font-black heading-font text-2xl flex items-center justify-center gap-6 transition-all ${!regName ? 'bg-slate-900 text-slate-800 opacity-50' : 'bg-white text-black hover:scale-[1.01] active:scale-95 shadow-2xl'}`}>
                   <ScannerIcon size={32} /> INITIALIZE SCAN
                </button>
             </div>

             <div className="lg:w-[450px] shrink-0 bg-black relative p-12 flex items-center justify-center">
                <div className="w-full h-full rounded-[48px] overflow-hidden relative border-4 border-white/10 shadow-[0_0_80px_rgba(59,130,246,0.2)]">
                   <video ref={videoRef} autoPlay playsInline className="w-full h-full object-cover scale-x-[-1] grayscale-[0.2]" />
                   <div className="scanner-overlay !z-10 bg-blue-900/10">
                      <div className="scanner-line !h-[6px] !bg-blue-400 !shadow-[0_0_30px_#3b82f6]"></div>
                      <div className="face-target !border-blue-500/30 !w-[280px] !h-[380px] !border-[3px] !rounded-[80px]"></div>
                      <div className="absolute top-8 left-8 flex items-center gap-4 bg-black/80 px-5 py-2 rounded-2xl backdrop-blur-3xl border border-white/10">
                          <div className="w-2.5 h-2.5 bg-red-600 rounded-full animate-pulse shadow-[0_0_15px_#dc2626]" />
                          <span className="text-[9px] font-black mono-font text-white uppercase tracking-widest">Scanning...</span>
                      </div>
                   </div>
                </div>
             </div>
          </div>
        </div>
      )}

    </div>
  );
}

export default App;
