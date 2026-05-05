import React, { useEffect, useRef, useState, useCallback } from 'react';
import { AlertCircle, CheckCircle2, Play, Square, Activity, Info, Camera as LucideCamera, Wifi, WifiOff } from 'lucide-react';

/* Global MediaPipe objects from index.html scripts */
const Pose = window.Pose;
const POSE_CONNECTIONS = window.POSE_CONNECTIONS;
const drawConnectors = window.drawConnectors;
const drawLandmarks = window.drawLandmarks;
const Camera = window.Camera;

// ─── Landmark Index Reference ──────────────────────────────────────────────
// 11=L_shoulder, 12=R_shoulder, 13=L_elbow, 14=R_elbow, 15=L_wrist, 16=R_wrist
// 23=L_hip,      24=R_hip,      25=L_knee,  26=R_knee,  27=L_ankle, 28=R_ankle
// ───────────────────────────────────────────────────────────────────────────

// Helper to pick the more visible side of the body
const getBetterSide = (landmarks, leftIdx, rightIdx) => {
  const leftVis  = landmarks[leftIdx]?.visibility  ?? 0;
  const rightVis = landmarks[rightIdx]?.visibility ?? 0;
  return leftVis >= rightVis ? 'left' : 'right';
};

// Calculate angle – unchanged but visibility-gated before calling
const calculateAngle = (a, b, c) => {
  const radians = Math.atan2(c.y - b.y, c.x - b.x) -
                  Math.atan2(a.y - b.y, a.x - b.x);
  let angle = Math.abs((radians * 180.0) / Math.PI);
  if (angle > 180.0) angle = 360 - angle;
  return angle;
};

// Visibility guard — returns null if any landmark is too uncertain
const safeAngle = (a, b, c, threshold = 0.5) => {
  if ((a?.visibility ?? 0) < threshold ||
      (b?.visibility ?? 0) < threshold ||
      (c?.visibility ?? 0) < threshold) return null;
  return calculateAngle(a, b, c);
};

// True vertical reference using a point directly above the hip
// Instead of {x: hip.x, y: 0} which points to top of frame (fragile),
// we use the midpoint of both shoulders for a proper spine vector.
const calculateBackAngle = (shoulder, hip) => {
  if ((shoulder?.visibility ?? 0) < 0.5 || (hip?.visibility ?? 0) < 0.5) return null;
  // Angle of the spine vector from vertical (down = 90° in image coords)
  const dx = shoulder.x - hip.x;
  const dy = shoulder.y - hip.y; // positive = shoulder is ABOVE hip
  const angle = Math.abs(Math.atan2(dx, -dy) * 180 / Math.PI); // 0° = perfectly upright
  return angle;
};

