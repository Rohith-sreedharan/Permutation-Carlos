import React, { useState } from 'react';
import { AlertCircle, Upload, CheckCircle } from 'lucide-react';

interface ReceiptTemplateProps {
  threadId: string;
  onClose: () => void;
  onSubmit: (data: any) => void;
}

export const ReceiptTemplate: React.FC<ReceiptTemplateProps> = ({
  threadId,
  onClose,
  onSubmit,
}) => {
  const [formData, setFormData] = useState({
    screenshot_url: '',
    market: '',
    line: '',
    result: 'W' as 'W' | 'L' | 'P',
  });
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [previewImage, setPreviewImage] = useState<string | null>(null);

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    // Client-side blur suggestion for personal info
    const reader = new FileReader();
    reader.onload = (event) => {
      const dataUrl = event.target?.result as string;
      setPreviewImage(dataUrl);
      setFormData({ ...formData, screenshot_url: dataUrl });
    };
    reader.readAsDataURL(file);
  };

  const handleChange = (field: string, value: any) => {
    setFormData({ ...formData, [field]: value });
    if (errors[field]) {
      setErrors({ ...errors, [field]: '' });
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    const newErrors: Record<string, string> = {};

    if (!formData.screenshot_url) newErrors.screenshot_url = 'Screenshot required';
    if (!formData.market) newErrors.market = 'Required';
    if (!formData.line) newErrors.line = 'Required';
    if (!formData.result) newErrors.result = 'Required';

    if (Object.keys(newErrors).length > 0) {
      setErrors(newErrors);
      return;
    }

    onSubmit({
      thread_id: threadId,
      ...formData,
    });
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-4 bg-navy/30 p-4 rounded-lg border border-green-500/30">
      <div className="flex justify-between items-center mb-4">
        <h4 className="font-bold text-green-400">Receipt Template</h4>
        <button type="button" onClick={onClose} className="text-light-gray hover:text-white text-sm">
          ✕
        </button>
      </div>

      {/* Screenshot Upload */}
      <div>
        <label className="text-xs font-bold text-light-gray block mb-2">
          Screenshot <span className="text-red-400">*</span> (Required)
        </label>
        <div className="border-2 border-dashed border-green-500/30 rounded-lg p-4 bg-charcoal/50 cursor-pointer hover:border-green-500/60 transition">
          <input
            type="file"
            accept="image/*"
            onChange={handleFileUpload}
            className="hidden"
            id="screenshot-upload"
          />
          <label htmlFor="screenshot-upload" className="cursor-pointer block text-center">
            {previewImage ? (
              <div className="space-y-2">
                <img src={previewImage} alt="preview" className="w-full max-h-40 object-cover rounded" />
                <p className="text-xs text-green-400">✓ Image selected</p>
              </div>
            ) : (
              <div className="space-y-2">
                <Upload size={24} className="mx-auto text-light-gray" />
                <p className="text-xs text-light-gray">Click to upload screenshot</p>
              </div>
            )}
          </label>
        </div>
        {errors.screenshot_url && <p className="text-xs text-red-400 mt-1">{errors.screenshot_url}</p>}
        <p className="text-xs text-light-gray mt-2 flex items-start space-x-1">
          <AlertCircle size={12} className="mt-0.5 flex-shrink-0" />
          <span>We suggest blurring personal info before uploading</span>
        </p>
      </div>

      {/* Market */}
      <div>
        <label className="text-xs font-bold text-light-gray">Market</label>
        <input
          type="text"
          placeholder="e.g., NBA - Lakers Spread"
          value={formData.market}
          onChange={(e) => handleChange('market', e.target.value)}
          className="w-full mt-1 bg-charcoal border border-navy rounded px-3 py-2 text-white text-sm"
        />
        {errors.market && <p className="text-xs text-red-400 mt-1">{errors.market}</p>}
      </div>

      {/* Line */}
      <div>
        <label className="text-xs font-bold text-light-gray">Line</label>
        <input
          type="text"
          placeholder="e.g., -5.5"
          value={formData.line}
          onChange={(e) => handleChange('line', e.target.value)}
          className="w-full mt-1 bg-charcoal border border-navy rounded px-3 py-2 text-white text-sm"
        />
        {errors.line && <p className="text-xs text-red-400 mt-1">{errors.line}</p>}
      </div>

      {/* Result */}
      <div>
        <label className="text-xs font-bold text-light-gray">Result</label>
        <div className="grid grid-cols-3 gap-2 mt-1">
          {[
            { value: 'W', label: '✓ WIN', color: 'green' },
            { value: 'L', label: '✗ LOSS', color: 'red' },
            { value: 'P', label: '~ PUSH', color: 'yellow' },
          ].map((option) => (
            <button
              key={option.value}
              type="button"
              onClick={() => handleChange('result', option.value)}
              className={`py-2 px-3 rounded text-xs font-bold transition ${
                formData.result === option.value
                  ? `bg-${option.color}-500 text-white`
                  : 'bg-navy text-light-gray hover:bg-navy/70'
              }`}
            >
              {option.label}
            </button>
          ))}
        </div>
      </div>

      {/* Submit */}
      <button
        type="submit"
        className="w-full bg-green-500 text-white font-bold py-2 rounded-lg hover:bg-green-600 transition"
      >
        Post Receipt
      </button>
    </form>
  );
};

