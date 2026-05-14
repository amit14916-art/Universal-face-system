import { useState, useRef } from 'react';
import { Upload, Zap, AlertCircle, CheckCircle } from 'lucide-react';

const API_BASE = import.meta.env.DEV ? 'http://localhost:8000' : '';

function ImageAnalyzer() {
  const [selectedImage, setSelectedImage] = useState(null);
  const [analysisType, setAnalysisType] = useState('general');
  const [context, setContext] = useState('');
  const [analysis, setAnalysis] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const fileInputRef = useRef(null);

  const analysisTypes = [
    { value: 'general', label: '📸 General Analysis', desc: 'Overall image insights' },
    { value: 'form', label: '💪 Form Analysis', desc: 'Workout form evaluation' },
    { value: 'security', label: '🔒 Security Check', desc: 'Biometric security quality' },
    { value: 'biometric', label: '🎯 Biometric Quality', desc: 'Face identification readiness' }
  ];

  const handleImageSelect = (e) => {
    const file = e.target.files?.[0];
    if (file) {
      const reader = new FileReader();
      reader.onload = (event) => {
        setSelectedImage(event.target?.result);
        setAnalysis(null);
        setError(null);
      };
      reader.readAsDataURL(file);
    }
  };

  const handleAnalyze = async () => {
    if (!selectedImage) {
      setError('Please select an image first');
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const response = await fetch(`${API_BASE}/api/analyze-image`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          image_base64: selectedImage,
          analysis_type: analysisType,
          context: context,
        }),
      });

      if (response.ok) {
        const data = await response.json();
        setAnalysis(data.analysis);
      } else {
        const error = await response.json();
        setError(error.detail || 'Analysis failed');
      }
    } catch (err) {
      console.error('Analysis error:', err);
      setError('Failed to analyze image. Check your connection.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex flex-col h-full bg-gray-50">
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {/* Image Upload Section */}
        <div className="glass-panel p-6 bg-white/[0.01] border-white/5 rounded-[32px]">
          <h3 className="text-lg font-black text-white uppercase tracking-tight mb-4">Upload Image</h3>
          
          <div
            onClick={() => fileInputRef.current?.click()}
            className="border-2 border-dashed border-blue-500/50 rounded-2xl p-8 text-center cursor-pointer hover:bg-blue-500/5 transition-all"
          >
            <Upload className="mx-auto mb-3 text-blue-500" size={32} />
            <p className="text-white font-bold mb-1">Click to upload or drag and drop</p>
            <p className="text-sm text-slate-500">PNG, JPG, WebP up to 10MB</p>
            <input
              ref={fileInputRef}
              type="file"
              accept="image/*"
              onChange={handleImageSelect}
              className="hidden"
            />
          </div>

          {selectedImage && (
            <div className="mt-4">
              <img src={selectedImage} alt="Selected" className="w-full max-h-[300px] object-contain rounded-xl" />
              <button
                onClick={() => {
                  setSelectedImage(null);
                  setAnalysis(null);
                }}
                className="mt-2 w-full py-2 px-4 bg-red-600/10 text-red-400 rounded-lg text-sm font-bold hover:bg-red-600/20"
              >
                Clear Image
              </button>
            </div>
          )}
        </div>

        {/* Analysis Type Selection */}
        <div className="glass-panel p-6 bg-white/[0.01] border-white/5 rounded-[32px]">
          <h3 className="text-lg font-black text-white uppercase tracking-tight mb-4">Analysis Type</h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {analysisTypes.map((type) => (
              <button
                key={type.value}
                onClick={() => setAnalysisType(type.value)}
                className={`p-4 rounded-lg text-left transition-all ${
                  analysisType === type.value
                    ? 'bg-blue-600 border-2 border-blue-400'
                    : 'bg-white/5 border-2 border-white/10 hover:border-blue-500/30'
                }`}
              >
                <div className="font-bold text-white">{type.label}</div>
                <div className="text-xs text-slate-400 mt-1">{type.desc}</div>
              </button>
            ))}
          </div>
        </div>

        {/* Context Input */}
        <div className="glass-panel p-6 bg-white/[0.01] border-white/5 rounded-[32px]">
          <h3 className="text-sm font-black text-white uppercase tracking-tight mb-2">Additional Context (Optional)</h3>
          <textarea
            value={context}
            onChange={(e) => setContext(e.target.value)}
            placeholder="e.g., 'Checking squat form' or 'Security verification for new member'"
            className="w-full bg-[#020617] border-2 border-white/10 rounded-lg p-3 text-white text-sm focus:outline-none focus:border-blue-500"
            rows={3}
          />
        </div>

        {/* Error Display */}
        {error && (
          <div className="bg-red-600/10 border-2 border-red-600/30 rounded-lg p-4 flex items-start gap-3">
            <AlertCircle className="text-red-500 flex-shrink-0 mt-1" size={20} />
            <div>
              <p className="font-bold text-red-400">Error</p>
              <p className="text-sm text-red-300">{error}</p>
            </div>
          </div>
        )}

        {/* Analysis Results */}
        {analysis && (
          <div className="bg-emerald-600/10 border-2 border-emerald-600/30 rounded-lg p-4 space-y-3">
            <div className="flex items-center gap-2">
              <CheckCircle className="text-emerald-500" size={24} />
              <h4 className="font-black text-emerald-400 uppercase text-sm">Analysis Complete</h4>
            </div>
            <div className="bg-black/30 rounded-lg p-4 text-white text-sm leading-relaxed max-h-[400px] overflow-y-auto whitespace-pre-wrap">
              {analysis}
            </div>
          </div>
        )}

        {/* Loading State */}
        {loading && (
          <div className="flex items-center justify-center py-8">
            <div className="text-center">
              <div className="flex gap-1 justify-center mb-3">
                <div className="w-2 h-2 bg-blue-500 rounded-full animate-bounce"></div>
                <div className="w-2 h-2 bg-blue-500 rounded-full animate-bounce" style={{ animationDelay: '0.1s' }}></div>
                <div className="w-2 h-2 bg-blue-500 rounded-full animate-bounce" style={{ animationDelay: '0.2s' }}></div>
              </div>
              <p className="text-slate-400 font-bold text-sm">Analyzing image...</p>
            </div>
          </div>
        )}
      </div>

      {/* Analyze Button */}
      <div className="border-t bg-white/[0.01] p-4">
        <button
          onClick={handleAnalyze}
          disabled={!selectedImage || loading}
          className="w-full bg-blue-600 text-white rounded-lg px-4 py-3 hover:bg-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50 disabled:cursor-not-allowed font-bold flex items-center justify-center gap-2 transition-all"
        >
          <Zap size={18} />
          {loading ? 'Analyzing...' : 'Analyze Image'}
        </button>
      </div>
    </div>
  );
}

export default ImageAnalyzer;