import { useState, useEffect, useRef } from 'react';
import { Shield, LayoutList, User, ShieldOff, Trash2, X } from 'lucide-react';
import './index.css';

function App() {
  const [logs, setLogs] = useState([]);
  const [users, setUsers] = useState([]);
  const [isRegisterOpen, setIsRegisterOpen] = useState(false);
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
      // Assuming FastAPI runs on 8000
      const baseUrl = 'http://localhost:8000';
      const [lRes, uRes] = await Promise.all([
        fetch(`${baseUrl}/api/logs`),
        fetch(`${baseUrl}/api/users`)
      ]);
      const logsData = await lRes.json();
      const usersData = await uRes.json();
      setLogs(logsData);
      setUsers(usersData);
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

  const deleteUser = async (id) => {
    if (confirm("Delete record?")) {
      await fetch(`http://localhost:8000/api/users/${id}`, { method: 'DELETE' });
      fetchData();
    }
  };

  const openWebcam = async () => {
    setIsRegisterOpen(true);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ video: true });
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
      }
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

  const todaysTraffic = logs.filter(l => {
    const d = new Date().toISOString().split('T')[0];
    return l.timestamp.includes(d);
  }).length;

  return (
    <div style={{ padding: '2rem 5%' }}>
      <div style={{ maxWidth: '1280px', margin: '0 auto' }}>
        
        {/* Header */}
        <header style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '2.5rem', flexWrap: 'wrap', gap: '1rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '1.5rem' }}>
            <div style={{ width: '56px', height: '56px', background: 'var(--accent-gradient)', borderRadius: '16px', display: 'flex', alignItems: 'center', justifyContent: 'center', boxShadow: '0 8px 24px rgba(59, 130, 246, 0.3)' }}>
              <Shield color="white" size={32} />
            </div>
            <div>
              <h1 className="heading-font" style={{ fontSize: '2.2rem', fontWeight: 700, margin: 0 }}>
                System Sentinel <span style={{ color: 'var(--accent-color)' }}>v3.0</span>
              </h1>
              <p style={{ color: 'var(--text-muted)', fontSize: '0.9rem', fontWeight: 500, margin: 0 }}>Biometric Intelligence & Security Monitoring</p>
            </div>
          </div>
          <button className="btn-primary" onClick={openWebcam}>
            Enroll Identity
          </button>
        </header>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: '1.5rem' }}>
          
          {/* Left Column */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem', gridColumn: 'span 2' }}>
            
            {/* Stats Row */}
            <div className="glass-panel" style={{ padding: '1.5rem', display: 'grid', gridTemplateColumns: '1fr 1fr 2fr', gap: '1rem' }}>
              <div className="stat-box">
                <div className="stat-label">Profiles</div>
                <div className="stat-value">{users.length}</div>
              </div>
              <div className="stat-box">
                <div className="stat-label">Today's Traffic</div>
                <div className="stat-value">{todaysTraffic}</div>
              </div>
              <div className="stat-box active">
                <div className="stat-label" style={{ color: 'var(--accent-color)' }}>System Status</div>
                <div className="stat-value active animate-pulse-soft">OPERATIONAL</div>
              </div>
            </div>

            {/* Access Stream */}
            <div className="glass-panel" style={{ display: 'flex', flexDirection: 'column', overflow: 'hidden', flexGrow: 1 }}>
              <div style={{ padding: '1.2rem 1.5rem', borderBottom: '1px solid var(--card-border)', background: 'rgba(30, 41, 59, 0.3)', display: 'flex', alignItems: 'center', gap: '8px' }}>
                <LayoutList size={20} color="var(--success)" />
                <h3 style={{ fontWeight: 600, margin: 0 }}>Access Stream</h3>
              </div>
              <div style={{ overflowX: 'auto' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                  <thead>
                    <tr>
                      <th style={{ padding: '1rem 1.5rem', textAlign: 'left', fontSize: '0.75rem', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em', borderBottom: '1px solid var(--card-border)' }}>Identification</th>
                      <th style={{ padding: '1rem 1.5rem', textAlign: 'right', fontSize: '0.75rem', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em', borderBottom: '1px solid var(--card-border)' }}>Activity</th>
                    </tr>
                  </thead>
                  <tbody>
                    {logs.length === 0 ? (
                      <tr><td colSpan="2" style={{ padding: '3rem', textAlign: 'center', color: 'var(--text-muted)', fontStyle: 'italic' }}>No access records detected</td></tr>
                    ) : (
                      logs.map((l, i) => {
                        const dateObj = new Date(l.timestamp);
                        return (
                          <tr key={l.id} className="table-row-animate" style={{ borderBottom: '1px solid rgba(255,255,255,0.02)', animationDelay: `${i * 0.05}s` }}>
                            <td style={{ padding: '1rem 1.5rem', display: 'flex', alignItems: 'center', gap: '1rem' }}>
                              <div style={{ width: '48px', height: '48px', borderRadius: '12px', background: 'rgba(30,41,59,0.8)', overflow: 'hidden', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                                {l.image_path ? <img src={`http://localhost:8000/${l.image_path}`} alt="" style={{ width: '100%', height: '100%', objectFit: 'cover' }} /> : <b style={{fontSize: '0.8rem'}}>{l.name[0]}</b>}
                              </div>
                              <div>
                                <div style={{ fontWeight: 'bold' }}>{l.name}</div>
                                <div style={{ fontSize: '0.65rem', textTransform: 'uppercase', color: 'var(--text-muted)', fontWeight: 600, letterSpacing: '0.05em' }}>{l.role}</div>
                              </div>
                            </td>
                            <td style={{ padding: '1rem 1.5rem', textAlign: 'right' }}>
                              <div style={{ fontWeight: 'bold' }}>{dateObj.toLocaleTimeString()}</div>
                              <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>{dateObj.toLocaleDateString()}</div>
                            </td>
                          </tr>
                        );
                      })
                    )}
                  </tbody>
                </table>
              </div>
            </div>

          </div>

          {/* Right Column - Registry Gallery */}
          <div className="glass-panel" style={{ display: 'flex', flexDirection: 'column', height: '600px' }}>
            <div style={{ padding: '1.2rem 1.5rem', display: 'flex', alignItems: 'center', gap: '8px' }}>
              <Shield size={20} color="var(--accent-color)" />
              <h3 style={{ fontWeight: 600, margin: 0 }}>Registry Gallery</h3>
            </div>
            
            <div style={{ padding: '0 1.5rem 1.5rem 1.5rem', overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '12px' }}>
              {users.length === 0 ? (
                <div style={{ padding: '2rem 0', textAlign: 'center', color: 'var(--text-muted)', fontSize: '0.9rem' }}>Synchronizing profiles...</div>
              ) : (
                users.map(u => (
                  <div key={u.id} style={{
                    padding: '12px', borderRadius: '16px', background: u.is_blacklisted ? 'rgba(239, 68, 68, 0.1)' : 'rgba(30, 41, 59, 0.4)',
                    border: u.is_blacklisted ? '1px solid rgba(239, 68, 68, 0.3)' : '1px solid transparent',
                    display: 'flex', alignItems: 'center', justifyContent: 'space-between'
                  }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                      <div style={{ width: '40px', height: '40px', borderRadius: '10px', background: 'rgba(15,23,42,0.8)', overflow: 'hidden', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                         {u.image_path ? <img src={`http://localhost:8000/${u.image_path}`} alt="" style={{ width: '100%', height: '100%', objectFit: 'cover' }} /> : <User size={16} color="var(--text-muted)" />}
                      </div>
                      <div>
                        <div style={{ fontSize: '0.9rem', fontWeight: 'bold' }}>{u.name}</div>
                        <div style={{ fontSize: '0.6rem', textTransform: 'uppercase', color: 'var(--text-muted)', fontWeight: 700, letterSpacing: '0.05em' }}>{u.role}</div>
                      </div>
                    </div>
                    <div style={{ display: 'flex', gap: '4px' }}>
                      <button className="btn-icon" onClick={() => toggleBlacklist(u.id, !u.is_blacklisted)} title="Toggle Blacklist">
                        <ShieldOff size={16} />
                      </button>
                      <button className="btn-icon" onClick={() => deleteUser(u.id)} title="Delete User">
                        <Trash2 size={16} />
                      </button>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>

        </div>
      </div>

      {/* modal overlay */}
      {isRegisterOpen && (
        <div style={{
          position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
          background: 'rgba(0,0,0,0.8)', backdropFilter: 'blur(8px)',
          display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 100
        }}>
          <div className="glass-panel" style={{ width: '100%', maxWidth: '500px', padding: '2rem', position: 'relative' }}>
            <button className="btn-icon" onClick={closeWebcam} style={{ position: 'absolute', top: '16px', right: '16px' }}>
              <X size={24} />
            </button>
            <h2 className="heading-font" style={{ marginBottom: '1.5rem' }}>Enroll New Identity</h2>
            
            <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
              <input 
                type="text" 
                placeholder="Full Name" 
                value={regName}
                onChange={e => setRegName(e.target.value)}
                style={{ width: '100%', background: 'rgba(15,23,42,0.8)', border: '1px solid var(--card-border)', color: 'white', padding: '12px 16px', borderRadius: '12px', outline: 'none' }} 
              />
              <select 
                value={regRole}
                onChange={e => setRegRole(e.target.value)}
                style={{ width: '100%', background: 'rgba(15,23,42,0.8)', border: '1px solid var(--card-border)', color: 'white', padding: '12px 16px', borderRadius: '12px', outline: 'none', appearance: 'none' }}
              >
                <option value="member">Member</option>
                <option value="staff">Staff</option>
                <option value="vip">VIP</option>
              </select>
              
              <div style={{ width: '100%', aspectRatio: '16/9', background: '#000', borderRadius: '12px', overflow: 'hidden' }}>
                <video ref={videoRef} autoPlay playsInline style={{ width: '100%', height: '100%', objectFit: 'cover' }}></video>
              </div>
              
              <button className="btn-primary" onClick={captureAndRegister} style={{ width: '100%', padding: '16px' }}>
                Start Enrollment
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default App;
