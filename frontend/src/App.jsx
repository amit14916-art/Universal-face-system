import { useState, useEffect, useRef } from 'react';
import { Shield, LayoutList, User, ShieldOff, Trash2, X, Activity, Users, Clock, Edit2 } from 'lucide-react';
import './index.css';

function App() {
  const [logs, setLogs] = useState([]);
  const [users, setUsers] = useState([]);
  const [stats, setStats] = useState({ hourly: [], unique_captured: 0 });
  const [isRegisterOpen, setIsRegisterOpen] = useState(false);
  const [editingUser, setEditingUser] = useState(null);
  const [newName, setNewName] = useState('');
  const videoRef = useRef(null);
  const [regName, setRegName] = useState('');
  const [regRole, setRegRole] = useState('member');

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 3000);
    return () => clearInterval(interval);
  }, []);

  const fetchData = async () => {
    try {
      const baseUrl = 'http://localhost:8000';
      const [lRes, uRes, sRes] = await Promise.all([
        fetch(`${baseUrl}/api/logs`),
        fetch(`${baseUrl}/api/users`),
        fetch(`${baseUrl}/api/stats/hourly`)
      ]);
      setLogs(await lRes.json());
      setUsers(await uRes.json());
      setStats(await sRes.json());
    } catch (error) {
      console.error("Dashboard Sync Fail:", error);
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
    await fetch(`http://localhost:8000/api/users/${editingUser.id}/rename`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name: newName })
    });
    setEditingUser(null);
    fetchData();
  };

  const deleteUser = async (id) => {
    if (confirm("Delete this biometric profile permanently?")) {
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
      console.error("Webcam error:", e);
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
    fetchData();
  };

  return (
    <div style={{ padding: '2.5rem 5%', maxWidth: '1600px', margin: '0 auto' }}>
      
      {/* Header Section */}
      <header style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '3rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '1.2rem' }}>
          <div className="pulse-ring" style={{ width: '64px', height: '64px', background: 'var(--accent-gradient)', borderRadius: '20px', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <Shield color="white" size={34} />
          </div>
          <div>
            <h1 className="heading-font" style={{ fontSize: '2.8rem', fontWeight: 800, margin: 0, letterSpacing: '-0.02em' }}>
              UNIVERSAL <span style={{ color: 'var(--accent-color)' }}>FACE SYSTEM</span>
            </h1>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--success)', fontWeight: 700, fontSize: '0.85rem' }}>
              <Activity size={14} /> CLOUD NODE ACTIVE (SUPABASE)
            </div>
          </div>
        </div>
        <button className="btn-primary" onClick={openWebcam}>
          <Users size={20} /> ENROLL NEW IDENTITY
        </button>
      </header>

      {/* Main Grid */}
      <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: '2rem' }}>
        
        {/* Left: Stats & Feed */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '2rem' }}>
          
          {/* Stats Bar */}
          <div className="glass-panel" style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)' }}>
            <div className="stat-card">
              <div style={{ color: 'var(--text-muted)', fontSize: '0.75rem', fontWeight: 700, textTransform: 'uppercase' }}>Cloud Database</div>
              <div className="stat-num">{stats.unique_captured || users.length}</div>
              <div style={{ fontSize: '0.7rem', color: 'var(--success)' }}>Profiles Synced</div>
            </div>
            <div className="stat-card">
              <div style={{ color: 'var(--text-muted)', fontSize: '0.75rem', fontWeight: 700, textTransform: 'uppercase' }}>24H Activity</div>
              <div className="stat-num">{logs.length}</div>
              <div style={{ fontSize: '0.7rem', color: 'var(--accent-color)' }}>Detections Logged</div>
            </div>
            <div className="stat-card">
              <div style={{ color: 'var(--text-muted)', fontSize: '0.75rem', fontWeight: 700, textTransform: 'uppercase' }}>Security Level</div>
              <div className="stat-num" style={{ background: 'var(--success)', WebkitTextFillColor: 'var(--success)' }}>HIGH</div>
              <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>Real-time Monitoring</div>
            </div>
          </div>

          {/* Activity Stream */}
          <div className="glass-panel" style={{ flexGrow: 1 }}>
            <div style={{ padding: '1.5rem', borderBottom: '1px solid var(--card-border)', background: 'rgba(255,255,255,0.02)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                <Clock size={20} color="var(--accent-color)" />
                <h3 className="heading-font" style={{ fontWeight: 700, margin: 0 }}>REAL-TIME DETECTION FEED</h3>
              </div>
              <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', fontWeight: 600 }}>LIVE SYNC ENABLED</div>
            </div>
            <div style={{ maxHeight: '600px', overflowY: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                <tbody style={{ verticalAlign: 'middle' }}>
                  {logs.map((l, i) => (
                    <tr key={l.id} className="table-row-animate" style={{ borderBottom: '1px solid rgba(255,255,255,0.03)', background: i % 2 === 0 ? 'rgba(255,255,255,0.01)' : 'transparent' }}>
                      <td style={{ padding: '1.2rem 1.5rem', display: 'flex', alignItems: 'center', gap: '1.2rem' }}>
                        <div className="img-container">
                          <img src={`http://localhost:8000/${l.image_path}`} alt="" />
                          <div className="status-dot"></div>
                        </div>
                        <div>
                          <div style={{ fontWeight: 800, fontSize: '1rem', letterSpacing: '-0.01em' }}>{l.name}</div>
                          <div className="badge">{l.role}</div>
                        </div>
                      </td>
                      <td style={{ padding: '1.2rem 1.5rem', textAlign: 'right' }}>
                        <div style={{ fontWeight: 800, color: 'var(--accent-color)', fontSize: '1.1rem' }}>{new Date(l.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}</div>
                        <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', fontWeight: 600 }}>{new Date(l.timestamp).toDateString()}</div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>

        {/* Right: Registry */}
        <div className="glass-panel" style={{ height: 'fit-content', maxHeight: '850px', display: 'flex', flexDirection: 'column' }}>
          <div style={{ padding: '1.5rem', borderBottom: '1px solid var(--card-border)', background: 'rgba(255,255,255,0.02)' }}>
            <h3 className="heading-font" style={{ fontWeight: 700, margin: 0 }}>PROFILE REGISTRY</h3>
          </div>
          <div style={{ padding: '1.5rem', overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '1rem' }}>
            {users.map(u => (
              <div key={u.id} style={{ padding: '1rem', borderRadius: '20px', background: u.is_blacklisted ? 'rgba(239, 68, 68, 0.05)' : 'rgba(255,255,255,0.03)', border: '1px solid var(--card-border)', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
                  <div style={{ width: '44px', height: '44px', borderRadius: '12px', background: '#0f172a', overflow: 'hidden' }}>
                    {u.image_path ? <img src={`http://localhost:8000/${u.image_path}`} style={{ width: '100%', height: '100%', objectFit: 'cover' }} /> : <User size={20} style={{ margin: '12px' }} />}
                  </div>
                  <div>
                    <div style={{ fontWeight: 700, fontSize: '0.95rem' }}>{u.name}</div>
                    <div className="badge" style={{ fontSize: '0.6rem' }}>{u.role}</div>
                  </div>
                </div>
                <div style={{ display: 'flex', gap: '6px' }}>
                  <button className="btn-icon" onClick={() => {setEditingUser(u); setNewName(u.name);}}><Edit2 size={16} /></button>
                  <button className="btn-icon" onClick={() => toggleBlacklist(u.id, !u.is_blacklisted)} style={{ color: u.is_blacklisted ? 'var(--danger)' : 'inherit' }}><ShieldOff size={16} /></button>
                  <button className="btn-icon" onClick={() => deleteUser(u.id)}><Trash2 size={16} /></button>
                </div>
              </div>
            ))}
          </div>
        </div>

      </div>

      {/* Rename Modal */}
      {editingUser && (
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.85)', backdropFilter: 'blur(10px)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000 }}>
          <div className="glass-panel" style={{ width: '400px', padding: '2rem' }}>
             <h2 className="heading-font">Update Profile</h2>
             <input value={newName} onChange={e => setNewName(e.target.value)} style={{ width: '100%', background: '#0f172a', border: '1px solid var(--card-border)', color: 'white', padding: '12px', borderRadius: '12px', marginTop: '1rem' }} />
             <div style={{ display: 'flex', gap: '10px', marginTop: '1.5rem' }}>
                <button className="btn-primary" style={{ flex: 1 }} onClick={handleRename}>Save</button>
                <button className="btn-icon" onClick={() => setEditingUser(null)}>Cancel</button>
             </div>
          </div>
        </div>
      )}

      {/* Enrollment Modal */}
      {isRegisterOpen && (
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.85)', backdropFilter: 'blur(10px)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000 }}>
          <div className="glass-panel" style={{ width: '100%', maxWidth: '550px', padding: '2.5rem', position: 'relative' }}>
             <button onClick={closeWebcam} style={{ position: 'absolute', top: '20px', right: '20px', background: 'none', border: 'none', color: 'white', cursor: 'pointer' }}><X size={32} /></button>
             <h2 className="heading-font" style={{ fontSize: '2rem' }}>Identity Enrollment</h2>
             <div style={{ display: 'flex', flexDirection: 'column', gap: '1.2rem', marginTop: '1.5rem' }}>
                <input value={regName} onChange={e => setRegName(e.target.value)} placeholder="Full Name" style={{ width: '100%', background: '#0f172a', border: '1px solid var(--card-border)', color: 'white', padding: '14px', borderRadius: '14px' }} />
                <select value={regRole} onChange={e => setRegRole(e.target.value)} style={{ width: '100%', background: '#0f172a', border: '1px solid var(--card-border)', color: 'white', padding: '14px', borderRadius: '14px' }}>
                  <option value="member">Member</option>
                  <option value="staff">Staff</option>
                  <option value="vip">VIP</option>
                </select>
                <div style={{ width: '100%', aspectRatio: '16/9', background: 'black', borderRadius: '14px', overflow: 'hidden' }}>
                    <video ref={videoRef} autoPlay playsInline style={{ width: '100%', height: '100%', objectFit: 'cover' }}></video>
                </div>
                <button className="btn-primary" style={{ width: '100%', justifyContent: 'center' }} onClick={captureAndRegister}>COMPLETE ENROLLMENT</button>
             </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default App;
