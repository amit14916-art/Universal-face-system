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
  const exerciseRef = useRef('Detecting...');
  const isActiveRef = useRef(true); 
  
  // rPPG State Refs
  const rppgBufferRef = useRef([]);
  const rppgTimesRef  = useRef([]);
  const lastBpmUpdateRef = useRef(0);
  
  // Exercise Detection Smoothing
  const exHistoryRef = useRef([]);

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

  const [isActive,      setIsActive]      = useState(true);
  const [exercise,      setExercise]      = useState('Detecting...');
  const [feedback,      setFeedback]      = useState('Stand in view to begin');
  const [counter,       setCounter]       = useState(0);
  const [stage,         setStage]         = useState('up');      // display only
  const [accuracy,      setAccuracy]      = useState(100);
  const [allAccuracies, setAllAccuracies] = useState([]);
  const [poseVisible,   setPoseVisible]   = useState(false);     // detection status
  const [biometrics,    setBiometrics]    = useState({ height: 0, weight: 0, body_fat: 0, heart_rate: 0 });

  // Keep refs in sync with state
  useEffect(() => { exerciseRef.current = exercise; }, [exercise]);
  useEffect(() => { isActiveRef.current = isActive; }, [isActive]);

  // ─── Core Results Handler ──────────────────────────────────────────────────
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
    // Only process exercise logic if the session is ACTIVE
    if (!isActiveRef.current) {
        // Just draw the skeleton for positioning, then exit
        drawConnectors(ctx, results.poseLandmarks, POSE_CONNECTIONS, { color: '#ffffff44', lineWidth: 1 });
        ctx.restore();
        return;
    }
    const lm = results.poseLandmarks;

    // ── AUTO DETECTION ENGINE ─────────────────────────────────────────────
    const side = getBetterSide(lm, 23, 24);
    const kneeAngle = safeAngle(lm[side === 'left' ? 23 : 24], lm[side === 'left' ? 25 : 26], lm[side === 'left' ? 27 : 28]);
    const elbowAngle = safeAngle(lm[side === 'left' ? 11 : 12], lm[side === 'left' ? 13 : 14], lm[side === 'left' ? 15 : 16]);
    const hipAngle = safeAngle(lm[side === 'left' ? 11 : 12], lm[side === 'left' ? 23 : 24], lm[side === 'left' ? 25 : 26]);
    const shoulderAngle = safeAngle(lm[side === 'left' ? 13 : 14], lm[side === 'left' ? 11 : 12], lm[side === 'left' ? 23 : 24]);
    
    const handsAboveHead = lm[15].y < lm[0].y && lm[16].y < lm[0].y;
    const handsAboveShoulders = lm[15].y < lm[11].y && lm[16].y < lm[12].y;
    const isLying = Math.abs(lm[11].y - lm[23].y) < 0.15;
    const feetApart = Math.abs(lm[27].x - lm[28].x) > 0.4;

    let detectedExercise = 'Standing';
    if (isLying) {
        if (hipAngle !== null && hipAngle < 100) detectedExercise = 'Sit-ups';
        else if (elbowAngle !== null && elbowAngle < 100) detectedExercise = 'Bench Press';
        else if (elbowAngle !== null && elbowAngle > 160 && hipAngle > 160) detectedExercise = 'Plank';
        else detectedExercise = 'Pushups';
    } else if (handsAboveHead) {
        if (feetApart && shoulderAngle > 120) detectedExercise = 'Jumping Jacks';
        else if (elbowAngle < 100) detectedExercise = 'Tricep Extensions';
        else detectedExercise = 'Shoulder Press';
    } else if (kneeAngle !== null && kneeAngle < 115) {
        const kneeDiff = Math.abs(lm[25].y - lm[26].y);
        detectedExercise = kneeDiff < 0.1 ? 'Squats' : 'Lunges';
    } else if (shoulderAngle !== null && shoulderAngle > 70) {
        const handsForward = lm[15].z < lm[11].z - 0.1;
        detectedExercise = handsForward ? 'Front Raises' : 'Lateral Raises';
    } else if (elbowAngle !== null && elbowAngle < 110) {
        detectedExercise = 'Bicep Curls';
    } else if (hipAngle !== null && hipAngle < 130) {
        detectedExercise = 'Deadlift';
    } else if (Math.abs(lm[11].y - lm[12].y) < 0.05 && shoulderAngle < 20) {
        // Detecting subtle shoulder elevation for shrugs is hard, but we'll try
        detectedExercise = 'Shrugs';
    }

    // Majority Vote for stability
    exHistoryRef.current.push(detectedExercise);
    if (exHistoryRef.current.length > 25) exHistoryRef.current.shift();
    const counts = exHistoryRef.current.reduce((acc, val) => { acc[val] = (acc[val] || 0) + 1; return acc; }, {});
    const mostFrequent = Object.keys(counts).reduce((a, b) => counts[a] > counts[b] ? a : b);

    if (mostFrequent !== 'Standing' && mostFrequent !== exerciseRef.current) {
        setExercise(mostFrequent);
        exerciseRef.current = mostFrequent;
        setCounter(0); 
        const startUp = ['Squats', 'Lunges', 'Pushups', 'Deadlift', 'Shoulder Press', 'Bench Press', 'Lateral Raises', 'Jumping Jacks', 'Front Raises', 'Shoulder Press', 'Tricep Extensions'];
        stageRef.current = startUp.includes(mostFrequent) ? 'up' : 'down';
        setStage(stageRef.current);
    } else if (mostFrequent === 'Standing' && exerciseRef.current === 'Detecting...') {
        setExercise('Standing');
        exerciseRef.current = 'Standing';
    }

    // Draw skeleton
    drawConnectors(ctx, lm, POSE_CONNECTIONS, { color: '#3b82f6', lineWidth: 2 });
    drawLandmarks(ctx, lm, { color: '#ffffff', lineWidth: 1, radius: 3 });

    const ex = exerciseRef.current;
    let currentFeedback = 'Good form ✓';
    let deductions = 0;
    let detected = false;

    if (ex === 'Squats') {
      const kneeAngle = safeAngle(lm[side === 'left' ? 23 : 24], lm[side === 'left' ? 25 : 26], lm[side === 'left' ? 27 : 28]);
      if (kneeAngle !== null) {
        detected = true;
        if (kneeAngle > 160) { if (stageRef.current === 'down') { setCounter(c => c + 1); stageRef.current = 'up'; setStage('up'); } currentFeedback = 'Lower into squat'; }
        else if (kneeAngle < 90) { stageRef.current = 'down'; setStage('down'); currentFeedback = 'Excellent depth! ✓'; }
      }
    }
    else if (ex === 'Pushups') {
      const elbowAngle = safeAngle(lm[side === 'left' ? 11 : 12], lm[side === 'left' ? 13 : 14], lm[side === 'left' ? 15 : 16]);
      if (elbowAngle !== null) {
        detected = true;
        if (elbowAngle > 160) { if (stageRef.current === 'down') { setCounter(c => c + 1); stageRef.current = 'up'; setStage('up'); } currentFeedback = 'Lower your chest'; }
        else if (elbowAngle < 90) { stageRef.current = 'down'; setStage('down'); currentFeedback = 'Good depth ✓'; }
      }
    }
    else if (ex === 'Jumping Jacks') {
        detected = true;
        if (shoulderAngle > 150 && feetApart) {
            if (stageRef.current === 'down') { setCounter(c => c + 1); stageRef.current = 'up'; setStage('up'); }
            currentFeedback = 'Arms up! ✓';
        } else if (shoulderAngle < 40 && !feetApart) {
            stageRef.current = 'down'; setStage('down');
            currentFeedback = 'Jump out!';
        }
    }
    else if (ex === 'Tricep Extensions') {
        detected = true;
        if (elbowAngle > 160) {
            if (stageRef.current === 'down') { setCounter(c => c + 1); stageRef.current = 'up'; setStage('up'); }
            currentFeedback = 'Full extension ✓';
        } else if (elbowAngle < 60) {
            stageRef.current = 'down'; setStage('down');
            currentFeedback = 'Lower behind head';
        }
    }
    else if (ex === 'Front Raises') {
        detected = true;
        if (shoulderAngle > 80) {
            if (stageRef.current === 'down') { setCounter(c => c + 1); stageRef.current = 'up'; setStage('up'); }
            currentFeedback = 'Shoulder height ✓';
        } else if (shoulderAngle < 20) {
            stageRef.current = 'down'; setStage('down');
            currentFeedback = 'Raise in front';
        }
    }
    else if (ex === 'Plank') {
        detected = true;
        currentFeedback = 'Hold position... core tight!';
        // For static exercises, we could use a timer, but we'll stick to rep detection as 'time held'
        if (isActiveRef.current) {
            // Count every 30 frames as 1 "unit" (approx 1 sec)
            if (window.plankCounter === undefined) window.plankCounter = 0;
            window.plankCounter++;
            if (window.plankCounter % 30 === 0) setCounter(c => c + 1);
        }
    }
    else if (ex === 'Shoulder Press') {
        if (elbowAngle !== null) {
            detected = true;
            if (elbowAngle > 160) { if (stageRef.current === 'down') { setCounter(c => c + 1); stageRef.current = 'up'; setStage('up'); } currentFeedback = 'Press to top! ✓'; }
            else if (elbowAngle < 70) { stageRef.current = 'down'; setStage('down'); currentFeedback = 'Lower to shoulders'; }
        }
    }
    else if (ex === 'Bench Press') {
        if (elbowAngle !== null) {
            detected = true;
            if (elbowAngle > 160) { if (stageRef.current === 'down') { setCounter(c => c + 1); stageRef.current = 'up'; setStage('up'); } currentFeedback = 'Push up! ✓'; }
            else if (elbowAngle < 80) { stageRef.current = 'down'; setStage('down'); currentFeedback = 'Lower to chest'; }
        }
    }
    else if (ex === 'Sit-ups') {
        if (hipAngle !== null) {
            detected = true;
            if (hipAngle < 80) { if (stageRef.current === 'down') { setCounter(c => c + 1); stageRef.current = 'up'; setStage('up'); } currentFeedback = 'Sit up! ✓'; }
            else if (hipAngle > 140) { stageRef.current = 'down'; setStage('down'); currentFeedback = 'Lower slowly'; }
        }
    }
    else if (ex === 'Lateral Raises') {
        if (shoulderAngle !== null) {
            detected = true;
            if (shoulderAngle > 85) { if (stageRef.current === 'down') { setCounter(c => c + 1); stageRef.current = 'up'; setStage('up'); } currentFeedback = 'Parallel to floor ✓'; }
            else if (shoulderAngle < 25) { stageRef.current = 'down'; setStage('down'); currentFeedback = 'Raise arms out'; }
        }
    }
    else if (ex === 'Lunges') {
      const leftKneeAngle = safeAngle(lm[23], lm[25], lm[27]);
      const rightKneeAngle = safeAngle(lm[24], lm[26], lm[28]);
      const frontAngle = leftKneeAngle ?? rightKneeAngle;
      if (frontAngle !== null) {
        detected = true;
        if (frontAngle > 160) { if (stageRef.current === 'down') { setCounter(c => c + 1); stageRef.current = 'up'; setStage('up'); } currentFeedback = 'Step & lower'; }
        else if (frontAngle < 100) { stageRef.current = 'down'; setStage('down'); currentFeedback = 'Good depth ✓'; }
      }
    }
    else if (ex === 'Deadlift') {
      if (hipAngle !== null) {
        detected = true;
        if (hipAngle > 165) { if (stageRef.current === 'down') { setCounter(c => c + 1); stageRef.current = 'up'; setStage('up'); } currentFeedback = 'Stand tall ✓'; }
        else if (hipAngle < 110) { stageRef.current = 'down'; setStage('down'); currentFeedback = 'Hips back'; }
      }
    }
    else if (ex === 'Bicep Curls') {
      if (elbowAngle !== null) {
        detected = true;
        if (elbowAngle > 150) { if (stageRef.current === 'up') { setCounter(c => c + 1); } stageRef.current = 'down'; setStage('down'); currentFeedback = 'Curl up!'; }
        else if (elbowAngle < 45) { stageRef.current = 'up'; setStage('up'); currentFeedback = 'Squeeze at top ✓'; }
      }
    }
    else if (ex === 'Shrugs') {
        detected = true;
        // Check for shoulder Y movement relative to nose
        const shY = (lm[11].y + lm[12].y) / 2;
        const relY = nose.y - shY;
        if (relY > 0.22) { // Shoulders high
            if (stageRef.current === 'down') { setCounter(c => c + 1); stageRef.current = 'up'; setStage('up'); }
            currentFeedback = 'Squeeze traps! ✓';
        } else if (relY < 0.18) { // Shoulders low
            stageRef.current = 'down'; setStage('down');
            currentFeedback = 'Lower shoulders';
        }
    }

    if (!detected) {
      currentFeedback = 'Adjust position — landmark not visible';
    }

    const currentAcc = Math.max(0, 100 - deductions);
    setFeedback(currentFeedback);
    setAccuracy(currentAcc);
    setAllAccuracies(prev => [...prev.slice(-29), currentAcc]);

    // ── BIOMETRICS ENGINE (Frontend Heuristics) ───────────────────────────
    const h = canvas.height;
    const w = canvas.width;
    
    // 1. rPPG Heart Rate
    let currentBpm = biometrics.heart_rate || 72;
    const nose = lm[0];
    if (nose && nose.visibility > 0.5) {
        const nx = nose.x * w;
        const ny = nose.y * h;
        const roiSize = 20;
        
        // Extract ROI and get average green
        try {
            const imageData = ctx.getImageData(nx - roiSize, ny - roiSize, roiSize * 2, roiSize * 2);
            const data = imageData.data;
            let greenSum = 0;
            for (let i = 1; i < data.length; i += 4) greenSum += data[i];
            const avgGreen = greenSum / (data.length / 4);
            
            rppgBufferRef.current.push(avgGreen);
            rppgTimesRef.current.push(Date.now());
            
            if (rppgBufferRef.current.length > 150) {
                rppgBufferRef.current.shift();
                rppgTimesRef.current.shift();
            }
            
            // Update BPM every 1 second if buffer is full
            if (rppgBufferRef.current.length >= 150 && Date.now() - lastBpmUpdateRef.current > 1000) {
                // Simple peak counting for BPM (approximate rPPG)
                const signal = rppgBufferRef.current;
                const mean = signal.reduce((a, b) => a + b) / signal.length;
                let peaks = 0;
                for (let i = 1; i < signal.length - 1; i++) {
                    if (signal[i] > mean && signal[i] > signal[i-1] && signal[i] > signal[i+1]) peaks++;
                }
                const durationSec = (rppgTimesRef.current[rppgTimesRef.current.length-1] - rppgTimesRef.current[0]) / 1000;
                const detectedBpm = Math.round((peaks / durationSec) * 60);
                if (detectedBpm > 45 && detectedBpm < 180) {
                    currentBpm = Math.round(0.8 * currentBpm + 0.2 * detectedBpm);
                }
                lastBpmUpdateRef.current = Date.now();
            }
            // Draw ROI for visual feedback
            ctx.strokeStyle = '#00c8ff';
            ctx.lineWidth = 1;
            ctx.strokeRect(nx - roiSize, ny - roiSize, roiSize * 2, roiSize * 2);
        } catch(e) { /* ROI out of bounds */ }
    }

    // 2. Height & Weight
    const lAnkle = lm[27];
    const rAnkle = lm[28];
    const lHip   = lm[23];
    const rHip   = lm[24];
    
    let estHeight = biometrics.height || 0;
    let estWeight = biometrics.weight || 0;
    let estBF     = biometrics.body_fat || 0;

    // Safety Guard: Only calculate if we can see the person's full torso and legs
    if (nose && lHip && rHip && nose.visibility > 0.6 && lHip.visibility > 0.6) {
        if (lAnkle && rAnkle && lAnkle.visibility > 0.5) {
            const midAnkleY = (lAnkle.y + rAnkle.y) / 2;
            estHeight = Math.round((midAnkleY - nose.y) * 220);
            
            const shL = lm[11], shR = lm[12];
            if (shL && shR && shL.visibility > 0.6) {
                const shW = Math.sqrt(Math.pow(shL.x - shR.x, 2) + Math.pow(shL.y - shR.y, 2));
                const hipW = Math.sqrt(Math.pow(lHip.x - rHip.x, 2) + Math.pow(lHip.y - rHip.y, 2));
                const vRatio = hipW / (shW + 1e-6);
                const hM = estHeight / 100;
                estWeight = Math.round((hM * hM) * (shW * 150) + (vRatio * 20));
                estBF = Math.round(vRatio * 30);
            }
            }
        } else {
            // Upper Body Fallback: Estimate from shoulder width and head size
            const shL = lm[11], shR = lm[12];
            if (shL && shR && shL.visibility > 0.6) {
                const shW = Math.sqrt(Math.pow(shL.x - shR.x, 2) + Math.pow(shL.y - shR.y, 2));
                // Assuming average shoulder width is 40cm
                const headToSh = Math.abs(shL.y - nose.y);
                estHeight = Math.round((headToSh * 10) * 170); // Very rough guess
                if (estHeight > 220) estHeight = 175; // Clamp
                if (estHeight < 140) estHeight = 160; 
                
                estWeight = Math.round(shW * 500); // Rough guess
                estBF = 18; // Default
            }
        }

    setBiometrics({
        height: estHeight,
        weight: estWeight,
        body_fat: estBF,
        heart_rate: currentBpm
    });
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
    if (videoRef.current) {
      camera = new Camera(videoRef.current, {
        onFrame: async () => {
          if (videoRef.current) {
            await pose.send({ image: videoRef.current });
          }
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
  }, [exercise, onResults]);

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
      onSessionEnd({ 
        reps: counter, 
        accuracy: avg, 
        exercise,
        height: biometrics.height,
        weight: biometrics.weight,
        body_fat: biometrics.body_fat,
        heart_rate: biometrics.heart_rate
      });
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

        {/* Auto Detection Badge */}
        <div className="flex items-center gap-3 bg-blue-600/10 px-6 py-3 rounded-2xl border border-blue-500/20">
          <Activity className="text-blue-500 animate-pulse" size={16} />
          <span className="text-[10px] font-black text-white uppercase tracking-widest">
            AI Detected: <span className="text-blue-400">{exercise}</span>
          </span>
        </div>

        <button
          onClick={toggleWorkout}
          className={`flex items-center gap-2 px-8 py-3 rounded-2xl font-bold transition-all ${
            isActive
              ? 'bg-red-500/20 text-red-500 border border-red-500/50'
              : 'bg-emerald-500 text-white shadow-xl shadow-emerald-500/20'
          }`}
        >
          {isActive ? <><Square size={18} /> Finish Session</> : <><Play size={18} /> Resume AI Tracking</>}
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

          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            <div className="p-6 bg-white/[0.02] rounded-3xl border border-white/10 shadow-xl">
              <span className="text-slate-500 text-[10px] font-black uppercase tracking-[0.2em]">Est. Height</span>
              <div className="text-3xl font-black text-white mt-2 tabular-nums">
                {biometrics.height > 0 ? biometrics.height : '--'} <span className="text-xs text-slate-500">{biometrics.height > 0 ? 'cm' : ''}</span>
              </div>
            </div>
            <div className="p-6 bg-white/[0.02] rounded-3xl border border-white/10 shadow-xl">
              <span className="text-slate-500 text-[10px] font-black uppercase tracking-[0.2em]">Est. Weight</span>
              <div className="text-3xl font-black text-white mt-2 tabular-nums">
                {biometrics.weight > 0 ? biometrics.weight : '--'} <span className="text-xs text-slate-500">{biometrics.weight > 0 ? 'kg' : ''}</span>
              </div>
            </div>
            <div className="p-6 bg-white/[0.02] rounded-3xl border border-white/10 shadow-xl">
              <span className="text-slate-500 text-[10px] font-black uppercase tracking-[0.2em]">Body Fat</span>
              <div className="text-3xl font-black text-white mt-2 tabular-nums">
                {biometrics.body_fat > 0 ? biometrics.body_fat : '--'} <span className="text-xs text-slate-500">{biometrics.body_fat > 0 ? '%' : ''}</span>
              </div>
            </div>
            <div className="p-6 bg-white/[0.02] rounded-3xl border border-white/10 shadow-xl">
              <span className="text-slate-500 text-[10px] font-black uppercase tracking-[0.2em]">Heart Rate</span>
              <div className="text-3xl font-black text-emerald-500 mt-2 tabular-nums flex items-center gap-2">
                {biometrics.heart_rate} <Activity size={18} className="animate-pulse" />
              </div>
            </div>
          </div>

          {/* Trainer Tips */}
          <div className="p-6 bg-blue-600/5 rounded-3xl border border-blue-500/20">
            <h4 className="text-blue-400 font-black text-xs uppercase tracking-widest mb-4 flex items-center gap-2">
              <Info size={14} /> Trainer Tips
            </h4>
            <ul className="text-xs text-slate-400 flex flex-col gap-3 font-bold">
              {exercise === 'Jumping Jacks' && (<>
                <li className="flex items-start gap-3"><CheckCircle2 size={14} className="text-emerald-500 shrink-0" /> Jump feet wide and hands up</li>
                <li className="flex items-start gap-3"><CheckCircle2 size={14} className="text-emerald-500 shrink-0" /> Stay light on your toes</li>
                <li className="flex items-start gap-3"><CheckCircle2 size={14} className="text-emerald-500 shrink-0" /> Maintain a steady rhythm</li>
              </>)}
              {exercise === 'Tricep Extensions' && (<>
                <li className="flex items-start gap-3"><CheckCircle2 size={14} className="text-emerald-500 shrink-0" /> Keep elbows close to ears</li>
                <li className="flex items-start gap-3"><CheckCircle2 size={14} className="text-emerald-500 shrink-0" /> Full extension at the top</li>
                <li className="flex items-start gap-3"><CheckCircle2 size={14} className="text-emerald-500 shrink-0" /> Lower weight slowly behind head</li>
              </>)}
              {exercise === 'Front Raises' && (<>
                <li className="flex items-start gap-3"><CheckCircle2 size={14} className="text-emerald-500 shrink-0" /> Keep arms straight but not locked</li>
                <li className="flex items-start gap-3"><CheckCircle2 size={14} className="text-emerald-500 shrink-0" /> Raise to shoulder level</li>
                <li className="flex items-start gap-3"><CheckCircle2 size={14} className="text-emerald-500 shrink-0" /> Control the weight on the way down</li>
              </>)}
              {exercise === 'Plank' && (<>
                <li className="flex items-start gap-3"><CheckCircle2 size={14} className="text-emerald-500 shrink-0" /> Keep your body in a straight line</li>
                <li className="flex items-start gap-3"><CheckCircle2 size={14} className="text-emerald-500 shrink-0" /> Squeeze your core and glutes</li>
                <li className="flex items-start gap-3"><CheckCircle2 size={14} className="text-emerald-500 shrink-0" /> Don't let your hips sag</li>
              </>)}
              {exercise === 'Shrugs' && (<>
                <li className="flex items-start gap-3"><CheckCircle2 size={14} className="text-emerald-500 shrink-0" /> Raise shoulders toward ears</li>
                <li className="flex items-start gap-3"><CheckCircle2 size={14} className="text-emerald-500 shrink-0" /> Squeeze traps at the top</li>
                <li className="flex items-start gap-3"><CheckCircle2 size={14} className="text-emerald-500 shrink-0" /> Avoid rolling your shoulders</li>
              </>)}
              {exercise === 'Squats' && (<>
                <li className="flex items-start gap-3"><CheckCircle2 size={14} className="text-emerald-500 shrink-0" /> Chest up, shoulders back</li>
                <li className="flex items-start gap-3"><CheckCircle2 size={14} className="text-emerald-500 shrink-0" /> Hips below knee level</li>
                <li className="flex items-start gap-3"><CheckCircle2 size={14} className="text-emerald-500 shrink-0" /> Keep knees in line with toes</li>
              </>)}
              {exercise === 'Pushups' && (<>
                <li className="flex items-start gap-3"><CheckCircle2 size={14} className="text-emerald-500 shrink-0" /> Body in a straight line</li>
                <li className="flex items-start gap-3"><CheckCircle2 size={14} className="text-emerald-500 shrink-0" /> Chest almost touches floor</li>
                <li className="flex items-start gap-3"><CheckCircle2 size={14} className="text-emerald-500 shrink-0" /> Elbows at 45 degree angle</li>
              </>)}
              {exercise === 'Shoulder Press' && (<>
                <li className="flex items-start gap-3"><CheckCircle2 size={14} className="text-emerald-500 shrink-0" /> Full lockout at the top</li>
                <li className="flex items-start gap-3"><CheckCircle2 size={14} className="text-emerald-500 shrink-0" /> Lower bar to chin level</li>
                <li className="flex items-start gap-3"><CheckCircle2 size={14} className="text-emerald-500 shrink-0" /> Keep core tight, no back arch</li>
              </>)}
              {exercise === 'Bench Press' && (<>
                <li className="flex items-start gap-3"><CheckCircle2 size={14} className="text-emerald-500 shrink-0" /> Keep feet flat on floor</li>
                <li className="flex items-start gap-3"><CheckCircle2 size={14} className="text-emerald-500 shrink-0" /> Bar touches mid-chest</li>
                <li className="flex items-start gap-3"><CheckCircle2 size={14} className="text-emerald-500 shrink-0" /> Drive bar up with control</li>
              </>)}
              {exercise === 'Sit-ups' && (<>
                <li className="flex items-start gap-3"><CheckCircle2 size={14} className="text-emerald-500 shrink-0" /> Hands behind ears or on chest</li>
                <li className="flex items-start gap-3"><CheckCircle2 size={14} className="text-emerald-500 shrink-0" /> Sit up until elbows touch knees</li>
                <li className="flex items-start gap-3"><CheckCircle2 size={14} className="text-emerald-500 shrink-0" /> Roll back down slowly</li>
              </>)}
              {exercise === 'Lateral Raises' && (<>
                <li className="flex items-start gap-3"><CheckCircle2 size={14} className="text-emerald-500 shrink-0" /> Slight bend in elbows</li>
                <li className="flex items-start gap-3"><CheckCircle2 size={14} className="text-emerald-500 shrink-0" /> Raise weights to shoulder height</li>
                <li className="flex items-start gap-3"><CheckCircle2 size={14} className="text-emerald-500 shrink-0" /> Avoid using momentum (swinging)</li>
              </>)}
              {exercise === 'Lunges' && (<>
                <li className="flex items-start gap-3"><CheckCircle2 size={14} className="text-emerald-500 shrink-0" /> 90° bend in both knees</li>
                <li className="flex items-start gap-3"><CheckCircle2 size={14} className="text-emerald-500 shrink-0" /> Keep upper body vertical</li>
                <li className="flex items-start gap-3"><CheckCircle2 size={14} className="text-emerald-500 shrink-0" /> Step back to starting position</li>
              </>)}
              {exercise === 'Deadlift' && (<>
                <li className="flex items-start gap-3"><CheckCircle2 size={14} className="text-emerald-500 shrink-0" /> Keep back flat, not rounded</li>
                <li className="flex items-start gap-3"><CheckCircle2 size={14} className="text-emerald-500 shrink-0" /> Bar stays close to legs</li>
                <li className="flex items-start gap-3"><CheckCircle2 size={14} className="text-emerald-500 shrink-0" /> Lock out hips at the top</li>
              </>)}
              {exercise === 'Bicep Curls' && (<>
                <li className="flex items-start gap-3"><CheckCircle2 size={14} className="text-emerald-500 shrink-0" /> Keep elbows tucked to sides</li>
                <li className="flex items-start gap-3"><CheckCircle2 size={14} className="text-emerald-500 shrink-0" /> Full extension at bottom</li>
                <li className="flex items-start gap-3"><CheckCircle2 size={14} className="text-emerald-500 shrink-0" /> Squeeze at the top</li>
              </>)}
              {(exercise === 'Standing' || exercise === 'Detecting...') && (<>
                <li className="flex items-start gap-3"><Info size={14} className="text-blue-400 shrink-0" /> Stand 6-8 feet back for best accuracy</li>
                <li className="flex items-start gap-3"><Info size={14} className="text-blue-400 shrink-0" /> Ensure your full body is in frame</li>
                <li className="flex items-start gap-3"><Info size={14} className="text-blue-400 shrink-0" /> AI will auto-detect your exercise</li>
              </>)}
            </ul>
          </div>
        </div>
      </div>
    </div>
  );
};

export default WorkoutFormAI;
