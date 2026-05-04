import { useState, useEffect, useRef } from 'react';
import { 
  Shield, LayoutList, User, ShieldOff, Trash2, X, Activity, 
  Users, Clock, Edit2, Settings, History, MapPin, Download,
  ChevronRight, Bell, Search, Info, Camera, LogIn, Lock, Mail, ArrowRight, LogOut, CheckCircle, AlertTriangle, Send, ShieldAlert
} from 'lucide-react';
import './index.css';
import StreamGrid from './components/StreamGrid';
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

function formatUptimeSeconds(sec) {
  if (sec == null || sec < 0) return '0m';
  if (sec < 60) return '<1m';
  if (sec < 3600) return `${Math.floor(sec / 60)}m`;
  if (sec < 86400) return `${Math.floor(sec / 3600)}h`;
  const d = Math.floor(sec / 86400);
  const h = Math.floor((sec % 86400) / 3600);
  return h > 0 ? `${d}d ${h}h` : `${d}d`;
}

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
  const [newRole, setNewRole] = useState('');
  const [newExpiry, setNewExpiry] = useState('');
  const [userActivity, setUserActivity] = useState([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [filterType, setFilterType] = useState('all');
  const videoRef = useRef(null);
  const [regName, setRegName] = useState('');
  const [regRole, setRegRole] = useState('member');
  const [regSource, setRegSource] = useState('local'); 
  const [uploadedImage, setUploadedImage] = useState(null);
  const [snapshots, setSnapshots] = useState([]);
  const fileInputRef = useRef(null);

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
  const [whatsappQr, setWhatsappQr] = useState(null);
  const [whatsappStatus, setWhatsappStatus] = useState('Disconnected');
  const [telegramEnabled, setTelegramEnabled] = useState(false);
  const [telegramToken, setTelegramToken] = useState('');
  const [telegramChatId, setTelegramChatId] = useState('');
  const [notifyOnEntry, setNotifyOnEntry] = useState(true);
  const [notifyOnExpiry, setNotifyOnExpiry] = useState(true);
  const [isSavingSettings, setIsSavingSettings] = useState(false);
  const [activeTab, setActiveTab] = useState('dashboard');
  const [useP2P, setUseP2P] = useState(false);
  const [p2pUid, setP2pUid] = useState('');
  const [p2pUser, setP2pUser] = useState('admin');
  const [p2pPass, setP2pPass] = useState('');
  const [useOnvif, setUseOnvif] = useState(false);
  const [onvifPort, setOnvifPort] = useState(80);
  const [onvifUser, setOnvifUser] = useState('admin');
  const [onvifPass, setOnvifPass] = useState('');
  
  const [cameraName, setCameraName] = useState('Main_Entrance');
  const [savedNodes, setSavedNodes] = useState([]);
  
  const [isWebcamNodeActive, setIsWebcamNodeActive] = useState(false);
  const [browserStream, setBrowserStream] = useState(null);
  const browserVideoRef = useRef(null);
  const [lastRecognition, setLastRecognition] = useState(null);
  const [authError, setAuthError] = useState('');
  const [isAuthLoading, setIsAuthLoading] = useState(false);
  const [isSignupLoading, setIsSignupLoading] = useState(false);
  const [dashboardReady, setDashboardReady] = useState(() => !localStorage.getItem('owner_id'));
  const [apiLatencyMs, setApiLatencyMs] = useState(null);

  useEffect(() => {
    if (localStorage.getItem('owner_id')) {
      setIsLoggedIn(true);
    }
  }, []);

  const measureLatency = async () => {
    try {
      const t0 = performance.now();
      const res = await fetch(`${API_BASE}/health`, { cache: 'no-store' });
      const ms = Math.round(performance.now() - t0);
      setApiLatencyMs(res.ok ? ms : null);
    } catch {
      setApiLatencyMs(null);
    }
  };

  useEffect(() => {
    if (!isLoggedIn || !ownerId) return undefined;
    measureLatency();
    const ping = setInterval(measureLatency, 10000);
    return () => clearInterval(ping);
  }, [isLoggedIn, ownerId]);

  useEffect(() => {
    if (!isLoggedIn || !ownerId) return undefined;
    let cancelled = false;

    const bootstrap = async () => {
      setDashboardReady(false);
      await fetchData();
      if (!cancelled) setDashboardReady(true);
    };

    bootstrap();
    const interval = setInterval(fetchData, 3000);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, [isLoggedIn, ownerId]);

  const fetchData = async () => {
    if (!ownerId) return;
    try {
      const baseUrl = API_BASE;
      const cacheBuster = `?t=${Date.now()}&owner_id=${ownerId}`;
      const reqs = [
        fetch(`${baseUrl}/api/logs${cacheBuster}`),
        fetch(`${baseUrl}/api/users${cacheBuster}`),
        fetch(`${baseUrl}/api/telemetry${cacheBuster}`),
        fetch(`${baseUrl}/api/stats${cacheBuster}`),
      ];
      const settled = await Promise.allSettled(reqs);

      const read = async (idx) => {
        const entry = settled[idx];
        if (entry.status !== 'fulfilled') return;
        const res = entry.value;
        if (!res.ok) return;
        try {
          return await res.json();
        } catch {
          return null;
        }
      };

      const logsData = await read(0);
      const usersData = await read(1);
      const telemetryData = await read(2);
      const statsData = await read(3);

      if (logsData) setLogs(logsData);
      if (usersData) setUsers(usersData);
      if (telemetryData) setTelemetry(telemetryData);
      if (statsData) setStats(statsData);
    } catch (error) {
      console.error('Sync Error:', error);
    }
  };

  const fetchSettings = async () => {
    if (!ownerId) return;
    try {
      const res = await fetch(`${API_BASE}/api/settings/notifications?owner_id=${ownerId}`);
      if (res.ok) {
        const data = await res.json();
        setWebhookUrl(data.webhook_url || '');
        setTelegramEnabled(data.telegram_enabled || false);
        setTelegramToken(data.telegram_token || '');
        setTelegramChatId(data.telegram_chat_id || '');
        setNotifyOnEntry(data.notify_on_entry);
        setNotifyOnExpiry(data.notify_on_expiry);
      }
      
      const nodesRes = await fetch(`${API_BASE}/api/nodes/list?owner_id=${ownerId}`);
      if (nodesRes.ok) {
        const nData = await nodesRes.json();
        setSavedNodes(nData);
        if (nData.length > 0) {
           const n = nData[0];
           setCameraUrl(n.url);
           setCameraName(n.name);
           setUseP2P(n.use_p2p || false);
           setP2pUid(n.p2p_uid || '');
           setP2pUser(n.p2p_user || 'admin');
           setP2pPass(n.p2p_pass || '');
           setUseOnvif(n.use_onvif || false);
           setOnvifPort(n.onvif_port || 80);
           setOnvifUser(n.onvif_user || 'admin');
           setOnvifPass(n.onvif_pass || '');
        }
      }
    } catch (e) { console.error(e); }
  };

  useEffect(() => {
    if (isLoggedIn && ownerId) fetchSettings();
  }, [isLoggedIn, ownerId]);

  useEffect(() => {
    let interval;
    if (isWebcamNodeActive) {
      const startWebcam = async () => {
        try {
          const stream = await navigator.mediaDevices.getUserMedia({ video: { width: 640, height: 480 } });
          setBrowserStream(stream);
          if (browserVideoRef.current) browserVideoRef.current.srcObject = stream;
          
          interval = setInterval(async () => {
            if (browserVideoRef.current) {
              const canvas = document.createElement('canvas');
              canvas.width = browserVideoRef.current.videoWidth;
              canvas.height = browserVideoRef.current.videoHeight;
              const ctx = canvas.getContext('2d');
              ctx.drawImage(browserVideoRef.current, 0, 0);
              const base64 = canvas.toDataURL('image/jpeg', 0.7);
              
              try {
                const res = await fetch(`${API_BASE}/api/recognize/crop`, {
                  method: 'POST',
                  headers: { 'Content-Type': 'application/json' },
                  body: JSON.stringify({
                    image_base64: base64,
                    node_name: "BROWSER_WEBCAM",
                    owner_id: parseInt(ownerId)
                  })
                });
                const data = await res.json();
                if (data.status === 'success' && data.name !== 'Scanning...') {
                  setLastRecognition(data);
                  setTimeout(() => setLastRecognition(null), 5000);
                }
              } catch (e) { console.error("Recognition Error:", e); }
            }
          }, 3000);
        } catch (e) {
          console.error("Webcam Error:", e);
          setIsWebcamNodeActive(false);
        }
      };
      startWebcam();
    } else {
      if (browserStream) {
        browserStream.getTracks().forEach(t => t.stop());
        setBrowserStream(null);
      }
      clearInterval(interval);
    }
    return () => {
      if (browserStream) browserStream.getTracks().forEach(t => t.stop());
      clearInterval(interval);
    };
  }, [isWebcamNodeActive]);

  useEffect(() => {
    let qrInterval;
    if (activeTab === 'settings') {
      qrInterval = setInterval(async () => {
        try {
          const res = await fetch(`${API_BASE}/api/whatsapp/qr`);
          const data = await res.json();
          setWhatsappQr(data.qr);
          setWhatsappStatus(data.status);
        } catch (e) {}
      }, 5000);
    }
    return () => clearInterval(qrInterval);
  }, [activeTab]);

  const handleLogoutWA = async () => {
     try {
       await fetch(`${API_BASE}/api/whatsapp/logout`, { method: 'POST' });
       alert("Logged out from WhatsApp");
     } catch (e) {}
  };

  const saveNotificationSettings = async () => {
    setIsSavingSettings(true);
    try {
      await fetch(`${API_BASE}/api/settings/notifications`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          owner_id: ownerId,
          webhook_url: webhookUrl,
          whatsapp_enabled: true,
          whatsapp_number: "",
          whatsapp_api_key: "",
          whatsapp_provider: "native",
          telegram_enabled: telegramEnabled,
          telegram_token: telegramToken,
          telegram_chat_id: telegramChatId,
          notify_on_entry: notifyOnEntry,
          notify_on_expiry: notifyOnExpiry
        })
      });
      alert("Settings Saved Successfully!");
    } catch (e) { alert("Failed to save settings"); }
    setIsSavingSettings(false);
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
      } catch (e) { console.error("Webcam Error:", e); }
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
      } else if (regSource === 'remote') {
        const streamImg = document.getElementById('sentinel-enroll-stream');
        if (!streamImg) return;
        const canvas = document.createElement('canvas');
        canvas.width = streamImg.naturalWidth || 640;
        canvas.height = streamImg.naturalHeight || 480;
        canvas.getContext('2d').drawImage(streamImg, 0, 0);
        frameData = canvas.toDataURL('image/jpeg');
      } else if (regSource === 'file') {
        frameData = uploadedImage;
      }
      
      if (!frameData) return alert("Failed to capture image");

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
      } else { alert("Error: " + data.message); }
    } catch (e) { alert("Registration failed: " + e.message); }
  };

  const detailFromBody = (body) => {
    const d = body?.detail;
    if (typeof d === 'string') return d;
    if (Array.isArray(d) && d[0]?.msg) return d[0].msg;
    return null;
  };

  const handleLogin = async (e) => {
    e?.preventDefault?.();
    setAuthError('');
    if (!identifier || !password) {
      setAuthError('Please enter your identifier and password.');
      return;
    }
    setIsAuthLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ identifier, password })
      });
      const data = await res.json().catch(() => ({}));
      if (res.ok) {
        setOwnerId(String(data.owner_id));
        setCurrentGymName(data.gym_name);
        localStorage.setItem('owner_id', String(data.owner_id));
        localStorage.setItem('gym_name', data.gym_name);
        setPassword('');
        setIsLoggedIn(true);
      } else {
        setAuthError(detailFromBody(data) || 'Invalid credentials');
      }
    } catch {
      setAuthError('Network error. Check your connection and try again.');
    } finally {
      setIsAuthLoading(false);
    }
  };

  const handleSignup = async (e) => {
    e?.preventDefault?.();
    setAuthError('');
    if (!gymName || !email || !mobile || !password || !confirmPassword) {
      setAuthError('Please fill all fields.');
      return;
    }
    if (password !== confirmPassword) {
      setAuthError('Passwords do not match.');
      return;
    }
    setIsSignupLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/auth/signup`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ gym_name: gymName, email, mobile, password })
      });
      const data = await res.json().catch(() => ({}));
      if (res.ok) {
        setAuthMode('login');
        setAuthError('');
        setIdentifier(email);
      } else {
        setAuthError(detailFromBody(data) || 'Sign up failed');
      }
    } catch {
      setAuthError('Network error. Check your connection and try again.');
    } finally {
      setIsSignupLoading(false);
    }
  };

  const handleUpdateProfile = async () => {
    if (!editingUser) return;
    try {
      await fetch(`${API_BASE}/api/users/${editingUser.id}/update`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: newName, role: newRole, subscription_expiry: newExpiry }),
      });
      fetchData();
      setEditingUser(null);
    } catch (err) { console.error(err); }
  };

  const handleUpdateNode = async () => {
    if (!cameraUrl) return alert("Please enter a valid Stream Link");
    try {
      await fetch(`${API_BASE}/api/nodes/add`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: cameraName || "Gym_Camera",
          url: cameraUrl,
          owner_id: ownerId,
          use_p2p: useP2P,
          p2p_uid: p2pUid,
          p2p_user: p2pUser,
          p2p_pass: p2pPass,
          use_onvif: useOnvif,
          onvif_port: parseInt(onvifPort) || 80,
          onvif_user: onvifUser,
          onvif_pass: onvifPass
        })
      });
      alert(`Node '${cameraName || "Gym_Camera"}' initialized!`);
      fetchSettings();
    } catch (e) { alert("Failed to add node."); }
  };

  const handleDeleteNode = async (nodeName) => {
    if (!confirm(`Delete ${nodeName}?`)) return;
    try {
      await fetch(`${API_BASE}/api/nodes/${nodeName}?owner_id=${ownerId}`, { method: 'DELETE' });
      fetchSettings();
    } catch (e) { alert("Failed to delete node."); }
  };

  if (!isLoggedIn) {
    return (
      <div className="min-h-screen w-full bg-[#020617] flex items-center justify-center p-6 relative overflow-hidden">
        <div className="glass-panel w-full max-w-sm p-12 border-white/10 rounded-[40px] shadow-2xl relative z-20 flex flex-col items-center">
            <div className="w-16 h-16 bg-blue-600 rounded-2xl flex items-center justify-center shadow-2xl shadow-blue-600/30 mb-8"><Shield size={32} className="text-white" /></div>
            <h1 className="text-3xl font-black heading-font text-white tracking-tighter mb-2 uppercase">Sentinel AI</h1>
            <p className="text-slate-500 text-[9px] font-black uppercase tracking-[0.3em] mb-6">{authMode === 'login' ? 'Gym Owner Login' : 'Gym Owner Sign Up'}</p>
            {authError ? (
              <div className="w-full mb-4 px-4 py-3 rounded-xl bg-red-500/10 border border-red-500/20 text-red-300 text-[11px] font-bold text-left" role="alert">{authError}</div>
            ) : null}
            <form className="w-full space-y-6" onSubmit={authMode === 'login' ? handleLogin : handleSignup}>
                {authMode === 'signup' && (
                  <>
                  <div className="space-y-3"><span className="text-[10px] font-black text-slate-500 uppercase tracking-widest block ml-2">GYM NAME</span><div className="flex items-center bg-[#020617] border-2 border-white/5 rounded-2xl px-5 py-4 focus-within:border-blue-600 transition-all"><LayoutList className="text-slate-600 shrink-0" size={18} /><input type="text" value={gymName} onChange={e => setGymName(e.target.value)} placeholder="Power Fitness Gym" className="w-full bg-transparent border-none text-sm text-white font-bold focus:outline-none placeholder:text-slate-700 ml-4" autoComplete="organization" /></div></div>
                  <div className="space-y-3"><span className="text-[10px] font-black text-slate-500 uppercase tracking-widest block ml-2">EMAIL</span><div className="flex items-center bg-[#020617] border-2 border-white/5 rounded-2xl px-5 py-4 focus-within:border-blue-600 transition-all"><Mail className="text-slate-600 shrink-0" size={18} /><input type="email" value={email} onChange={e => setEmail(e.target.value)} placeholder="owner@example.com" className="w-full bg-transparent border-none text-sm text-white font-bold focus:outline-none placeholder:text-slate-700 ml-4" autoComplete="email" /></div></div>
                  <div className="space-y-3"><span className="text-[10px] font-black text-slate-500 uppercase tracking-widest block ml-2">MOBILE</span><div className="flex items-center bg-[#020617] border-2 border-white/5 rounded-2xl px-5 py-4 focus-within:border-blue-600 transition-all"><User className="text-slate-600 shrink-0" size={18} /><input type="tel" value={mobile} onChange={e => setMobile(e.target.value)} placeholder="+1 555 000 0000" className="w-full bg-transparent border-none text-sm text-white font-bold focus:outline-none placeholder:text-slate-700 ml-4" autoComplete="tel" /></div></div>
                  </>
                )}
                {authMode === 'login' && (
                <div className="space-y-3"><span className="text-[10px] font-black text-slate-500 uppercase tracking-widest block ml-2">IDENTIFIER</span><div className="flex items-center bg-[#020617] border-2 border-white/5 rounded-2xl px-5 py-4 focus-within:border-blue-600 transition-all"><User className="text-slate-600 shrink-0" size={18} /><input type="text" value={identifier} onChange={e => setIdentifier(e.target.value)} placeholder="Email or Mobile" className="w-full bg-transparent border-none text-sm text-white font-bold focus:outline-none placeholder:text-slate-700 ml-4" autoComplete="username" /></div></div>
                )}
                <div className="space-y-3"><span className="text-[10px] font-black text-slate-500 uppercase tracking-widest block ml-2">PASSWORD</span><div className="flex items-center bg-[#020617] border-2 border-white/5 rounded-2xl px-5 py-4 focus-within:border-blue-600 transition-all"><Lock className="text-slate-600 shrink-0" size={18} /><input type="password" value={password} onChange={e => setPassword(e.target.value)} placeholder="••••••••" className="w-full bg-transparent border-none text-sm text-white font-bold focus:outline-none placeholder:text-slate-700 ml-4" autoComplete={authMode === 'login' ? 'current-password' : 'new-password'} /></div></div>
                {authMode === 'signup' && (
                <div className="space-y-3"><span className="text-[10px] font-black text-slate-500 uppercase tracking-widest block ml-2">CONFIRM PASSWORD</span><div className="flex items-center bg-[#020617] border-2 border-white/5 rounded-2xl px-5 py-4 focus-within:border-blue-600 transition-all"><Lock className="text-slate-600 shrink-0" size={18} /><input type="password" value={confirmPassword} onChange={e => setConfirmPassword(e.target.value)} placeholder="••••••••" className="w-full bg-transparent border-none text-sm text-white font-bold focus:outline-none placeholder:text-slate-700 ml-4" autoComplete="new-password" /></div></div>
                )}
            <button type="submit" disabled={isAuthLoading || isSignupLoading} className="w-full bg-white text-black py-4 rounded-2xl font-black heading-font text-base flex items-center justify-center gap-3 mt-10 hover:bg-slate-200 transition-all active:scale-95 disabled:opacity-50 disabled:pointer-events-none">
              {(authMode === 'login' ? isAuthLoading : isSignupLoading) ? (
                <span className="flex items-center gap-2"><span className="w-4 h-4 border-2 border-black/30 border-t-black rounded-full animate-spin inline-block" aria-hidden /> Please wait</span>
              ) : (
                <>{authMode === 'login' ? 'LOG IN' : 'SIGN UP'} <ArrowRight size={18} /></>
              )}
            </button>
            </form>
            <button type="button" onClick={() => { setAuthError(''); setAuthMode(authMode === 'login' ? 'signup' : 'login'); }} className="mt-8 text-[9px] font-black text-slate-600 uppercase tracking-widest hover:text-blue-500 transition-colors">{authMode === 'login' ? 'New user? Sign Up here' : 'Already have an account? Log In'}</button>
        </div>
      </div>
    );
  }

  const summary = stats?.summary;
  const registeredCount = summary?.total_members ?? users.length;
  const visits24h = summary?.visits_last_24h ?? 0;
  const expiriesCount = summary?.expired_members ?? users.filter((u) => u.subscription_status === 'expired').length;
  const uptimeLabel = formatUptimeSeconds(summary?.server_uptime_seconds ?? 0);
  const weekTrend = stats?.weekly_trend || [];
  const peakHours = stats?.peak_hours || [];
  const hasWeekData = weekTrend.some((d) => (d.count ?? 0) > 0);
  const hasPeakData = peakHours.some((d) => (d.count ?? 0) > 0);

  return (
    <div className="min-h-screen w-full bg-[#020617] text-slate-100 selection:bg-blue-500/30">
      {isLoggedIn && !dashboardReady && (
        <div className="fixed inset-0 z-[60] flex items-center justify-center bg-[#020617]/75 backdrop-blur-sm">
          <div className="glass-panel px-10 py-7 rounded-2xl border border-white/10 flex items-center gap-4 shadow-2xl">
            <div className="w-7 h-7 border-2 border-blue-500/30 border-t-blue-500 rounded-full animate-spin" aria-hidden />
            <span className="text-xs font-black text-white uppercase tracking-widest">Loading your workspace</span>
          </div>
        </div>
      )}
      <div className={`max-w-[1400px] mx-auto flex flex-col relative z-20 transition-opacity duration-300 ${dashboardReady ? 'opacity-100' : 'opacity-60'}`}>
        <nav className="flex items-center justify-between py-5 px-6 border-b border-white/5 bg-[#020617]/50 backdrop-blur-3xl sticky top-0 z-50">
          <div className="flex items-center gap-4 shrink-0"><div className="w-9 h-9 bg-blue-600 rounded-lg flex items-center justify-center shadow-xl shadow-blue-600/30"><Shield size={18} className="text-white" /></div><h1 className="text-sm font-black heading-font text-white leading-none tracking-tighter uppercase">{currentGymName || 'Sentinel_AI'}</h1></div>
          <div className="flex items-center gap-1 bg-white/5 p-1 rounded-xl border border-white/10 shrink-0">
            {['dashboard', 'logs', 'registry', 'settings'].map(tab => (
              <button key={tab} type="button" onClick={() => setActiveTab(tab)} className={`px-5 py-2 rounded-lg text-[9px] font-black uppercase tracking-widest transition-all ${activeTab === tab ? 'bg-blue-600 text-white shadow-lg' : 'text-slate-500 hover:text-white'}`}>{tab === 'dashboard' ? 'Analytics' : tab === 'logs' ? 'Activity' : tab === 'registry' ? 'Registry' : 'Nodes'}</button>
            ))}
          </div>
          <div className="flex items-center gap-3">
            <button type="button" onClick={() => openWebcam('local')} className="py-2.5 px-6 rounded-xl flex items-center gap-2 bg-blue-600 text-white hover:bg-blue-500 font-black text-[9px] uppercase tracking-widest transition-all shadow-xl active:scale-95 shrink-0"><Camera size={14} /> Master Enroll</button>
            <button type="button" onClick={() => { localStorage.removeItem('owner_id'); localStorage.removeItem('gym_name'); setOwnerId(null); setIsLoggedIn(false); setDashboardReady(true); }} className="w-9 h-9 rounded-xl flex items-center justify-center bg-white/5 border border-white/10 text-slate-500 hover:text-red-500 transition-all shrink-0" title="Sign out"><LogOut size={16} /></button>
          </div>
        </nav>

        <main className="p-8 md:p-10 flex-1 flex flex-col gap-10">
          <header className="flex justify-between items-end border-b-2 border-white/5 pb-6 text-left">
            <div><h2 className="text-3xl font-black heading-font text-white tracking-widest uppercase mb-2">{activeTab.toUpperCase()} PROTOCOL</h2><div className="flex items-center gap-2"><div className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" /><p className="text-slate-600 text-[9px] font-black uppercase tracking-widest">Active surveillance stream ready</p></div></div>
            <div className="text-right">
              <span className="text-[10px] font-black text-slate-600 uppercase tracking-widest block">API latency</span>
              <span className={`text-md font-black tabular-nums ${apiLatencyMs != null && apiLatencyMs < 800 ? 'text-emerald-500' : 'text-amber-500'}`}>
                {apiLatencyMs != null ? `${apiLatencyMs} ms` : '—'}
              </span>
            </div>
          </header>

          <div className="grid grid-cols-1 lg:grid-cols-12 gap-10">
             <div className="lg:col-span-12 flex flex-col gap-6">
                <div className="glass-panel bg-white/[0.01] border-white/5 rounded-[40px] flex flex-col min-h-[500px] shadow-2xl overflow-hidden">
                    <div className="p-8 pb-4 flex flex-wrap justify-between items-center gap-6 text-left"><h3 className="heading-font font-black text-[12px] text-slate-500 tracking-widest uppercase pl-2">System_Output</h3></div>
                    <div className="flex-1 overflow-y-auto custom-scroll p-4">
                        {activeTab === 'dashboard' ? (
                          <div className="space-y-8 p-4 text-left">
                            <div className="glass-panel p-8 bg-white/[0.01] border-white/5 rounded-[40px]">
                              <div className="flex items-center justify-between mb-8">
                                <div><h3 className="text-lg font-black text-white uppercase tracking-tighter">Live Surveillance Feed</h3><p className="text-[9px] text-slate-500 font-bold uppercase tracking-widest">Active Neural Tracking Nodes</p></div>
                                <button onClick={() => setIsWebcamNodeActive(!isWebcamNodeActive)} className={`px-6 py-2.5 rounded-xl text-[9px] font-black uppercase transition-all flex items-center gap-2 ${isWebcamNodeActive ? 'bg-red-600 text-white' : 'bg-blue-600/20 text-blue-400 border border-blue-500/20'}`}><Camera size={14} /> {isWebcamNodeActive ? 'Disconnect Webcam' : 'Connect Webcam'}</button>
                              </div>
                              <div className="flex flex-col lg:flex-row gap-8">
                                <div className="flex-1"><StreamGrid telemetry={telemetry} savedCameraCount={savedNodes.length} onSnapshot={(img) => setSnapshots(prev => [{id: Date.now(), img, time: new Date().toISOString()}, ...prev].slice(0, 5))} /></div>
                                <div className="lg:w-[300px] flex flex-col gap-6">
                                   <div className="glass-panel p-6 bg-blue-600/5 border border-blue-600/20 rounded-3xl"><h3 className="text-[10px] font-black text-white uppercase mb-4">Security Notice</h3><p className="text-[10px] text-slate-500 font-bold leading-relaxed">System is performing real-time biometric hashing. All unrecognized identities are flagged.</p></div>
                                   {lastRecognition && (<div className="glass-panel p-6 bg-emerald-500/10 border border-emerald-500/20 rounded-3xl animate-in zoom-in-95"><div className="text-[8px] font-black text-emerald-500 uppercase tracking-widest mb-1">Identity Confirmed</div><div className="text-xl font-black text-white">{lastRecognition.name}</div></div>)}
                                </div>
                              </div>
                            </div>
                            <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
                               {[
                                 { l: 'Registered', v: registeredCount, i: Users, c: 'text-blue-500' },
                                 { l: 'Visits 24h', v: visits24h, i: Activity, c: 'text-emerald-500' },
                                 { l: 'Expiries', v: expiriesCount, i: ShieldAlert, c: 'text-red-500' },
                                 { l: 'Uptime', v: uptimeLabel, i: Settings, c: 'text-purple-500' }
                               ].map((stat, i) => (
                                 <div key={i} className="glass-panel p-6 bg-white/[0.01] border-white/5 rounded-3xl flex flex-col gap-2">
                                    <stat.i className={stat.c} size={24} /><div className="text-2xl font-black text-white tracking-tighter">{stat.v}</div><div className="text-[8px] text-slate-500 font-black uppercase tracking-widest">{stat.l}</div>
                                 </div>
                               ))}
                            </div>
                            <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
                               <div className="glass-panel p-8 bg-white/[0.01] rounded-[40px] h-[300px] flex flex-col relative"><h4 className="text-[10px] font-black text-slate-500 uppercase tracking-widest mb-6">Attendance Trend</h4><div className="flex-1 min-h-0 relative">{!hasWeekData ? (<div className="absolute inset-0 flex items-center justify-center z-10 text-center px-6"><p className="text-[11px] text-slate-600 font-bold">No check-ins in the last 7 days yet. Visits will appear here once members are recognized.</p></div>) : null}<ResponsiveContainer width="100%" height="100%"><AreaChart data={weekTrend}><defs><linearGradient id="colorCount" x1="0" y1="0" x2="0" y2="1"><stop offset="5%" stopColor="#2563eb" stopOpacity={0.3}/><stop offset="95%" stopColor="#2563eb" stopOpacity={0}/></linearGradient></defs><CartesianGrid strokeDasharray="3 3" stroke="#ffffff05" vertical={false} /><XAxis dataKey="day" hide /><YAxis hide /><Tooltip contentStyle={{backgroundColor: '#020617', border: '1px solid #ffffff10', borderRadius: '12px'}} /><Area type="monotone" dataKey="count" stroke="#2563eb" strokeWidth={3} fillOpacity={1} fill="url(#colorCount)" /></AreaChart></ResponsiveContainer></div></div>
                               <div className="glass-panel p-8 bg-white/[0.01] rounded-[40px] h-[300px] flex flex-col relative"><h4 className="text-[10px] font-black text-slate-500 uppercase tracking-widest mb-6">Peak Activity</h4><div className="flex-1 min-h-0 relative">{!hasPeakData ? (<div className="absolute inset-0 flex items-center justify-center z-10 text-center px-6"><p className="text-[11px] text-slate-600 font-bold">No visits recorded today between 6:00 and 22:00 yet.</p></div>) : null}<ResponsiveContainer width="100%" height="100%"><BarChart data={peakHours}><CartesianGrid strokeDasharray="3 3" stroke="#ffffff05" vertical={false} /><XAxis dataKey="hour" hide /><YAxis hide /><Bar dataKey="count" radius={[4, 4, 0, 0]}>{peakHours.map((e, idx) => (<Cell key={`cell-${idx}`} fill={e.count > 0 ? '#2563eb' : '#ffffff05'} />))}</Bar></BarChart></ResponsiveContainer></div></div>
                            </div>
                          </div>
                        ) : activeTab === 'registry' ? (
                          <div className="w-full h-full text-left p-4">
                             <div className="flex gap-2 mb-8 overflow-x-auto pb-2">{['all', 'active', 'expired'].map(f => (<button key={f} onClick={() => setFilterType(f)} className={`px-6 py-3 rounded-2xl font-black text-[10px] uppercase tracking-widest transition-all ${filterType === f ? 'bg-blue-600 text-white' : 'bg-white/5 text-slate-500'}`}>{f}</button>))}</div>
                             <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                                {users.filter(u => {
                                   const matchesSearch = u.name.toLowerCase().includes(searchQuery.toLowerCase());
                                   const isExpired = u.subscription_expiry != null && new Date(u.subscription_expiry) < new Date();
                                   if (filterType === 'active') return matchesSearch && !isExpired;
                                   if (filterType === 'expired') return matchesSearch && isExpired;
                                   return matchesSearch;
                                }).map(u => (
                                <div key={u.id} className="glass-panel p-4 flex items-center justify-between bg-white/[0.015] rounded-[24px] group">
                                   <div className="flex items-center gap-4"><div className="w-14 h-14 rounded-2xl overflow-hidden border-2 border-white/5"><img src={u.image_path?.startsWith('http') ? u.image_path : `${API_BASE}/${u.image_path}`} className="w-full h-full object-cover grayscale group-hover:grayscale-0 transition-all" alt="" /></div><div><div className="text-md font-black text-white uppercase tracking-tighter leading-none">{u.name}</div><div className="text-[7px] font-black text-slate-500 uppercase mt-2 px-1.5 py-0.5 bg-white/5 rounded w-fit">Exp: {u.subscription_expiry ? new Date(u.subscription_expiry).toLocaleDateString() : 'No Plan'}</div></div></div>
                                   <div className="flex gap-1.5"><button onClick={() => {setEditingUser(u); setNewName(u.name); setNewRole(u.role); setNewExpiry(u.subscription_expiry ? u.subscription_expiry.split('T')[0] : '');}} className="w-9 h-9 flex items-center justify-center rounded-xl bg-white/5 text-slate-600 hover:bg-blue-600 hover:text-white transition-all"><Edit2 size={15} /></button><button onClick={() => deleteUser(u.id)} className="w-9 h-9 flex items-center justify-center rounded-xl bg-white/5 text-slate-600 hover:bg-red-600 hover:text-white transition-all"><Trash2 size={15} /></button></div>
                                </div>
                             ))}
                             {users.length === 0 ? (
                               <div className="col-span-full py-16 text-center text-slate-600 text-sm font-bold">No members enrolled yet. Use Master Enroll to add your first member.</div>
                             ) : users.filter(u => {
                                   const matchesSearch = u.name.toLowerCase().includes(searchQuery.toLowerCase());
                                   const isExpired = u.subscription_expiry != null && new Date(u.subscription_expiry) < new Date();
                                   if (filterType === 'active') return matchesSearch && !isExpired;
                                   if (filterType === 'expired') return matchesSearch && isExpired;
                                   return matchesSearch;
                                }).length === 0 ? (
                               <div className="col-span-full py-16 text-center text-slate-600 text-sm font-bold">No members match this filter.</div>
                             ) : null}
                             </div>
                          </div>
                        ) : activeTab === 'settings' ? (
                          <div className="p-8 space-y-12 max-w-4xl text-left">
                              <div className="glass-panel p-8 bg-white/[0.01] rounded-[40px] space-y-8 shadow-2xl">
                                <div className="border-b border-white/5 pb-4"><h3 className="text-xl font-black text-white uppercase tracking-tighter">Node Configuration</h3><p className="text-[10px] text-slate-500 font-bold uppercase tracking-widest mt-1">Connect surveillance hardware</p></div>
                                <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
                                   <div className="space-y-3"><label className="text-[10px] font-black text-slate-500 uppercase tracking-widest block ml-2">Node Label</label><div className="flex items-center bg-[#020617] border-2 border-white/5 rounded-2xl px-5 py-4"><Activity className="text-blue-500 shrink-0" size={18} /><input type="text" value={cameraName} onChange={e => setCameraName(e.target.value)} className="w-full bg-transparent border-none text-sm text-white font-bold ml-4 focus:outline-none" /></div></div>
                                   <div className="space-y-3"><label className="text-[10px] font-black text-slate-500 uppercase tracking-widest block ml-2">RTSP Link</label><div className="flex items-center bg-[#020617] border-2 border-white/5 rounded-2xl px-5 py-4"><Camera className="text-blue-500 shrink-0" size={18} /><input type="text" value={cameraUrl} onChange={e => setCameraUrl(e.target.value)} className="w-full bg-transparent border-none text-sm text-white font-bold ml-4 focus:outline-none" /></div></div>
                                </div>

                                {/* P2P CONFIGURATION */}
                                <div className="glass-panel p-6 bg-white/[0.01] rounded-3xl space-y-4 border border-white/5">
                                   <div className="flex items-center justify-between">
                                      <div className="flex items-center gap-3"><div className={`w-8 h-8 rounded-lg flex items-center justify-center ${useP2P ? 'bg-blue-500/20 text-blue-400' : 'bg-white/5 text-slate-600'}`}><MapPin size={16} /></div><span className="text-[10px] font-black text-white uppercase">P2P Tunneling</span></div>
                                      <button onClick={() => setUseP2P(!useP2P)} className={`w-10 h-5 rounded-full p-1 transition-all ${useP2P ? 'bg-blue-500' : 'bg-slate-800'}`}><div className={`w-3 h-3 bg-white rounded-full transition-all ${useP2P ? 'translate-x-5' : 'translate-x-0'}`} /></button>
                                   </div>
                                   {useP2P && (
                                      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 animate-in slide-in-from-top-2">
                                         <input value={p2pUid} onChange={e => setP2pUid(e.target.value)} placeholder="P2P UID" className="bg-[#020617] border border-white/5 rounded-xl py-3 px-4 text-xs text-white" />
                                         <input value={p2pUser} onChange={e => setP2pUser(e.target.value)} placeholder="User" className="bg-[#020617] border border-white/5 rounded-xl py-3 px-4 text-xs text-white" />
                                         <input type="password" value={p2pPass} onChange={e => setP2pPass(e.target.value)} placeholder="Pass" className="bg-[#020617] border border-white/5 rounded-xl py-3 px-4 text-xs text-white" />
                                      </div>
                                   )}
                                </div>

                                {/* ONVIF CONFIGURATION */}
                                <div className="glass-panel p-6 bg-white/[0.01] rounded-3xl space-y-4 border border-white/5">
                                   <div className="flex items-center justify-between">
                                      <div className="flex items-center gap-3"><div className={`w-8 h-8 rounded-lg flex items-center justify-center ${useOnvif ? 'bg-purple-500/20 text-purple-400' : 'bg-white/5 text-slate-600'}`}><Settings size={16} /></div><span className="text-[10px] font-black text-white uppercase">ONVIF Discovery</span></div>
                                      <button onClick={() => setUseOnvif(!useOnvif)} className={`w-10 h-5 rounded-full p-1 transition-all ${useOnvif ? 'bg-purple-500' : 'bg-slate-800'}`}><div className={`w-3 h-3 bg-white rounded-full transition-all ${useOnvif ? 'translate-x-5' : 'translate-x-0'}`} /></button>
                                   </div>
                                   {useOnvif && (
                                      <div className="grid grid-cols-1 md:grid-cols-4 gap-4 animate-in slide-in-from-top-2">
                                         <input type="number" value={onvifPort} onChange={e => setOnvifPort(e.target.value)} placeholder="Port (80)" className="bg-[#020617] border border-white/5 rounded-xl py-3 px-4 text-xs text-white" />
                                         <input value={onvifUser} onChange={e => setOnvifUser(e.target.value)} placeholder="User" className="bg-[#020617] border border-white/5 rounded-xl py-3 px-4 text-xs text-white" />
                                         <input type="password" value={onvifPass} onChange={e => setOnvifPass(e.target.value)} placeholder="Pass" className="bg-[#020617] border border-white/5 rounded-xl py-3 px-4 text-xs text-white" />
                                      </div>
                                   )}
                                </div>
                                <button onClick={handleUpdateNode} className="w-full md:w-auto px-10 py-5 bg-blue-600 text-white rounded-[20px] font-black text-sm flex items-center justify-center gap-3 hover:bg-blue-500 transition-all shadow-xl active:scale-95">ADD / UPDATE NODE <ArrowRight size={18} /></button>
                              </div>
                              <div className="glass-panel p-8 bg-white/[0.01] rounded-[40px] space-y-6 shadow-2xl">
                                 <div className="border-b border-white/5 pb-4"><h3 className="text-xl font-black text-white uppercase tracking-tighter">Active Nodes</h3></div>
                                 <div className="grid grid-cols-1 gap-4">
                                   {savedNodes.length === 0 ? (
                                     <p className="text-[12px] text-slate-600 font-bold py-6 text-center">No cameras saved yet. Add a node label and RTSP link above, then click Add / Update Node.</p>
                                   ) : savedNodes.map(node => (
                                     <div key={node.name} className="flex items-center justify-between p-4 bg-[#020617] border-2 border-white/5 rounded-3xl hover:border-blue-500/50 transition-all group">
                                       <div className="flex items-center gap-5"><div className="w-12 h-12 bg-blue-600/10 rounded-2xl flex items-center justify-center text-blue-500"><Camera size={20} /></div><div><div className="text-sm font-black text-white uppercase">{node.name}</div><div className="text-[9px] text-slate-500 truncate mt-1 w-[200px] md:w-[400px]">{node.url}</div></div></div>
                                       <button type="button" onClick={() => handleDeleteNode(node.name)} className="w-12 h-12 flex items-center justify-center bg-white/5 text-slate-500 rounded-2xl hover:bg-red-500 hover:text-white transition-all"><Trash2 size={18} /></button>
                                     </div>
                                   ))}
                                 </div>
                              </div>
                              <div className="glass-panel p-8 bg-white/[0.01] rounded-[40px] space-y-8 shadow-2xl">
                                 <div className="border-b border-white/5 pb-4"><h3 className="text-xl font-black text-white uppercase tracking-tighter">Smart Alerts</h3><p className="text-[10px] text-slate-500 font-bold uppercase tracking-widest mt-1">Multi-channel delivery system</p></div>
                                 <div className="space-y-6">
                                    <div className="glass-panel p-8 bg-white/[0.02] border-2 border-white/10 rounded-[32px] flex flex-col md:flex-row items-center gap-10">
                                       <div className="shrink-0">{whatsappStatus === 'Connected' ? (<div className="w-40 h-40 bg-emerald-500/10 rounded-[32px] border-4 border-emerald-500/20 flex flex-col items-center justify-center gap-4"><CheckCircle size={40} className="text-emerald-500" /><button onClick={handleLogoutWA} className="text-[9px] text-slate-500 underline uppercase font-black">Logout</button></div>) : (<div className="p-4 bg-white rounded-[32px]">{whatsappQr ? <img src={whatsappQr} className="w-32 h-32" alt="QR" /> : <div className="w-32 h-32 flex items-center justify-center text-black text-[9px] font-black">SCANNING...</div>}</div>)}</div>
                                       <div className="flex-1"><h3 className="text-xl font-black text-white uppercase mb-2">WhatsApp Bridge</h3><p className="text-[10px] text-slate-500 font-bold leading-relaxed mb-4">Scan the QR code with your WhatsApp app (Linked Devices) to send AI alerts directly from your number.</p><div className={`px-4 py-1.5 rounded-full text-[8px] font-black uppercase w-fit ${whatsappStatus === 'Connected' ? 'bg-emerald-500/20 text-emerald-400' : 'bg-red-500/20 text-red-400'}`}>Status: {whatsappStatus}</div></div>
                                    </div>
                                    <div className="glass-panel p-8 bg-white/[0.01] rounded-[32px] space-y-6">
                                       <div className="flex items-center justify-between"><div className="flex items-center gap-4"><div className={`w-10 h-10 rounded-xl flex items-center justify-center ${telegramEnabled ? 'bg-blue-400/10 text-blue-400' : 'bg-white/5 text-slate-500'}`}><Send size={20} /></div><div><h3 className="text-sm font-black text-white uppercase">Telegram Bot</h3><p className="text-[9px] text-slate-500 font-bold uppercase mt-1">Free instant notifications</p></div></div><button onClick={() => setTelegramEnabled(!telegramEnabled)} className={`w-12 h-6 rounded-full p-1 transition-all ${telegramEnabled ? 'bg-blue-500' : 'bg-slate-800'}`}><div className={`w-4 h-4 bg-white rounded-full transition-all ${telegramEnabled ? 'translate-x-6' : 'translate-x-0'}`} /></button></div>
                                       {telegramEnabled && (<div className="grid grid-cols-1 md:grid-cols-2 gap-4 animate-in slide-in-from-top-4"><input type="password" value={telegramToken} onChange={e => setTelegramToken(e.target.value)} placeholder="Bot Token" className="w-full bg-[#020617] border-2 border-white/5 rounded-xl py-4 px-6 text-white font-bold text-xs focus:border-blue-600 outline-none" /><input value={telegramChatId} onChange={e => setTelegramChatId(e.target.value)} placeholder="Chat ID" className="w-full bg-[#020617] border-2 border-white/5 rounded-xl py-4 px-6 text-white font-bold text-xs focus:border-blue-600 outline-none" /></div>)}
                                    </div>
                                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                                      <button onClick={() => setNotifyOnEntry(!notifyOnEntry)} className={`p-6 rounded-3xl border-2 flex items-center justify-between transition-all ${notifyOnEntry ? 'bg-blue-600/10 border-blue-600 text-white' : 'bg-white/5 border-white/5 text-slate-500'}`}><div><span className="text-[8px] font-black uppercase block opacity-60">Every Scan</span><span className="text-xs font-black">Notify on Entry</span></div><CheckCircle size={24} /></button>
                                      <button onClick={() => setNotifyOnExpiry(!notifyOnExpiry)} className={`p-6 rounded-3xl border-2 flex items-center justify-between transition-all ${notifyOnExpiry ? 'bg-red-500/10 border-red-500 text-white' : 'bg-white/5 border-white/5 text-slate-500'}`}><div><span className="text-[8px] font-black uppercase block opacity-60">Critical</span><span className="text-xs font-black">Notify Expiries</span></div><AlertTriangle size={24} /></button>
                                    </div>
                                    <button onClick={saveNotificationSettings} className="w-full md:w-auto px-10 py-5 bg-emerald-600 text-white rounded-[20px] font-black text-sm flex items-center justify-center gap-3 hover:bg-emerald-500 transition-all shadow-xl disabled:opacity-50" disabled={isSavingSettings}>{isSavingSettings ? 'SAVING...' : 'SAVE CONFIGURATION'} <CheckCircle size={18} /></button>
                                 </div>
                              </div>
                          </div>
                        ) : (
                          <div className="divide-y divide-white/5 min-h-[200px]">
                             {logs.length === 0 ? (
                               <div className="p-16 flex flex-col items-center justify-center text-center gap-3">
                                 <History className="text-slate-700 opacity-40" size={40} />
                                 <p className="text-sm font-black text-slate-500 uppercase tracking-widest">No activity yet</p>
                                 <p className="text-[12px] text-slate-600 font-bold max-w-md">Check-ins from your cameras and browser webcam will show here with time and location.</p>
                               </div>
                             ) : logs.map(l => (
                                <div key={l.id} className="p-6 px-8 flex items-center justify-between hover:bg-white/[0.015] transition-all group text-left">
                                   <div className="flex items-center gap-6"><div className="w-16 h-16 rounded-[22px] overflow-hidden border-2 border-white/5"><img src={l.image_path?.startsWith('http') ? l.image_path : `${API_BASE}/${l.image_path}`} className="w-full h-full object-cover" alt="" /></div><div><div className="text-xl font-black text-white tracking-tighter leading-none">{l.name}</div><div className="flex items-center gap-2 mt-2"><div className="text-[8px] font-black uppercase px-3 py-1 rounded bg-blue-500/10 text-blue-400">{l.role}</div><div className={`text-[8px] font-black uppercase px-3 py-1 rounded ${l.subscription_status === 'active' ? 'bg-emerald-500/10 text-emerald-500' : 'bg-red-500/10 text-red-500'}`}>{l.subscription_status}</div></div></div></div>
                                   <div className="flex items-center gap-6 text-right"><div><div className="text-2xl font-black text-blue-500 tabular-nums">{new Date(l.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</div><div className="text-[8px] font-black text-slate-700 uppercase mt-1">{l.location}</div></div></div>
                                </div>
                             ))}
                          </div>
                        )}
                    </div>
                </div>
             </div>
          </div>
        </main>
      </div>

      {editingUser && (
        <div className="fixed inset-0 bg-[#020617]/95 backdrop-blur-3xl z-[200] flex items-center justify-center p-6">
          <div className="glass-panel w-full max-w-2xl p-10 border-4 border-white/10 rounded-[48px] shadow-2xl bg-[#020617] animate-in zoom-in-95">
             <div className="flex items-center gap-6 mb-8 text-left"><div className="w-20 h-20 rounded-[28px] overflow-hidden border-4 border-white/10 shadow-2xl"><img src={editingUser.image_path?.startsWith('http') ? editingUser.image_path : `${API_BASE}/${editingUser.image_path}`} className="w-full h-full object-cover" alt="" /></div><div><h2 className="text-3xl font-black heading-font text-white uppercase leading-none">Modify Identity</h2><p className="text-[10px] text-slate-500 font-bold uppercase mt-2">Biometric Registry Sync</p></div></div>
             <div className="space-y-6">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                   <div className="space-y-2 text-left"><label className="text-[9px] font-black text-slate-500 uppercase ml-4">Full Name</label><input value={newName} onChange={e => setNewName(e.target.value)} className="w-full bg-white/5 border-2 border-white/5 rounded-2xl py-4 px-6 text-white font-black outline-none" /></div>
                   <div className="space-y-2 text-left"><label className="text-[9px] font-black text-slate-500 uppercase ml-4">Role</label><select value={newRole} onChange={e => setNewRole(e.target.value)} className="w-full bg-[#020617] border-2 border-white/5 rounded-2xl py-4 px-6 text-white font-black outline-none appearance-none"><option value="member">MEMBER</option><option value="vip">VIP</option><option value="trainer">TRAINER</option></select></div>
                </div>
                <div className="space-y-2 text-left"><label className="text-[9px] font-black text-slate-500 uppercase ml-4">Subscription Expiry</label><input type="date" value={newExpiry} onChange={e => setNewExpiry(e.target.value)} className="w-full bg-white/5 border-2 border-white/5 rounded-2xl py-4 px-6 text-white font-black outline-none [color-scheme:dark]" /></div>
                <div className="flex gap-4 pt-4"><button onClick={handleUpdateProfile} className="py-5 px-10 bg-blue-600 text-white font-black rounded-2xl flex-1 shadow-xl hover:bg-blue-500 active:scale-95 transition-all">SAVE CHANGES</button><button onClick={() => setEditingUser(null)} className="py-5 px-10 bg-white/5 text-slate-500 font-black rounded-2xl flex-1 border-2 border-white/5 hover:bg-white/10 transition-all">CANCEL</button></div>
             </div>
          </div>
        </div>
      )}

      {isRegisterOpen && (
        <div className="fixed inset-0 bg-[#020617]/98 backdrop-blur-3xl z-[100] flex items-center justify-center p-6">
          <div className="glass-panel w-full max-w-5xl flex flex-col md:flex-row border-white/10 rounded-[64px] shadow-2xl relative border-2 overflow-hidden">
             <button onClick={closeWebcam} className="absolute top-8 right-8 z-[110] w-12 h-12 rounded-2xl flex items-center justify-center bg-white/5 text-white hover:bg-red-600 transition-all"><X size={24} /></button>
             <div className="flex-1 p-12 flex flex-col gap-10 bg-white/[0.015] text-left">
                <div><h2 className="text-4xl font-black heading-font text-white tracking-widest uppercase">ENROLLMENT</h2><p className="text-slate-600 text-lg mt-2 font-medium">Neural identity master path sync active.</p></div>
                <div className="space-y-6">
                   <div className="space-y-2"><label className="text-[9px] font-black text-slate-600 uppercase ml-3">Subject Name</label><input value={regName} onChange={e => setRegName(e.target.value)} placeholder="Marcus Vane" className="w-full bg-[#020617] border-4 border-white/5 rounded-[32px] py-5 px-8 text-xl text-white font-black outline-none" /></div>
                   <div className="flex gap-2 p-1 bg-[#020617] border-2 border-white/5 rounded-2xl"><button onClick={() => { closeWebcam(); openWebcam('local'); }} className={`flex-1 py-3 rounded-xl text-[9px] font-black uppercase transition-all ${regSource === 'local' ? 'bg-blue-600 text-white' : 'text-slate-500'}`}>Webcam</button><button onClick={() => { closeWebcam(); openWebcam('remote'); }} className={`flex-1 py-3 rounded-xl text-[9px] font-black uppercase transition-all ${regSource === 'remote' ? 'bg-blue-600 text-white' : 'text-slate-500'}`}>Phone</button><button onClick={() => { setRegSource('file'); fileInputRef.current?.click(); }} className={`flex-1 py-3 rounded-xl text-[9px] font-black uppercase transition-all ${regSource === 'file' ? 'bg-blue-600 text-white' : 'text-slate-500'}`}>File</button></div>
                   <input type="file" ref={fileInputRef} className="hidden" accept="image/*" onChange={(e) => { const file = e.target.files[0]; if (file) { const reader = new FileReader(); reader.onloadend = () => { setUploadedImage(reader.result); setRegSource('file'); }; reader.readAsDataURL(file); } }} />
                </div>
                <button onClick={captureAndRegister} disabled={!regName} className={`w-full py-6 rounded-[32px] font-black heading-font text-xl flex items-center justify-center gap-4 transition-all ${!regName ? 'bg-slate-900 text-slate-800 opacity-50' : 'bg-white text-black shadow-2xl active:scale-95'}`}><ScannerIcon size={28} /> INITIALIZE SCAN</button>
             </div>
             <div className="lg:w-[400px] bg-black flex items-center justify-center p-8">
                <div className="w-full aspect-[3/4] rounded-[48px] overflow-hidden relative border-4 border-white/10 shadow-2xl">
                   {regSource === 'local' ? ( <video ref={videoRef} autoPlay playsInline className="w-full h-full object-cover scale-x-[-1] grayscale-[0.2]" /> ) : regSource === 'remote' ? ( <img id="sentinel-enroll-stream" src={`${API_BASE}/api/stream/Gym_Camera?t=${Date.now()}`} className="w-full h-full object-cover" alt="Remote" crossOrigin="anonymous" onError={(e) => { e.target.src = "https://via.placeholder.com/640?text=Camera+Offline"; }} /> ) : ( <img src={uploadedImage || "https://via.placeholder.com/640?text=Select+File"} className="w-full h-full object-cover" alt="Preview" /> )}
                   <div className="scanner-overlay !z-10 bg-blue-900/10"><div className="scanner-line !h-[6px] !bg-blue-400"></div><div className="face-target !border-blue-500/30 !w-[220px] !h-[300px] !border-[3px] !rounded-[60px]"></div></div>
                </div>
             </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default App;