const WorkoutFormAI = ({ onSessionEnd }) => {
  const videoRef    = useRef(null);
  const canvasRef   = useRef(null);

  // Store stage in a ref so onResults always reads the CURRENT value
  // (avoids stale-closure bug where setStage updates React state but the
  // MediaPipe callback still sees the old captured value)
  const stageRef    = useRef('up');
  const exerciseRef = useRef('Squats');

  // Initialization Check (must be before any hook calls)
  if (!Pose || !Camera) {
    return (
      <div className="flex flex-col items-center justify-center p-20 bg-slate-900/50 rounded-[40px] border border-white/5 text-center">
        <AlertCircle size={48} className="text-red-500 mb-4" />
        <h3 className="text-xl font-bold text-white mb-2">AI Modules Loading…</h3>
        <p className="text-slate-400 max-w-md">The AI tracking engine is initialising. Please wait or refresh if this persists.</p>
      </div>
    );
  }

  const [isActive,      setIsActive]      = useState(false);
  const [exercise,      setExercise]      = useState('Squats');
  const [feedback,      setFeedback]      = useState('Stand in view to begin');
  const [counter,       setCounter]       = useState(0);
  const [stage,         setStage]         = useState('up');      // display only
  const [accuracy,      setAccuracy]      = useState(100);
  const [allAccuracies, setAllAccuracies] = useState([]);
  const [poseVisible,   setPoseVisible]   = useState(false);     // detection status

  // Keep exerciseRef in sync with state so onResults always has the fresh value
  useEffect(() => { exerciseRef.current = exercise; }, [exercise]);

  // ─── Core Results Handler ──────────────────────────────────────────────────
  // useCallback with empty deps so MediaPipe always calls the same fn reference;
  // internal state is accessed via refs, not closures.
  const onResults = useCallback((results) => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    ctx.save();
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    if (!results.poseLandmarks || results.poseLandmarks.length === 0) {
      ctx.restore();
      setPoseVisible(false);
      setFeedback('No person detected — adjust camera angle');
      return;
    }

    setPoseVisible(true);
    const lm = results.poseLandmarks;

    // Draw skeleton
    drawConnectors(ctx, lm, POSE_CONNECTIONS, { color: '#3b82f6', lineWidth: 2 });
    drawLandmarks(ctx, lm, { color: '#ffffff', lineWidth: 1, radius: 3 });

    const ex = exerciseRef.current;
    let currentFeedback = 'Good form ✓';
    let deductions = 0;    // penalty points (0-100)
    let detected = false;  // did we get valid landmarks for this exercise?

    // ── SQUATS ────────────────────────────────────────────────────────────
    if (ex === 'Squats') {
      const side = getBetterSide(lm, 23, 24); // L/R hip
      const hipIdx  = side === 'left' ? 23 : 24;
      const kneeIdx = side === 'left' ? 25 : 26;
      const ankleIdx= side === 'left' ? 27 : 28;
      const shoulderIdx = side === 'left' ? 11 : 12;

      const kneeAngle = safeAngle(lm[hipIdx], lm[kneeIdx], lm[ankleIdx]);
      const backAngle = calculateBackAngle(lm[shoulderIdx], lm[hipIdx]);

      if (kneeAngle !== null) {
        detected = true;
        if (kneeAngle > 160) {
          if (stageRef.current === 'down') {
            setCounter(c => c + 1);
            stageRef.current = 'up';
            setStage('up');
          }
          currentFeedback = 'Lower into squat';
        } else if (kneeAngle < 90) {
          stageRef.current = 'down';
          setStage('down');
          currentFeedback = 'Excellent depth! ✓';
        } else {
          currentFeedback = 'Keep going lower…';
        }
      }
      // Back form check
      if (backAngle !== null && backAngle > 25) {
        currentFeedback = '⚠ Straighten your back!';
        deductions += 30;
      }
    }

    // ── PUSH-UPS ──────────────────────────────────────────────────────────
    else if (ex === 'Pushups') {
      // Pick better-visible shoulder side
      const side      = getBetterSide(lm, 11, 12);
      const shIdx     = side === 'left' ? 11 : 12;
      const elIdx     = side === 'left' ? 13 : 14;
      const wrIdx     = side === 'left' ? 15 : 16;
      const hipIdx    = side === 'left' ? 23 : 24;
      const ankleIdx  = side === 'left' ? 27 : 28;

      const elbowAngle    = safeAngle(lm[shIdx], lm[elIdx], lm[wrIdx]);
      const bodyAlignment = safeAngle(lm[shIdx], lm[hipIdx], lm[ankleIdx]);

      if (elbowAngle !== null) {
        detected = true;
        if (elbowAngle > 160) {
          if (stageRef.current === 'down') {
            setCounter(c => c + 1);
            stageRef.current = 'up';
            setStage('up');
          }
          currentFeedback = 'Lower your chest';
        } else if (elbowAngle < 90) {
          stageRef.current = 'down';
          setStage('down');
          currentFeedback = 'Good depth ✓';
        }
      }
      if (bodyAlignment !== null && bodyAlignment < 160) {
        currentFeedback = '⚠ Tighten your core!';
        deductions += 40;
      }
    }

    // ── LUNGES ────────────────────────────────────────────────────────────
    else if (ex === 'Lunges') {
      // check BOTH knees independently for lunges
      const leftKneeAngle  = safeAngle(lm[23], lm[25], lm[27]);  // L hip-knee-ankle
      const rightKneeAngle = safeAngle(lm[24], lm[26], lm[28]);  // R hip-knee-ankle
      const frontAngle     = leftKneeAngle ?? rightKneeAngle;     // best available

      if (frontAngle !== null) {
        detected = true;
        if (frontAngle > 160) {
          if (stageRef.current === 'down') {
            setCounter(c => c + 1);
            stageRef.current = 'up';
            setStage('up');
          }
          currentFeedback = 'Step forward & lower';
        } else if (frontAngle < 100) {
          stageRef.current = 'down';
          setStage('down');
          currentFeedback = 'Great depth ✓';
        }
        // Check back knee doesn't drop below 90°
        const backAngle = leftKneeAngle !== null && rightKneeAngle !== null
          ? Math.min(leftKneeAngle, rightKneeAngle)
          : null;
        if (backAngle !== null && backAngle < 80) {
          currentFeedback = '⚠ Don\'t let back knee touch floor';
          deductions += 20;
        }
      }
    }

    // ── DEADLIFT ──────────────────────────────────────────────────────────
    else if (ex === 'Deadlift') {
      const side    = getBetterSide(lm, 11, 12);
      const shIdx   = side === 'left' ? 11 : 12;
      const hipIdx  = side === 'left' ? 23 : 24;
      const kneeIdx = side === 'left' ? 25 : 26;
      const ankleIdx= side === 'left' ? 27 : 28;

      const hipAngle  = safeAngle(lm[shIdx], lm[hipIdx], lm[kneeIdx]);
      const kneeAngle = safeAngle(lm[hipIdx], lm[kneeIdx], lm[ankleIdx]);
      const backAngle = calculateBackAngle(lm[shIdx], lm[hipIdx]); // proper spine angle

      if (hipAngle !== null && kneeAngle !== null) {
        detected = true;
        if (hipAngle > 160 && kneeAngle > 160) {
          if (stageRef.current === 'down') {
            setCounter(c => c + 1);
            stageRef.current = 'up';
            setStage('up');
          }
          currentFeedback = 'Stand tall ✓';
        } else if (hipAngle < 100) {
          stageRef.current = 'down';
          setStage('down');
          currentFeedback = 'Drive hips back';
        }
      }
      if (backAngle !== null && backAngle > 20 && stageRef.current === 'down') {
        currentFeedback = '⚠ Keep your back FLAT!';
        deductions += 35;
      }
    }

    // ── BICEP CURLS ───────────────────────────────────────────────────────
    else if (ex === 'Bicep Curls') {
      // Initial stage should be 'down' (arm extended), not 'up'.
      // Rep is counted when arm comes BACK DOWN after curling.
      const side    = getBetterSide(lm, 11, 12);
      const shIdx   = side === 'left' ? 11 : 12;
      const elIdx   = side === 'left' ? 13 : 14;
      const wrIdx   = side === 'left' ? 15 : 16;
      // Check elbow doesn't flare out (elbow stays close to torso)
      const hipIdx  = side === 'left' ? 23 : 24;

      const elbowAngle = safeAngle(lm[shIdx], lm[elIdx], lm[wrIdx]);

      if (elbowAngle !== null) {
        detected = true;
        if (elbowAngle > 150) {
          // Arm fully extended (bottom of curl)
          if (stageRef.current === 'up') {
            // Rep complete: was curled, now extended again
            setCounter(c => c + 1);
          }
          stageRef.current = 'down';
          setStage('down');
          currentFeedback = 'Curl up!';
        } else if (elbowAngle < 45) {
          // Arm fully curled (top)
          stageRef.current = 'up';
          setStage('up');
          currentFeedback = 'Squeeze & lower slowly ✓';
        } else {
          currentFeedback = 'Keep curling…';
        }
        // Elbow flare check: shoulder shouldn't move much
        if (lm[shIdx] && lm[hipIdx]) {
          const shoulderMovement = Math.abs(lm[shIdx].x - lm[hipIdx].x);
          if (shoulderMovement > 0.15) {
            deductions += 15;
            currentFeedback = '⚠ Keep elbow fixed!';
          }
        }
      }
    }

    if (!detected) {
      currentFeedback = 'Adjust position — landmark not visible';
    }

    const currentAcc = Math.max(0, 100 - deductions);
    setFeedback(currentFeedback);
    setAccuracy(currentAcc);
    setAllAccuracies(prev => [...prev.slice(-29), currentAcc]);
    ctx.restore();
  }, []); // no deps — reads live data via refs

  // ─── MediaPipe Setup ───────────────────────────────────────────────────────
  useEffect(() => {
    const pose = new Pose({
      locateFile: (file) => `https://cdn.jsdelivr.net/npm/@mediapipe/pose/${file}`,
    });

    pose.setOptions({
      modelComplexity: 2,            // use 2 for CCTV/angled cameras
      smoothLandmarks: true,
      enableSegmentation: false,
      minDetectionConfidence: 0.55,
      minTrackingConfidence: 0.55,
    });

    pose.onResults(onResults);

    let camera = null;
    if (isActive && videoRef.current) {
      camera = new Camera(videoRef.current, {
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
  }, [isActive, exercise, onResults]);

  // ─── Reset stage ref when exercise changes ─────────────────────────────────
  const handleExerciseChange = (ex) => {
    stageRef.current = ex === 'Bicep Curls' ? 'down' : 'up'; // correct init per exercise
    setStage(stageRef.current);
    setExercise(ex);
    setCounter(0);
    setAccuracy(100);
    setAllAccuracies([]);
    setFeedback('Stand in view to begin');
  };

  const toggleWorkout = () => {
    if (isActive) {
      const avg = allAccuracies.length > 0
        ? Math.floor(allAccuracies.reduce((a, b) => a + b) / allAccuracies.length)
        : 0;
      onSessionEnd({ reps: counter, accuracy: avg, exercise });
      setCounter(0);
      setAllAccuracies([]);
      stageRef.current = exercise === 'Bicep Curls' ? 'down' : 'up';
      setStage(stageRef.current);
    }
    setIsActive(prev => !prev);
  };

  const avgAccuracy = allAccuracies.length > 0
    ? Math.floor(allAccuracies.reduce((a, b) => a + b) / allAccuracies.length)
    : 100;

  return (
    <div className="flex flex-col gap-6 p-6 bg-[#0f172a] rounded-3xl border border-white/10 backdrop-blur-xl">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="p-3 bg-blue-500/20 rounded-2xl">
            <Activity className="text-blue-500" />
          </div>
          <div>
            <h3 className="text-xl font-bold text-white">AI Personal Trainer</h3>
            <p className="text-slate-400 text-sm">
              {poseVisible
                ? <span className="text-emerald-400">● Tracking active</span>
                : <span className="text-slate-500">○ Waiting for person in frame</span>}
            </p>
          </div>
        </div>

        {/* Exercise Selector */}
        <div className="flex items-center gap-3 bg-white/5 p-1.5 rounded-2xl border border-white/10 flex-wrap">
          {['Squats', 'Pushups', 'Lunges', 'Deadlift', 'Bicep Curls'].map(ex => (
            <button
              key={ex}
              disabled={isActive}
              onClick={() => handleExerciseChange(ex)}
              className={`px-4 py-2 rounded-xl text-xs font-black uppercase transition-all ${
                exercise === ex
                  ? 'bg-blue-600 text-white shadow-lg'
                  : 'text-slate-500 hover:text-white'
              } disabled:opacity-50`}
            >
              {ex}
            </button>
          ))}
        </div>

        <button
          onClick={toggleWorkout}
          className={`flex items-center gap-2 px-8 py-3 rounded-2xl font-bold transition-all ${
            isActive
              ? 'bg-red-500/20 text-red-500 border border-red-500/50'
              : 'bg-blue-500 text-white shadow-xl shadow-blue-500/20'
          }`}
        >
          {isActive ? <><Square size={18} /> Stop Session</> : <><Play size={18} /> Start {exercise}</>}
        </button>
      </div>

      {/* Main Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Camera */}
        <div className="lg:col-span-2 relative aspect-video bg-black rounded-2xl overflow-hidden border border-white/5 shadow-2xl">
          {!isActive && (
            <div className="absolute inset-0 flex items-center justify-center bg-slate-900/50 backdrop-blur-sm z-10">
              <div className="text-center">
                <div className="w-16 h-16 bg-blue-600/20 rounded-full flex items-center justify-center mx-auto mb-4 animate-pulse">
                  <LucideCamera className="text-blue-500" size={32} />
                </div>
                <p className="text-slate-300 font-bold uppercase tracking-widest text-xs">Ready to start {exercise}?</p>
              </div>
            </div>
          )}
          <video ref={videoRef} className="absolute inset-0 w-full h-full object-cover" playsInline muted />
          <canvas ref={canvasRef} className="absolute inset-0 w-full h-full z-10" width="640" height="480" />

          {/* HUD */}
          {isActive && (
            <div className="absolute top-4 left-4 z-20 flex flex-col gap-2">
              <div className="px-5 py-3 bg-black/70 backdrop-blur-xl rounded-2xl border border-white/10 flex items-center gap-4 shadow-2xl">
                <div className={`w-3 h-3 rounded-full animate-pulse ${
                  feedback.startsWith('⚠') ? 'bg-red-500 shadow-[0_0_10px_#ef4444]'
                  : accuracy > 80 ? 'bg-green-500 shadow-[0_0_10px_#22c55e]'
                  : 'bg-yellow-500 shadow-[0_0_10px_#eab308]'
                }`} />
                <span className="text-white font-black text-lg tracking-tight">{feedback}</span>
              </div>
              {/* Stage indicator */}
              <div className="px-4 py-2 bg-black/60 rounded-xl border border-white/5 text-xs text-slate-400 font-bold uppercase tracking-widest">
                Stage: <span className={stage === 'up' ? 'text-blue-400' : 'text-orange-400'}>{stage}</span>
              </div>
            </div>
          )}
        </div>

        {/* Stats */}
        <div className="flex flex-col gap-4">
          <div className="p-6 bg-white/[0.02] rounded-3xl border border-white/10 shadow-xl">
            <span className="text-slate-500 text-[10px] font-black uppercase tracking-[0.2em]">Rep Count</span>
            <div className="text-7xl font-black text-white mt-2 tabular-nums">{counter}</div>
          </div>

          <div className="p-6 bg-white/[0.02] rounded-3xl border border-white/10 shadow-xl">
            <span className="text-slate-500 text-[10px] font-black uppercase tracking-[0.2em]">Session Avg Accuracy</span>
            <div className={`text-4xl font-black mt-2 ${avgAccuracy > 80 ? 'text-emerald-500' : 'text-amber-500'}`}>
              {avgAccuracy}%
            </div>
            <div className="w-full bg-white/5 h-3 rounded-full mt-4 overflow-hidden border border-white/5">
              <div
                className={`h-full transition-all duration-500 ${avgAccuracy > 80 ? 'bg-emerald-500' : 'bg-amber-500'}`}
                style={{ width: `${avgAccuracy}%` }}
              />
            </div>
            <p className="text-slate-600 text-[10px] mt-2">Based on last {allAccuracies.length} frames</p>
          </div>

          {/* Trainer Tips */}
          <div className="p-6 bg-blue-600/5 rounded-3xl border border-blue-500/20">
            <h4 className="text-blue-400 font-black text-xs uppercase tracking-widest mb-4 flex items-center gap-2">
              <Info size={14} /> Trainer Tips
            </h4>
            <ul className="text-xs text-slate-400 flex flex-col gap-3 font-bold">
              {exercise === 'Squats' && (<>
                <li className="flex items-start gap-3"><CheckCircle2 size={14} className="text-emerald-500 shrink-0" /> Chest up, shoulders back</li>
                <li className="flex items-start gap-3"><CheckCircle2 size={14} className="text-emerald-500 shrink-0" /> Hips below knee level</li>
                <li className="flex items-start gap-3"><CheckCircle2 size={14} className="text-emerald-500 shrink-0" /> Face camera directly or from side</li>
              </>)}
              {exercise === 'Pushups' && (<>
                <li className="flex items-start gap-3"><CheckCircle2 size={14} className="text-emerald-500 shrink-0" /> Body in a straight line</li>
                <li className="flex items-start gap-3"><CheckCircle2 size={14} className="text-emerald-500 shrink-0" /> Chest almost touches floor</li>
                <li className="flex items-start gap-3"><CheckCircle2 size={14} className="text-emerald-500 shrink-0" /> Camera should be at ground level side-on</li>
              </>)}
              {exercise === 'Lunges' && (<>
                <li className="flex items-start gap-3"><CheckCircle2 size={14} className="text-emerald-500 shrink-0" /> 90° bend in both knees</li>
                <li className="flex items-start gap-3"><CheckCircle2 size={14} className="text-emerald-500 shrink-0" /> Keep upper body vertical</li>
                <li className="flex items-start gap-3"><CheckCircle2 size={14} className="text-emerald-500 shrink-0" /> Back knee should not touch floor</li>
              </>)}
              {exercise === 'Deadlift' && (<>
                <li className="flex items-start gap-3"><CheckCircle2 size={14} className="text-emerald-500 shrink-0" /> Keep back flat, not rounded</li>
                <li className="flex items-start gap-3"><CheckCircle2 size={14} className="text-emerald-500 shrink-0" /> Drive through your heels</li>
                <li className="flex items-start gap-3"><CheckCircle2 size={14} className="text-emerald-500 shrink-0" /> Side-angle camera works best</li>
              </>)}
              {exercise === 'Bicep Curls' && (<>
                <li className="flex items-start gap-3"><CheckCircle2 size={14} className="text-emerald-500 shrink-0" /> Keep elbows tucked to sides</li>
                <li className="flex items-start gap-3"><CheckCircle2 size={14} className="text-emerald-500 shrink-0" /> Full extension at bottom</li>
                <li className="flex items-start gap-3"><CheckCircle2 size={14} className="text-emerald-500 shrink-0" /> Rep counts on the way DOWN</li>
              </>)}
            </ul>
          </div>
        </div>
      </div>
    </div>
  );
};

export default WorkoutFormAI;