interface ParlayBuildTemplateProps {
  threadId: string;
  onClose: () => void;
  onSubmit: (data: any) => void;
}

export const ParlayBuildTemplate: React.FC<ParlayBuildTemplateProps> = ({
  threadId,
  onClose,
  onSubmit,
}) => {
  const [formData, setFormData] = useState({
    leg_count: 2,
    legs: [
      { market: '', line: '', confidence: 'med' },
      { market: '', line: '', confidence: 'med' },
    ],
    risk_profile: 'balanced' as 'balanced' | 'high_vol',
    reasoning: '',
  });
  const [errors, setErrors] = useState<Record<string, string>>({});

  const handleAddLeg = () => {
    if (formData.legs.length < 15) {
      setFormData({
        ...formData,
        legs: [...formData.legs, { market: '', line: '', confidence: 'med' }],
        leg_count: formData.legs.length + 1,
      });
    }
  };

  const handleRemoveLeg = (index: number) => {
    if (formData.legs.length > 2) {
      const newLegs = formData.legs.filter((_, i) => i !== index);
      setFormData({
        ...formData,
        legs: newLegs,
        leg_count: newLegs.length,
      });
    }
  };

  const handleLegChange = (index: number, field: string, value: any) => {
    const newLegs = [...formData.legs];
    newLegs[index] = { ...newLegs[index], [field]: value };
    setFormData({ ...formData, legs: newLegs });
  };

  const handleChange = (field: string, value: any) => {
    setFormData({ ...formData, [field]: value });
    if (errors[field]) {
      setErrors({ ...errors, [field]: '' });
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    const newErrors: Record<string, string> = {};

    if (formData.legs.length < 2) newErrors.legs = 'Minimum 2 legs';
    if (!formData.reasoning || formData.reasoning.length < 10) newErrors.reasoning = 'Min 10 characters';
    if (formData.reasoning.length > 300) newErrors.reasoning = 'Max 300 characters';

    if (Object.keys(newErrors).length > 0) {
      setErrors(newErrors);
      return;
    }

    onSubmit({
      thread_id: threadId,
      ...formData,
    });
  };

  const volatilityBadges = formData.legs.map((leg) => {
    if (leg.confidence === 'high') return 'high_vol';
    if (leg.confidence === 'low') return 'low_confidence';
    return 'balanced';
  });

  return (
    <form onSubmit={handleSubmit} className="space-y-4 bg-navy/30 p-4 rounded-lg border border-purple-500/30">
      <div className="flex justify-between items-center mb-4">
        <h4 className="font-bold text-purple-400">Parlay Build Template</h4>
        <button type="button" onClick={onClose} className="text-light-gray hover:text-white text-sm">
          ✕
        </button>
      </div>

      {/* Legs */}
      <div>
        <div className="flex justify-between items-center mb-2">
          <label className="text-xs font-bold text-light-gray">Legs ({formData.legs.length})</label>
          {formData.legs.length < 15 && (
            <button
              type="button"
              onClick={handleAddLeg}
              className="text-xs text-purple-400 hover:text-purple-300 font-bold"
            >
              + Add Leg
            </button>
          )}
        </div>
        <div className="space-y-2 max-h-48 overflow-y-auto">
          {formData.legs.map((leg, idx) => (
            <div key={idx} className="bg-charcoal/50 p-2 rounded border border-navy space-y-1">
              <div className="flex justify-between items-center">
                <span className="text-xs font-bold text-light-gray">Leg {idx + 1}</span>
                {formData.legs.length > 2 && (
                  <button
                    type="button"
                    onClick={() => handleRemoveLeg(idx)}
                    className="text-xs text-red-400 hover:text-red-300"
                  >
                    Remove
                  </button>
                )}
              </div>
              <input
                type="text"
                placeholder="Market (e.g., Lakers Spread)"
                value={leg.market}
                onChange={(e) => handleLegChange(idx, 'market', e.target.value)}
                className="w-full bg-charcoal border border-navy rounded px-2 py-1 text-white text-xs"
              />
              <input
                type="text"
                placeholder="Line (e.g., -5.5)"
                value={leg.line}
                onChange={(e) => handleLegChange(idx, 'line', e.target.value)}
                className="w-full bg-charcoal border border-navy rounded px-2 py-1 text-white text-xs"
              />
              <select
                value={leg.confidence}
                onChange={(e) => handleLegChange(idx, 'confidence', e.target.value)}
                className="w-full bg-charcoal border border-navy rounded px-2 py-1 text-white text-xs"
              >
                <option value="low">Low Confidence</option>
                <option value="med">Medium Confidence</option>
                <option value="high">High Confidence</option>
              </select>
            </div>
          ))}
        </div>
      </div>

      {/* Risk Profile */}
      <div>
        <label className="text-xs font-bold text-light-gray">Risk Profile</label>
        <div className="grid grid-cols-2 gap-2 mt-1">
          {[
            { value: 'balanced', label: 'Balanced' },
            { value: 'high_vol', label: 'High Vol 📈' },
          ].map((option) => (
            <button
              key={option.value}
              type="button"
              onClick={() => handleChange('risk_profile', option.value)}
              className={`py-2 px-3 rounded text-xs font-bold transition ${
                formData.risk_profile === option.value
                  ? 'bg-purple-500 text-white'
                  : 'bg-navy text-light-gray hover:bg-navy/70'
              }`}
            >
              {option.label}
            </button>
          ))}
        </div>
      </div>

      {/* Reasoning */}
      <div>
        <label className="text-xs font-bold text-light-gray">
          Why These Legs? ({formData.reasoning.length}/300)
        </label>
        <textarea
          placeholder="Explain the logic behind your parlay"
          value={formData.reasoning}
          onChange={(e) => handleChange('reasoning', e.target.value)}
          maxLength={300}
          className="w-full mt-1 bg-charcoal border border-navy rounded px-3 py-2 text-white text-sm"
          rows={3}
        />
        {errors.reasoning && <p className="text-xs text-red-400 mt-1">{errors.reasoning}</p>}
      </div>

      {/* Volatility Badges */}
      <div className="bg-charcoal/50 p-2 rounded text-xs text-light-gray">
        <p className="font-bold mb-1">Volatility Badges:</p>
        <div className="flex flex-wrap gap-1">
          {volatilityBadges.map((badge, idx) => (
            <span key={idx} className="bg-purple-500/20 text-purple-400 px-2 py-0.5 rounded text-xs">
              {badge}
            </span>
          ))}
        </div>
      </div>

      {/* Submit */}
      <button
        type="submit"
        className="w-full bg-purple-500 text-white font-bold py-2 rounded-lg hover:bg-purple-600 transition"
      >
        Post Parlay Build
      </button>
    </form>
  );
};
