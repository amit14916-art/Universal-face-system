import React, { useEffect, useRef, useState } from 'react';
import { Pose } from '@mediapipe/pose';
import * as cam from '@mediapipe/camera_utils';
import { drawConnectors, drawLandmarks } from '@mediapipe/drawing_utils';
import { POSE_CONNECTIONS } from '@mediapipe/pose';
import { AlertCircle, CheckCircle2, Play, Square, Activity } from 'lucide-react';

const WorkoutFormAI = ({ onSessionEnd }) => {
  const videoRef = useRef(null);
  const canvasRef = useRef(null);
  const [isActive, setIsActive] = useState(false);
  const [feedback, setFeedback] = useState('Stand in view to begin');
  const [counter, setCounter] = useState(0);
  const [stage, setStage] = useState('up');
  const [accuracy, setAccuracy] = useState(0);
  const [allAccuracies, setAllAccuracies] = useState([]);

  // Calculate angle between three points
  const calculateAngle = (a, b, c) => {
    const radians = Math.atan2(c.y - b.y, c.x - b.x) - Math.atan2(a.y - b.y, a.x - b.x);
    let angle = Math.abs((radians * 180.0) / Math.PI);
    if (angle > 180.0) angle = 360 - angle;
    return angle;
  };

  const onResults = (results) => {
    if (!results.poseLandmarks) return;

    const canvasCtx = canvasRef.current.getContext('2d');
    canvasCtx.save();
    canvasCtx.clearRect(0, 0, canvasRef.current.width, canvasRef.current.height);
    
    // Draw landmarks
    drawConnectors(canvasCtx, results.poseLandmarks, POSE_CONNECTIONS, { color: '#3b82f6', lineWidth: 2 });
    drawLandmarks(canvasCtx, results.poseLandmarks, { color: '#ffffff', lineWidth: 1, radius: 3 });

    const landmarks = results.poseLandmarks;
    
    // Squat Logic (Right Side)
    const hip = landmarks[24];
    const knee = landmarks[26];
    const ankle = landmarks[28];
    const shoulder = landmarks[12];

    const kneeAngle = calculateAngle(hip, knee, ankle);
    const backAngle = calculateAngle(shoulder, hip, { x: hip.x, y: 0 }); // Angle with vertical

    // Feedback logic
    let currentFeedback = 'Good form';
    let currentAcc = 100;

    if (kneeAngle > 160) {
      if (stage === 'down') {
        setCounter(c => c + 1);
        setStage('up');
      }
      currentFeedback = 'Go down';
    } else if (kneeAngle < 90) {
      setStage('down');
      currentFeedback = 'Excellent depth';
    } else {
      currentFeedback = 'Keep going down';
    }

    // Back posture check
    if (backAngle > 30) {
      currentFeedback = 'Keep your back straighter!';
      currentAcc -= 30;
    }

    setFeedback(currentFeedback);
    setAccuracy(currentAcc);
    setAllAccuracies(prev => [...prev.slice(-10), currentAcc]); // Keep last 10 for avg

    canvasCtx.restore();
  };

  useEffect(() => {
    const pose = new Pose({
      locateFile: (file) => `https://cdn.jsdelivr.net/npm/@mediapipe/pose/${file}`,
    });

    pose.setOptions({
      modelComplexity: 1,
      smoothLandmarks: true,
      minDetectionConfidence: 0.5,
      minTrackingConfidence: 0.5,
    });

    pose.onResults(onResults);

    let camera = null;
    if (isActive && videoRef.current) {
      camera = new cam.Camera(videoRef.current, {
        onFrame: async () => {
          await pose.send({ image: videoRef.current });
        },
        width: 640,
        height: 480,
      });
      camera.start();
    }

    return () => {
      if (camera) camera.stop();
      pose.close();
    };
  }, [isActive]);

  const toggleWorkout = () => {
    if (isActive) {
      const avg = allAccuracies.length > 0 ? Math.floor(allAccuracies.reduce((a,b) => a+b)/allAccuracies.length) : 0;
      onSessionEnd({
        reps: counter,
        accuracy: avg,
        exercise: 'Squats'
      });
    }
    setIsActive(!isActive);
  };

  return (
    <div className="flex flex-col gap-6 p-6 bg-[#0f172a] rounded-3xl border border-white/10 backdrop-blur-xl">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="p-3 bg-blue-500/20 rounded-2xl">
            <Activity className="text-blue-500" />
          </div>
          <div>
            <h3 className="text-xl font-bold text-white">AI Form Analyzer</h3>
            <p className="text-slate-400 text-sm">Real-time posture & rep tracking</p>
          </div>
        </div>
        <button 
          onClick={toggleWorkout}
          className={`flex items-center gap-2 px-6 py-3 rounded-2xl font-bold transition-all ${
            isActive ? 'bg-red-500/20 text-red-500 border border-red-500/50' : 'bg-blue-500 text-white shadow-lg shadow-blue-500/20'
          }`}
        >
          {isActive ? <><Square size={18} /> Stop Session</> : <><Play size={18} /> Start Squats</>}
        </button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Camera View */}
        <div className="lg:col-span-2 relative aspect-video bg-black rounded-2xl overflow-hidden border border-white/5">
          {!isActive && (
            <div className="absolute inset-0 flex items-center justify-center bg-slate-900/50 backdrop-blur-sm z-10">
              <p className="text-slate-400 font-medium">Click Start to initialize AI camera</p>
            </div>
          )}
          <video ref={videoRef} className="absolute inset-0 w-full h-full object-cover" playsInline muted />
          <canvas ref={canvasRef} className="absolute inset-0 w-full h-full z-10" width="640" height="480" />
          
          {/* HUD Overlay */}
          {isActive && (
            <div className="absolute top-4 left-4 z-20 flex flex-col gap-2">
              <div className="px-4 py-2 bg-black/60 backdrop-blur-md rounded-xl border border-white/10 flex items-center gap-3">
                <div className={`w-3 h-3 rounded-full animate-pulse ${accuracy > 80 ? 'bg-green-500' : 'bg-yellow-500'}`} />
                <span className="text-white font-bold text-lg">{feedback}</span>
              </div>
            </div>
          )}
        </div>

        {/* Stats Panel */}
        <div className="flex flex-col gap-4">
          <div className="p-6 bg-white/5 rounded-2xl border border-white/10">
            <span className="text-slate-400 text-xs font-black uppercase tracking-widest">Rep Counter</span>
            <div className="text-6xl font-black text-white mt-2">{counter}</div>
          </div>
          
          <div className="p-6 bg-white/5 rounded-2xl border border-white/10">
            <span className="text-slate-400 text-xs font-black uppercase tracking-widest">Form Accuracy</span>
            <div className={`text-4xl font-black mt-2 ${accuracy > 80 ? 'text-green-500' : 'text-yellow-500'}`}>
              {accuracy}%
            </div>
            <div className="w-full bg-white/10 h-2 rounded-full mt-4 overflow-hidden">
              <div 
                className="h-full bg-blue-500 transition-all duration-300" 
                style={{ width: `${accuracy}%` }} 
              />
            </div>
          </div>

          <div className="p-6 bg-blue-500/10 rounded-2xl border border-blue-500/20">
            <h4 className="text-blue-400 font-bold mb-2 flex items-center gap-2">
              <Info size={16} /> AI Tips
            </h4>
            <ul className="text-sm text-slate-300 flex flex-col gap-2">
              <li className="flex items-start gap-2">
                <CheckCircle2 size={14} className="text-green-500 mt-1 shrink-0" />
                Keep your weight on your heels
              </li>
              <li className="flex items-start gap-2">
                <AlertCircle size={14} className="text-blue-400 mt-1 shrink-0" />
                Hips should go below knee level for a full rep
              </li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  );
};

export default WorkoutFormAI;
