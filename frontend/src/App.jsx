import { useState, useEffect, useRef } from 'react';
import { 
  Shield, LayoutList, User, ShieldOff, Trash2, X, Activity, 
  Users, Clock, Edit2, Settings, History, MapPin, 
  ChevronRight, Bell, Search, Info, Camera, LogIn, Lock, Mail, ArrowRight, LogOut, CheckCircle
} from 'lucide-react';
import './index.css';
import StreamGrid from './components/StreamGrid';
import TelemetryPanel from './components/TelemetryPanel';
import { 
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  BarChart, Bar, Cell
} from 'recharts';

const ScannerIcon = ({ size = 24, className = "" }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" className={className}>
    <path d="M3 7V5a2 2 0 0 1 2-2h2" />
    <path d="M17 3h2a2 2 0 0 1 2 2v2" />
    <path d="M21 17v2a2 2 0 0 1-2 2h-2" />
    <path d="M7 21H5a2 2 0 0 1-2-2v-2" />
    <line x1="7" y1="12" x2="17" y2="12" />
  </svg>
);

const API_BASE = import.meta.env.DEV ? 'http://localhost:8000' : '';

function App() {
  const [isLoggedIn, setIsLoggedIn] = useState(false);
  const [authMode, setAuthMode] = useState('login');
  const [logs, setLogs] = useState([]);
  const [users, setUsers] = useState([]);
  const [telemetry, setTelemetry] = useState({});
  const [cameraUrl, setCameraUrl] = useState('');
  const [isRegisterOpen, setIsRegisterOpen] = useState(false);
  const [editingUser, setEditingUser] = useState(null);
  const [newName, setNewName] = useState('');
  const videoRef = useRef(null);
  const [regName, setRegName] = useState('');
  const [regRole, setRegRole] = useState('member');
  const [activeTab, setActiveTab] = useState('dashboard');
  const [regSource, setRegSource] = useState('local'); 

  const [identifier, setIdentifier] = useState('');
  const [email, setEmail] = useState('');
  const [mobile, setMobile] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [gymName, setGymName] = useState('');
  const [ownerId, setOwnerId] = useState(localStorage.getItem('owner_id') || null);
  const [currentGymName, setCurrentGymName] = useState(localStorage.getItem('gym_name') || '');
  const [stats, setStats] = useState(null);
  const [webhookUrl, setWebhookUrl] = useState('');
  const [notifyOnEntry, setNotifyOnEntry] = useState(true);
  const [notifyOnExpiry, setNotifyOnExpiry] = useState(true);
  const [isSavingSettings, setIsSavingSettings] = useState(false);

  useEffect(() => {
    if (isLoggedIn && ownerId) {
      fetchData();
      const interval = setInterval(fetchData, 3000);
      return () => clearInterval(interval);
    }
  }, [isLoggedIn, ownerId]);

  const fetchData = async () => {
    if (!ownerId) return;
    try {
      const baseUrl = API_BASE;
      const cacheBuster = `?t=${Date.now()}&owner_id=${ownerId}`;
      const [lRes, uRes, tRes, sRes] = await Promise.all([
        fetch(`${baseUrl}/api/logs${cacheBuster}`),
        fetch(`${baseUrl}/api/users${cacheBuster}`),
        fetch(`${baseUrl}/api/telemetry${cacheBuster}`),
        fetch(`${baseUrl}/api/stats${cacheBuster}`)
      ]).catch(() => [null, null, null, null]);

      if (lRes && lRes.ok) setLogs(await lRes.json());
      if (uRes && uRes.ok) setUsers(await uRes.json());
      if (tRes && tRes.ok) setTelemetry(await tRes.json());
      if (sRes && sRes.ok) setStats(await sRes.json());
    } catch (error) {
      console.error("Sync Error:", error);
    }
  };

  const fetchSettings = async () => {
    if (!ownerId) return;
    try {
      const res = await fetch(`${API_BASE}/api/settings/notifications?owner_id=${ownerId}`);
      if (res.ok) {
        const data = await res.json();
        setWebhookUrl(data.webhook_url || '');
        setNotifyOnEntry(data.notify_on_entry);
        setNotifyOnExpiry(data.notify_on_expiry);
      }
    } catch (e) { console.error(e); }
  };

  useEffect(() => {
    if (isLoggedIn && ownerId) fetchSettings();
  }, [isLoggedIn, ownerId]);

  const saveNotificationSettings = async () => {
    setIsSavingSettings(true);
    try {
      await fetch(`${API_BASE}/api/settings/notifications`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          owner_id: ownerId,
          webhook_url: webhookUrl,
          notify_on_entry: notifyOnEntry,
          notify_on_expiry: notifyOnExpiry
        })
      });
      alert("Settings Saved Successfully!");
    } catch (e) { alert("Failed to save settings"); }
    setIsSavingSettings(false);
  };

  const toggleBlacklist = async (id, status) => {
    await fetch(`${API_BASE}/api/users/${id}/blacklist`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ is_blacklisted: status })
    });
    fetchData();
  };

  const handleRename = async () => {
    if (!editingUser || !newName.trim()) return;
    try {
      await fetch(`${API_BASE}/api/users/${editingUser.id}/rename`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: newName })
      });
    } catch (e) {
      console.error("Save failed:", e);
    } finally {
      setEditingUser(null);
      setNewName('');
      fetchData();
    }
  };

  const deleteUser = async (id) => {
    if (confirm("Permanently delete this biometric profile?")) {
      await fetch(`${API_BASE}/api/users/${id}`, { method: 'DELETE' });
      fetchData();
    }
  };

  const openWebcam = async (source = 'local') => {
    setIsRegisterOpen(true);
    setRegSource(source);
    if (source === 'local') {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({ video: true });
        if (videoRef.current) videoRef.current.srcObject = stream;
      } catch (e) {
        console.error("Webcam Error:", e);
      }
    }
  };

  const closeWebcam = () => {
    setIsRegisterOpen(false);
    if (videoRef.current && videoRef.current.srcObject) {
      videoRef.current.srcObject.getTracks().forEach(t => t.stop());
    }
  };

  const captureAndRegister = async () => {
    let frameData = "";
    try {
      if (regSource === 'local') {
        if (!videoRef.current) return;
        const canvas = document.createElement('canvas');
        canvas.width = videoRef.current.videoWidth;
        canvas.height = videoRef.current.videoHeight;
        canvas.getContext('2d').drawImage(videoRef.current, 0, 0);
        frameData = canvas.toDataURL('image/jpeg');
      } else {
        const streamImg = document.getElementById('sentinel-enroll-stream');
        if (!streamImg) return;
        const canvas = document.createElement('canvas');
        canvas.width = streamImg.naturalWidth || 640;
        canvas.height = streamImg.naturalHeight || 480;
        canvas.getContext('2d').drawImage(streamImg, 0, 0);
        frameData = canvas.toDataURL('image/jpeg');
      }
      
      if (!frameData) {
        alert("Failed to capture image data.");
        return;
      }

      const res = await fetch(`${API_BASE}/api/register`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          owner_id: parseInt(ownerId),
          name: regName,
          role: regRole,
          image_base64: frameData
        })
      });

      const data = await res.json();
      if (data.status === 'success') {
        alert("Enrollment Successful!");
        closeWebcam();
        setRegName('');
        fetchData();
      } else {
        alert("Error: " + data.message);
      }
    } catch (e) {
      console.error("Registration Error:", e);
      alert("Registration failed: " + e.message);
    }
  };

  const handleLogin = async () => {
    if (!identifier || !password) return alert("Please fill all fields");
    try {
      const res = await fetch(`${API_BASE}/api/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ identifier, password })
      });
      const data = await res.json();
      if (res.ok) {
        setOwnerId(data.owner_id);
        setCurrentGymName(data.gym_name);
        localStorage.setItem('owner_id', data.owner_id);
        localStorage.setItem('gym_name', data.gym_name);
        setIsLoggedIn(true);
      } else {
        alert(data.detail || "Login failed");
      }
    } catch(e) {
      console.error("Login Error:", e);
    }
  };

  const handleSignup = async () => {
    if (!gymName || !email || !mobile || !password || !confirmPassword) return alert("Please fill all fields");
    if (password !== confirmPassword) return alert("Passwords do not match!");
    try {
      const res = await fetch(`${API_BASE}/api/auth/signup`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ gym_name: gymName, email, mobile, password })
      });
      const data = await res.json();
      if (res.ok) {
        alert("Sign Up successful! Please Login.");
        setAuthMode('login');
      } else {
        alert(data.detail || "Sign Up failed");
      }
    } catch(e) {
      console.error("Sign Up Error:", e);
    }
  };

  const handleUpdateSubscription = async (userId, expiryDate, planType) => {
    try {
      const res = await fetch(`${API_BASE}/api/users/subscription`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ user_id: userId, expiry_date: expiryDate, plan_type: planType })
      });
      if (res.ok) {
        alert("Subscription updated!");
        fetchData();
      }
    } catch (e) {
      console.error("Update failed", e);
    }
  };

  const handleUpdateNode = async () => {
    try {
      await fetch(`${API_BASE}/api/nodes/add`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: "Gym_Camera", url: cameraUrl || "0" })
      });
      alert("Node protocol updated successfully!");
    } catch(e) {
      console.error("Failed to update node", e);
      alert("Update failed");
    }
  };

  if (!isLoggedIn) {
    return (
      <div className="min-h-screen w-full bg-[#020617] flex items-center justify-center p-6 relative overflow-hidden">
        <div className="absolute top-[-10%] left-[-10%] w-[40%] h-[40%] bg-blue-600/10 blur-[120px] rounded-full" />
        <div className="absolute bottom-[-10%] right-[-10%] w-[40%] h-[40%] bg-emerald-600/10 blur-[120px] rounded-full" />
        
        <div className="glass-panel w-full max-w-sm p-12 border-white/10 rounded-[40px] shadow-2xl relative z-20 flex flex-col items-center animate-in fade-in zoom-in-95 duration-500">
            <div className="w-16 h-16 bg-blue-600 rounded-2xl flex items-center justify-center shadow-2xl shadow-blue-600/30 mb-8">
              <Shield size={32} className="text-white" />
            </div>
            <h1 className="text-3xl font-black heading-font text-white tracking-tighter mb-2">SENTINEL AI</h1>
            <p className="text-slate-500 text-[9px] font-black uppercase tracking-[0.3em] mb-10">
              {authMode === 'login' ? 'Gym Owner Login' : 'Gym Owner Sign Up'}
            </p>
            
            <div className="w-full space-y-6">
                {authMode === 'signup' ? (
                  <>
                    <div className="space-y-3 animate-in slide-in-from-top-2">
                      <span className="text-[10px] font-black text-slate-500 uppercase tracking-widest block ml-2">GYM NAME</span>
                      <div className="flex items-center bg-[#020617] border-2 border-white/5 rounded-2xl px-5 py-4 focus-within:border-blue-600 transition-all">
                        <LayoutList className="text-slate-600 flex-shrink-0" size={18} />
                        <input 
                          type="text" 
                          value={gymName}
                          onChange={e => setGymName(e.target.value)}
                          placeholder="Power Fitness Gym" 
                          className="w-full bg-transparent border-none text-sm text-white font-bold focus:outline-none placeholder:text-slate-700 ml-4" 
                        />
                      </div>
                    </div>

                    <div className="space-y-3">
                      <span className="text-[10px] font-black text-slate-500 uppercase tracking-widest block ml-2">EMAIL ADDRESS</span>
                      <div className="flex items-center bg-[#020617] border-2 border-white/5 rounded-2xl px-5 py-4 focus-within:border-blue-600 transition-all">
                        <Mail className="text-slate-600 flex-shrink-0" size={18} />
                        <input 
                          type="email" 
                          value={email}
                          onChange={e => setEmail(e.target.value)}
                          placeholder="owner@gym.com" 
                          className="w-full bg-transparent border-none text-sm text-white font-bold focus:outline-none placeholder:text-slate-700 ml-4" 
                        />
                      </div>
                    </div>

                    <div className="space-y-3">
                      <span className="text-[10px] font-black text-slate-500 uppercase tracking-widest block ml-2">MOBILE NO.</span>
                      <div className="flex items-center bg-[#020617] border-2 border-white/5 rounded-2xl px-5 py-4 focus-within:border-blue-600 transition-all">
                        <Search className="text-slate-600 flex-shrink-0" size={18} />
                        <input 
                          type="tel" 
                          value={mobile}
                          onChange={e => setMobile(e.target.value)}
                          placeholder="+91 8770557655" 
                          className="w-full bg-transparent border-none text-sm text-white font-bold focus:outline-none placeholder:text-slate-700 ml-4" 
                        />
                      </div>
                    </div>
                  </>
                ) : (
                  <div className="space-y-3">
                    <span className="text-[10px] font-black text-slate-500 uppercase tracking-widest block ml-2">EMAIL OR MOBILE NO.</span>
                    <div className="flex items-center bg-[#020617] border-2 border-white/5 rounded-2xl px-5 py-4 focus-within:border-blue-600 transition-all">
                      <User className="text-slate-600 flex-shrink-0" size={18} />
                      <input 
                        type="text" 
                        value={identifier}
                        onChange={e => setIdentifier(e.target.value)}
                        placeholder="Email or +91..." 
                        className="w-full bg-transparent border-none text-sm text-white font-bold focus:outline-none placeholder:text-slate-700 ml-4" 
                      />
                    </div>
                  </div>
                )}

                <div className="space-y-3">
                  <span className="text-[10px] font-black text-slate-500 uppercase tracking-widest block ml-2">PASSWORD</span>
                  <div className="flex items-center bg-[#020617] border-2 border-white/5 rounded-2xl px-5 py-4 focus-within:border-blue-600 transition-all">
                    <Lock className="text-slate-600 flex-shrink-0" size={18} />
                    <input 
                      type="password" 
                      value={password}
                      onChange={e => setPassword(e.target.value)}
                      placeholder="••••••••" 
                      className="w-full bg-transparent border-none text-sm text-white font-bold focus:outline-none placeholder:text-slate-700 ml-4" 
                    />
                  </div>
                </div>

                {authMode === 'signup' && (
                  <div className="space-y-3 animate-in slide-in-from-top-2">
                    <span className="text-[10px] font-black text-slate-500 uppercase tracking-widest block ml-2">CONFIRM PASSWORD</span>
                    <div className="flex items-center bg-[#020617] border-2 border-white/5 rounded-2xl px-5 py-4 focus-within:border-blue-600 transition-all">
                      <Lock className="text-slate-600 flex-shrink-0" size={18} />
                      <input 
                        type="password" 
                        value={confirmPassword}
                        onChange={e => setConfirmPassword(e.target.value)}
                        placeholder="••••••••" 
                        className="w-full bg-transparent border-none text-sm text-white font-bold focus:outline-none placeholder:text-slate-700 ml-4" 
                      />
                    </div>
                  </div>
                )}
            </div>

            <button 
              onClick={authMode === 'login' ? handleLogin : handleSignup} 
              className="w-full bg-white text-black py-4.5 rounded-2xl font-black heading-font text-base flex items-center justify-center gap-3 mt-10 hover:bg-slate-200 transition-all shadow-xl active:scale-95"
            >
               {authMode === 'login' ? 'LOG IN' : 'SIGN UP'} <ArrowRight size={18} />
            </button>

            <button 
              onClick={() => setAuthMode(authMode === 'login' ? 'signup' : 'login')} 
              className="mt-8 text-[9px] font-black text-slate-600 uppercase tracking-widest hover:text-blue-500 transition-colors"
            >
               {authMode === 'login' ? 'New user? Sign Up here' : 'Already have an account? Log In'}
            </button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen w-full bg-[#020617] text-slate-100 font-sans selection:bg-blue-500/30 overflow-x-hidden p-0 m-0">
      
      <div className="max-w-[1400px] mx-auto flex flex-col relative z-20">
        
        {/* POLISHED NAVBAR */}
        <nav className="flex items-center justify-between py-5 px-6 border-b border-white/5 bg-[#020617]/50 backdrop-blur-3xl sticky top-0 z-50">
          <div className="flex items-center gap-4 shrink-0">
            <div className="w-9 h-9 bg-blue-600 rounded-lg flex items-center justify-center shadow-xl shadow-blue-600/30">
              <Shield size={18} className="text-white" />
            </div>
            <h1 className="text-sm font-black heading-font text-white leading-none tracking-tighter uppercase">{currentGymName || 'Sentinel_AI'}</h1>
          </div>

          <div className="flex items-center gap-1 bg-white/5 p-1 rounded-xl border border-white/10 shrink-0">
            <button onClick={() => setActiveTab('dashboard')} className={`px-5 py-2 rounded-lg text-[9px] font-black uppercase tracking-widest transition-all ${activeTab === 'dashboard' ? 'bg-blue-600 text-white shadow-lg' : 'text-slate-500 hover:text-white'}`}>Analytics</button>
            <button onClick={() => setActiveTab('logs')} className={`px-5 py-2 rounded-lg text-[9px] font-black uppercase tracking-widest transition-all ${activeTab === 'logs' ? 'bg-blue-600 text-white shadow-lg' : 'text-slate-500 hover:text-white'}`}>Activity Logs</button>
            <button onClick={() => setActiveTab('registry')} className={`px-5 py-2 rounded-lg text-[9px] font-black uppercase tracking-widest transition-all ${activeTab === 'registry' ? 'bg-blue-600 text-white shadow-lg' : 'text-slate-500 hover:text-white'}`}>Member Registry</button>
            <button onClick={() => setActiveTab('settings')} className={`px-5 py-2 rounded-lg text-[9px] font-black uppercase tracking-widest transition-all ${activeTab === 'settings' ? 'bg-blue-600 text-white shadow-lg' : 'text-slate-500 hover:text-white'}`}>Node Settings</button>
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
                {activeTab === 'dashboard' ? 'ANALYTICS INSIGHTS' : activeTab === 'registry' ? 'MEMBER REGISTRY' : activeTab === 'settings' ? 'NODE SETTINGS' : 'ACTIVITY LOGS'}
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

          {/* REAL-TIME EXPIRY ALERTS */}
          {logs.length > 0 && new Date(logs[0].timestamp) > new Date(Date.now() - 30000) && logs[0].subscription_status === 'expired' && (
            <div className="bg-red-600/20 border-2 border-red-600/50 rounded-[32px] p-8 flex items-center justify-between animate-pulse shadow-2xl shadow-red-900/20">
              <div className="flex items-center gap-6">
                <div className="w-16 h-16 rounded-2xl bg-red-600 flex items-center justify-center shadow-lg shadow-red-600/40">
                  <ShieldOff size={32} className="text-white" />
                </div>
                <div className="text-left">
                  <h4 className="text-xl font-black text-white tracking-tighter uppercase mb-1">CRITICAL ACCESS DENIED</h4>
                  <p className="text-[10px] text-red-500 font-black uppercase tracking-widest">
                    Member <span className="text-white">{logs[0].name}</span> has an expired subscription. Access protocol engaged.
                  </p>
                </div>
              </div>
              <div className="hidden md:flex flex-col items-end">
                <span className="text-[10px] font-black text-red-500 uppercase tracking-widest">Detected at</span>
                <span className="text-2xl font-black text-white heading-font tabular-nums">{new Date(logs[0].timestamp).toLocaleTimeString()}</span>
              </div>
            </div>
          )}

          <div className="grid grid-cols-1 lg:grid-cols-12 gap-10">
             
             {/* DATA LIST AREA */}
             <div className="lg:col-span-12 flex flex-col gap-6">
                
                <div className="glass-panel bg-white/[0.01] border-white/5 rounded-[40px] flex flex-col min-h-[500px] shadow-2xl">
                   <div className="p-8 pb-4 flex flex-wrap justify-between items-center gap-6">
                      <h3 className="heading-font font-black text-[12px] text-slate-500 tracking-widest uppercase pl-2">
                        {activeTab === 'registry' ? 'Database_Registry' : activeTab === 'settings' ? 'Camera_Configuration' : 'Full_History'}
                      </h3>
                      {(activeTab === 'registry' || activeTab === 'logs') && (
                        <div className="relative">
                           <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-700" size={14} />
                           <input placeholder="SEARCH PROTOCOL..." className="bg-[#020617] border border-white/10 rounded-xl py-2 pl-9 pr-6 text-[9px] w-64 focus:outline-none focus:border-blue-600/50 transition-all font-black uppercase tracking-widest" />
                        </div>
                      )}
                   </div>

                    <div className="flex-1 overflow-y-auto custom-scroll p-4">
                       {activeTab === 'dashboard' ? (
                         <div className="space-y-8 p-4 text-left">
                           {/* Summary Cards */}
                           <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                             {[
                               { label: 'Total Members', value: stats?.summary?.total_members || 0, icon: Users, color: 'text-blue-500' },
                               { label: 'Active Plans', value: stats?.summary?.active_members || 0, icon: CheckCircle, color: 'text-emerald-500' },
                               { label: 'Today Entries', value: stats?.summary?.today_attendance || 0, icon: Activity, color: 'text-purple-500' },
                               { label: 'Expired', value: stats?.summary?.expired_members || 0, icon: ShieldOff, color: 'text-red-500' }
                             ].map((card, i) => (
                               <div key={i} className="glass-panel p-6 bg-white/[0.02] border-white/5 rounded-[32px] flex flex-col gap-2">
                                 <card.icon className={card.color} size={20} />
                                 <div className="text-3xl font-black text-white mt-2 tracking-tighter">{card.value}</div>
                                 <div className="text-[10px] font-black text-slate-500 uppercase tracking-widest">{card.label}</div>
                               </div>
                             ))}
                           </div>

                           <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
                             {/* Weekly Trend Chart */}
                             <div className="glass-panel p-8 bg-white/[0.01] border-white/5 rounded-[40px] h-[350px] flex flex-col">
                               <h4 className="text-[10px] font-black text-slate-500 uppercase tracking-widest mb-8">Weekly_Attendance_Trend</h4>
                               <div className="flex-1 min-h-0">
                                 <ResponsiveContainer width="100%" height="100%">
                                   <AreaChart data={stats?.weekly_trend || []}>
                                     <defs>
                                       <linearGradient id="colorCount" x1="0" y1="0" x2="0" y2="1">
                                         <stop offset="5%" stopColor="#2563eb" stopOpacity={0.3}/>
                                         <stop offset="95%" stopColor="#2563eb" stopOpacity={0}/>
                                       </linearGradient>
                                     </defs>
                                     <CartesianGrid strokeDasharray="3 3" stroke="#ffffff05" vertical={false} />
                                     <XAxis dataKey="day" axisLine={false} tickLine={false} tick={{fill: '#475569', fontSize: 10, fontWeight: 900}} />
                                     <YAxis axisLine={false} tickLine={false} tick={{fill: '#475569', fontSize: 10, fontWeight: 900}} />
                                     <Tooltip 
                                       contentStyle={{backgroundColor: '#020617', border: '1px solid #ffffff10', borderRadius: '16px', fontSize: '10px', fontWeight: 900}}
                                       itemStyle={{color: '#fff'}}
                                     />
                                     <Area type="monotone" dataKey="count" stroke="#2563eb" strokeWidth={4} fillOpacity={1} fill="url(#colorCount)" />
                                   </AreaChart>
                                 </ResponsiveContainer>
                               </div>
                             </div>

                             {/* Peak Hours Chart */}
                             <div className="glass-panel p-8 bg-white/[0.01] border-white/5 rounded-[40px] h-[350px] flex flex-col">
                               <h4 className="text-[10px] font-black text-slate-500 uppercase tracking-widest mb-8">Today_Peak_Hours</h4>
                               <div className="flex-1 min-h-0">
                                 <ResponsiveContainer width="100%" height="100%">
                                   <BarChart data={stats?.peak_hours || []}>
                                     <CartesianGrid strokeDasharray="3 3" stroke="#ffffff05" vertical={false} />
                                     <XAxis dataKey="hour" axisLine={false} tickLine={false} tick={{fill: '#475569', fontSize: 8, fontWeight: 900}} />
                                     <YAxis axisLine={false} tickLine={false} tick={{fill: '#475569', fontSize: 10, fontWeight: 900}} />
                                     <Tooltip 
                                       contentStyle={{backgroundColor: '#020617', border: '1px solid #ffffff10', borderRadius: '16px', fontSize: '10px', fontWeight: 900}}
                                       cursor={{fill: '#ffffff05'}}
                                     />
                                     <Bar dataKey="count" radius={[4, 4, 0, 0]}>
                                       {(stats?.peak_hours || []).map((entry, index) => (
                                         <Cell key={`cell-${index}`} fill={entry.count > 0 ? '#2563eb' : '#ffffff05'} />
                                       ))}
                                     </Bar>
                                   </BarChart>
                                 </ResponsiveContainer>
                               </div>
                             </div>
                           </div>
                         </div>
                       ) : activeTab === 'registry' ? (
                         <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 h-fit">
                            {users.map(u => (
                               <div key={u.id} className="glass-panel p-4 flex items-center justify-between border-white/5 hover:border-blue-600/30 transition-all bg-white/[0.015] rounded-[24px] group">
                                  <div className="flex items-center gap-4 text-left">
                                     <div className="w-14 h-14 rounded-2xl overflow-hidden border-2 border-white/5 relative shadow-xl group-hover:scale-105 transition-transform duration-500">
                                        <img src={`${API_BASE}/${u.image_path}`} className="w-full h-full object-cover" alt="" />
                                        {u.is_blacklisted && <div className="absolute inset-0 bg-red-600/40 backdrop-blur-[1px] flex items-center justify-center"><ShieldOff size={20} className="text-white" /></div>}
                                     </div>
                                     <div className="flex flex-col">
                                        <div className="text-sm font-black text-white leading-tight tracking-tight">{u.name}</div>
                                         <div className="flex items-center gap-2 mt-1.5">
                                            <div className="text-[7px] font-black text-slate-600 uppercase tracking-widest px-1.5 py-0.5 border border-white/5 rounded bg-white/5">{u.role}</div>
                                            {u.subscription_expiry ? (
                                              <div className={`text-[7px] font-black uppercase tracking-widest px-1.5 py-0.5 rounded ${new Date(u.subscription_expiry) > new Date() ? 'bg-emerald-500/10 text-emerald-500' : 'bg-red-500/10 text-red-500'}`}>
                                                Exp: {new Date(u.subscription_expiry).toLocaleDateString()}
                                              </div>
                                            ) : (
                                              <div className="text-[7px] font-black text-slate-600 uppercase tracking-widest px-1.5 py-0.5 bg-white/5 rounded">No Plan</div>
                                            )}
                                         </div>
                                     </div>
                                  </div>
                                   <div className="flex gap-1.5">
                                      <button onClick={() => {
                                        const nextMonth = new Date();
                                        nextMonth.setMonth(nextMonth.getMonth() + 1);
                                        handleUpdateSubscription(u.id, nextMonth.toISOString(), 'monthly');
                                      }} className="w-9 h-9 flex items-center justify-center rounded-xl bg-white/5 text-slate-600 hover:bg-emerald-600 hover:text-white transition-all" title="Renew 1 Month"><Clock size={15} /></button>
                                      <button onClick={() => {setEditingUser(u); setNewName(u.name);}} className="w-9 h-9 flex items-center justify-center rounded-xl bg-white/5 text-slate-600 hover:bg-blue-600 hover:text-white transition-all"><Edit2 size={15} /></button>
                                     <button onClick={() => deleteUser(u.id)} className="w-9 h-9 flex items-center justify-center rounded-xl bg-white/5 text-slate-600 hover:bg-red-600 hover:text-white transition-all"><Trash2 size={15} /></button>
                                  </div>
                               </div>
                            ))}
                         </div>
                      ) : activeTab === 'settings' ? (
                         <div className="p-8 space-y-12 max-w-2xl">
                            <div className="space-y-4">
                               <label className="text-xs font-black text-slate-400 uppercase tracking-widest block ml-2">IP CAMERA LINK (HTTP/RTSP)</label>
                               <div className="flex items-center bg-[#020617] border-2 border-white/10 rounded-2xl px-6 py-5 focus-within:border-blue-600 transition-all">
                                 <Camera className="text-slate-600 flex-shrink-0" size={24} />
                                 <input 
                                   type="text" 
                                   value={cameraUrl} 
                                   onChange={e => setCameraUrl(e.target.value)} 
                                   placeholder="rtsp://admin:12345@192.168.1.100" 
                                   className="w-full bg-transparent border-none text-lg text-white font-black focus:outline-none placeholder:text-slate-800 ml-6" 
                                 />
                               </div>
                               <p className="text-[10px] text-slate-600 font-bold uppercase tracking-wider ml-2">Enter the RTSP or HTTP stream URL from your IP camera or mobile device.</p>
                            </div>
                            
                            <button 
                              onClick={handleUpdateNode}
                              className="px-10 py-5 bg-blue-600 text-white rounded-2xl font-black heading-font text-sm flex items-center gap-3 hover:bg-blue-500 transition-all shadow-xl shadow-blue-900/20 active:scale-95"
                            >
                               UPDATE PROTOCOL <ArrowRight size={18} />
                            </button>

                             <div className="pt-8 border-t border-white/5 space-y-8 text-left">
                                <div>
                                  <h3 className="text-xl font-black text-white uppercase tracking-tighter mb-2">Smart Notifications</h3>
                                  <p className="text-[10px] text-slate-500 font-bold uppercase tracking-widest">Connect WhatsApp/Telegram via Webhooks</p>
                                </div>

                                <div className="space-y-6">
                                  <div className="space-y-4">
                                    <label className="text-xs font-black text-slate-400 uppercase tracking-widest block ml-2">Webhook URL</label>
                                    <div className="flex items-center bg-[#020617] border-2 border-white/10 rounded-2xl px-6 py-5 focus-within:border-blue-600 transition-all">
                                      <Bell className="text-slate-600 flex-shrink-0" size={24} />
                                      <input 
                                        type="text" 
                                        value={webhookUrl} 
                                        onChange={e => setWebhookUrl(e.target.value)} 
                                        placeholder="https://webhook.site/..." 
                                        className="w-full bg-transparent border-none text-md text-white font-black focus:outline-none placeholder:text-slate-800 ml-6" 
                                      />
                                    </div>
                                  </div>

                                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                                    <button 
                                      onClick={() => setNotifyOnEntry(!notifyOnEntry)}
                                      className={`p-6 rounded-[24px] border-2 flex items-center justify-between transition-all ${notifyOnEntry ? 'bg-blue-600/10 border-blue-600 text-white' : 'bg-white/5 border-white/5 text-slate-500'}`}
                                    >
                                      <div className="flex flex-col items-start">
                                        <span className="text-[10px] font-black uppercase tracking-widest">Every Entry</span>
                                        <span className="text-sm font-black">Notify on Check-in</span>
                                      </div>
                                      <CheckCircle className={notifyOnEntry ? 'text-white' : 'text-slate-800'} size={24} />
                                    </button>

                                    <button 
                                      onClick={() => setNotifyOnExpiry(!notifyOnExpiry)}
                                      className={`p-6 rounded-[24px] border-2 flex items-center justify-between transition-all ${notifyOnExpiry ? 'bg-red-500/10 border-red-500 text-white' : 'bg-white/5 border-white/5 text-slate-500'}`}
                                    >
                                      <div className="flex flex-col items-start">
                                        <span className="text-[10px] font-black uppercase tracking-widest">Critical Alert</span>
                                        <span className="text-sm font-black">Expiry Notifications</span>
                                      </div>
                                      <Bell className={notifyOnExpiry ? 'text-white' : 'text-slate-800'} size={24} />
                                    </button>
                                  </div>

                                  <button 
                                    onClick={saveNotificationSettings}
                                    disabled={isSavingSettings}
                                    className="w-full px-10 py-5 bg-emerald-600 text-white rounded-2xl font-black heading-font text-sm flex items-center justify-center gap-3 hover:bg-emerald-500 transition-all shadow-xl shadow-emerald-900/20 active:scale-95 disabled:opacity-50"
                                  >
                                    {isSavingSettings ? 'SAVING...' : 'SAVE CONFIGURATION'} <CheckCircle size={18} />
                                  </button>
                                </div>
                             </div>
                          </div>
                       ) : (
                         <div className="divide-y divide-white/5">
                            {logs.map((l, i) => (
                               <div key={l.id} className="p-6 px-8 flex items-center justify-between hover:bg-white/[0.015] transition-all group animate-in slide-in-from-bottom-2 duration-500">
                                  <div className="flex items-center gap-6 text-left">
                                     <div className="w-16 h-16 rounded-[22px] overflow-hidden border-2 border-white/5 shadow-2xl shrink-0 group-hover:border-blue-600/20 transition-all duration-500">
                                        <img src={`${API_BASE}/${l.image_path}`} className="w-full h-full object-cover" alt="" />
                                     </div>
                                     <div>
                                        <div className="text-xl font-black text-white tracking-tighter leading-none">{l.name}</div>
                                         <div className="flex items-center gap-2 mt-2">
                                            <div className={`inline-flex items-center px-3 py-1 rounded-lg border text-[8px] font-black uppercase tracking-widest ${l.role === 'government' ? 'bg-yellow-500/10 text-yellow-500 border-yellow-500/10' : 'bg-blue-500/10 text-blue-400 border-blue-500/10'}`}>{l.role}</div>
                                            <div className={`inline-flex items-center px-3 py-1 rounded-lg border text-[8px] font-black uppercase tracking-widest ${l.subscription_status === 'active' ? 'bg-emerald-500/10 text-emerald-500 border-emerald-500/10' : 'bg-red-500/10 text-red-500 border-red-500/10'}`}>{l.subscription_status}</div>
                                         </div>
                                     </div>
                                  </div>
                                  <div className="flex items-center gap-6 text-right">
                                     <div className="flex flex-col items-end gap-2">
                                        <div className="text-2xl font-black text-blue-500 heading-font leading-none tracking-tighter">{new Date(l.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</div>
                                        <div className="text-[9px] font-black text-slate-700 uppercase flex items-center gap-2">
                                           <MapPin size={10} /> {l.location}
                                        </div>
                                     </div>
                                     <button onClick={() => { setEditingUser({id: l.face_id, name: l.name}); setNewName(l.name); }} className="w-10 h-10 flex items-center justify-center rounded-xl bg-white/5 text-slate-400 hover:bg-blue-600 hover:text-white transition-all opacity-0 group-hover:opacity-100">
                                        <Edit2 size={16} />
                                     </button>
                                  </div>
                               </div>
                            ))}
                         </div>
                      )}
                   </div>
                </div>
             </div>

             {/* FIXED TELEMETRY TIER REMOVED */}
          </div>
        </main>
      </div>

      {/* FIXED RENAME MODAL */}
      {editingUser && (
        <div className="fixed inset-0 bg-[#020617]/95 backdrop-blur-3xl z-[200] flex items-center justify-center p-6 md:p-12">
          <div className="glass-panel w-full max-w-xl p-10 md:p-16 border-4 border-white/10 rounded-[48px] shadow-[0_0_100px_rgba(0,0,0,0.8)] relative bg-[#020617] animate-in zoom-in-95 duration-300">
             <div className="absolute top-0 right-0 w-40 h-40 bg-blue-600/10 blur-[80px] rounded-full pointer-events-none" />
             <h2 className="text-3xl md:text-4xl font-black heading-font text-white mb-10 tracking-tight leading-normal">MOD_PROTOCOL</h2>
             <div className="space-y-10">
                <div className="space-y-3">
                   <label className="text-xs font-black text-slate-400 uppercase tracking-widest block ml-4">UPDATED IDENTITY LABEL</label>
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
        <div className="fixed inset-0 bg-[#020617]/98 backdrop-blur-3xl z-[100] flex items-center justify-center p-6 md:p-16">
          <div className="glass-panel w-full max-w-5xl flex flex-col md:flex-row border-white/10 rounded-[64px] shadow-2xl animate-in zoom-in-95 duration-500 border-2 relative">
             
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
                 <div className="space-y-3">
                    <label className="text-[10px] font-black text-slate-600 uppercase tracking-widest pl-3">Capture Source</label>
                    <div className="flex gap-2 p-1 bg-[#020617] border-2 border-white/5 rounded-2xl">
                       <button onClick={() => { closeWebcam(); openWebcam('local'); }} className={`flex-1 py-3 rounded-xl text-[10px] font-black uppercase tracking-widest transition-all ${regSource === 'local' ? 'bg-blue-600 text-white shadow-lg' : 'text-slate-500 hover:text-white'}`}>Laptop Webcam</button>
                       <button onClick={() => { closeWebcam(); openWebcam('remote'); }} className={`flex-1 py-3 rounded-xl text-[10px] font-black uppercase tracking-widest transition-all ${regSource === 'remote' ? 'bg-blue-600 text-white shadow-lg' : 'text-slate-500 hover:text-white'}`}>Phone Camera</button>
                    </div>
                 </div>

                 <button onClick={captureAndRegister} disabled={!regName} className={`w-full py-8 rounded-[40px] font-black heading-font text-2xl flex items-center justify-center gap-6 transition-all ${!regName ? 'bg-slate-900 text-slate-800 opacity-50' : 'bg-white text-black hover:scale-[1.01] active:scale-95 shadow-2xl'}`}>
                   <ScannerIcon size={32} /> INITIALIZE SCAN
                </button>
             </div>

             <div className="lg:w-[450px] shrink-0 bg-black relative p-12 flex items-center justify-center">
                <div className="w-full h-full rounded-[48px] overflow-hidden relative border-4 border-white/10 shadow-[0_0_80px_rgba(59,130,246,0.2)]">
                   {regSource === 'local' ? (
                     <video ref={videoRef} autoPlay playsInline className="w-full h-full object-cover scale-x-[-1] grayscale-[0.2]" />
                   ) : (
                     <img 
                       id="sentinel-enroll-stream"
                       src={`${API_BASE}/api/stream/Gym_Camera?t=${Date.now()}`} 
                       className="w-full h-full object-cover" 
                       alt="Remote Stream"
                       crossOrigin="anonymous"
                       onError={(e) => { e.target.src = "https://via.placeholder.com/640x480?text=Camera+Offline"; }}
                     />
                   )}
                   <div className="scanner-overlay !z-10 bg-blue-900/10">
                      <div className="scanner-line !h-[6px] !bg-blue-400 !shadow-[0_0_30px_#3b82f6]"></div>
                      <div className="face-target !border-blue-500/30 !w-[280px] !h-[380px] !border-[3px] !rounded-[80px]"></div>
                      <div className="absolute top-8 left-8 flex items-center gap-4 bg-black/80 px-5 py-2 rounded-2xl backdrop-blur-3xl border border-white/10">
                          <div className={`w-2.5 h-2.5 rounded-full animate-pulse ${regSource === 'local' ? 'bg-red-600 shadow-[0_0_15px_#dc2626]' : 'bg-emerald-500 shadow-[0_0_15px_#10b981]'}`} />
                          <span className="text-[9px] font-black mono-font text-white uppercase tracking-widest">{regSource === 'local' ? 'Local Webcam' : 'Phone Link Active'}</span>
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
