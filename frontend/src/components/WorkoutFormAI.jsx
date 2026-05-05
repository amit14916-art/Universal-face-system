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
  const [exercise, setExercise] = useState('Squats');
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
    let currentFeedback = 'Good form';
    let currentAcc = 100;

    if (exercise === 'Squats') {
      const hip = landmarks[24];
      const knee = landmarks[26];
      const ankle = landmarks[28];
      const shoulder = landmarks[12];
      const kneeAngle = calculateAngle(hip, knee, ankle);
      const backAngle = calculateAngle(shoulder, hip, { x: hip.x, y: 0 });

      if (kneeAngle > 160) {
        if (stage === 'down') { setCounter(c => c + 1); setStage('up'); }
        currentFeedback = 'Go down';
      } else if (kneeAngle < 90) {
        setStage('down');
        currentFeedback = 'Excellent depth';
      } else {
        currentFeedback = 'Keep going down';
      }
      if (backAngle > 30) { currentFeedback = 'Straighten your back!'; currentAcc -= 30; }

    } else if (exercise === 'Pushups') {
      const shoulder = landmarks[12];
      const elbow = landmarks[14];
      const wrist = landmarks[16];
      const hip = landmarks[24];
      const ankle = landmarks[28];

      const elbowAngle = calculateAngle(shoulder, elbow, wrist);
      const bodyAlignment = calculateAngle(shoulder, hip, ankle); // Should be close to 180

      if (elbowAngle > 160) {
        if (stage === 'down') { setCounter(c => c + 1); setStage('up'); }
        currentFeedback = 'Lower your chest';
      } else if (elbowAngle < 90) {
        setStage('down');
        currentFeedback = 'Good depth';
      }

      if (bodyAlignment < 160) { currentFeedback = 'Keep your core tight!'; currentAcc -= 40; }

    } else if (exercise === 'Lunges') {
      const hip = landmarks[24];
      const knee = landmarks[26];
      const ankle = landmarks[28];
      const kneeAngle = calculateAngle(hip, knee, ankle);

      if (kneeAngle > 160) {
        if (stage === 'down') { setCounter(c => c + 1); setStage('up'); }
        currentFeedback = 'Step forward & down';
      } else if (kneeAngle < 100) {
        setStage('down');
        currentFeedback = 'Great depth';
      }
    }

    setFeedback(currentFeedback);
    setAccuracy(currentAcc);
    setAllAccuracies(prev => [...prev.slice(-10), currentAcc]);
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
  }, [isActive, exercise]);

  const toggleWorkout = () => {
    if (isActive) {
      const avg = allAccuracies.length > 0 ? Math.floor(allAccuracies.reduce((a,b) => a+b)/allAccuracies.length) : 0;
      onSessionEnd({
        reps: counter,
        accuracy: avg,
        exercise: exercise
      });
      setCounter(0);
    }
    setIsActive(!isActive);
  };

  return (
    <div className="flex flex-col gap-6 p-6 bg-[#0f172a] rounded-3xl border border-white/10 backdrop-blur-xl">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="p-3 bg-blue-500/20 rounded-2xl">
            <Activity className="text-blue-500" />
          </div>
          <div>
            <h3 className="text-xl font-bold text-white">AI Personal Trainer</h3>
            <p className="text-slate-400 text-sm">Select exercise and begin</p>
          </div>
        </div>

        <div className="flex items-center gap-3 bg-white/5 p-1.5 rounded-2xl border border-white/10">
          {['Squats', 'Pushups', 'Lunges'].map(ex => (
            <button
              key={ex}
              disabled={isActive}
              onClick={() => setExercise(ex)}
              className={`px-4 py-2 rounded-xl text-xs font-black uppercase transition-all ${
                exercise === ex ? 'bg-blue-600 text-white shadow-lg' : 'text-slate-500 hover:text-white'
              } disabled:opacity-50`}
            >
              {ex}
            </button>
          ))}
        </div>

        <button 
          onClick={toggleWorkout}
          className={`flex items-center gap-2 px-8 py-3 rounded-2xl font-bold transition-all ${
            isActive ? 'bg-red-500/20 text-red-500 border border-red-500/50' : 'bg-blue-500 text-white shadow-xl shadow-blue-500/20'
          }`}
        >
          {isActive ? <><Square size={18} /> Stop Session</> : <><Play size={18} /> Start {exercise}</>}
        </button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Camera View */}
        <div className="lg:col-span-2 relative aspect-video bg-black rounded-2xl overflow-hidden border border-white/5 shadow-2xl">
          {!isActive && (
            <div className="absolute inset-0 flex items-center justify-center bg-slate-900/50 backdrop-blur-sm z-10">
              <div className="text-center">
                <div className="w-16 h-16 bg-blue-600/20 rounded-full flex items-center justify-center mx-auto mb-4 animate-pulse">
                  <Camera className="text-blue-500" size={32} />
                </div>
                <p className="text-slate-300 font-bold uppercase tracking-widest text-xs">Ready to start {exercise}?</p>
              </div>
            </div>
          )}
          <video ref={videoRef} className="absolute inset-0 w-full h-full object-cover" playsInline muted />
          <canvas ref={canvasRef} className="absolute inset-0 w-full h-full z-10" width="640" height="480" />
          
          {/* HUD Overlay */}
          {isActive && (
            <div className="absolute top-4 left-4 z-20 flex flex-col gap-2">
              <div className="px-5 py-3 bg-black/70 backdrop-blur-xl rounded-2xl border border-white/10 flex items-center gap-4 shadow-2xl">
                <div className={`w-3 h-3 rounded-full animate-pulse ${accuracy > 80 ? 'bg-green-500 shadow-[0_0_10px_#22c55e]' : 'bg-yellow-500 shadow-[0_0_10px_#eab308]'}`} />
                <span className="text-white font-black text-xl tracking-tight uppercase">{feedback}</span>
              </div>
            </div>
          )}
        </div>

        {/* Stats Panel */}
        <div className="flex flex-col gap-4">
          <div className="p-6 bg-white/[0.02] rounded-3xl border border-white/10 shadow-xl">
            <span className="text-slate-500 text-[10px] font-black uppercase tracking-[0.2em]">Rep Count</span>
            <div className="text-7xl font-black text-white mt-2 tabular-nums">{counter}</div>
          </div>
          
          <div className="p-6 bg-white/[0.02] rounded-3xl border border-white/10 shadow-xl">
            <span className="text-slate-500 text-[10px] font-black uppercase tracking-[0.2em]">Form Accuracy</span>
            <div className={`text-4xl font-black mt-2 ${accuracy > 80 ? 'text-emerald-500' : 'text-amber-500'}`}>
              {accuracy}%
            </div>
            <div className="w-full bg-white/5 h-3 rounded-full mt-4 overflow-hidden border border-white/5">
              <div 
                className={`h-full transition-all duration-500 ${accuracy > 80 ? 'bg-emerald-500' : 'bg-amber-500'}`} 
                style={{ width: `${accuracy}%` }} 
              />
            </div>
          </div>

          <div className="p-6 bg-blue-600/5 rounded-3xl border border-blue-500/20">
            <h4 className="text-blue-400 font-black text-xs uppercase tracking-widest mb-4 flex items-center gap-2">
              <Info size={14} /> Trainer Tips
            </h4>
            <ul className="text-xs text-slate-400 flex flex-col gap-3 font-bold">
              {exercise === 'Squats' && (
                <>
                  <li className="flex items-start gap-3"><CheckCircle2 size={14} className="text-emerald-500 shrink-0" /> Chest up, shoulders back</li>
                  <li className="flex items-start gap-3"><CheckCircle2 size={14} className="text-emerald-500 shrink-0" /> Hips below knee level</li>
                </>
              )}
              {exercise === 'Pushups' && (
                <>
                  <li className="flex items-start gap-3"><CheckCircle2 size={14} className="text-emerald-500 shrink-0" /> Body in a straight line</li>
                  <li className="flex items-start gap-3"><CheckCircle2 size={14} className="text-emerald-500 shrink-0" /> Chest almost touches floor</li>
                </>
              )}
              {exercise === 'Lunges' && (
                <>
                  <li className="flex items-start gap-3"><CheckCircle2 size={14} className="text-emerald-500 shrink-0" /> 90 deg bend in both knees</li>
                  <li className="flex items-start gap-3"><CheckCircle2 size={14} className="text-emerald-500 shrink-0" /> Keep upper body vertical</li>
                </>
              )}
            </ul>
          </div>
        </div>
      </div>
    </div>
  );
};

export default WorkoutFormAI;
