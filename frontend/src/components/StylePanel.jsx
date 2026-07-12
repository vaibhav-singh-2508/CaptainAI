/**
 * StylePanel — shows Granite metadata + preset selector + manual overrides.
 *
 * Props:
 *   graniteResult  — raw GraniteResult from SSE (genre, keywords, summary, style_preset)
 *   style          — current StylePreset object
 *   onStyleChange  — (newStyle) => void
 */

import { STYLE_PRESETS } from '../hooks/useSubtitleEditor'

const PRESET_NAMES = ['cinematic', 'social', 'education', 'minimal', 'karaoke']

const GENRE_BADGE_COLOR = {
  study: 'bg-blue-100 text-blue-800',
  talk:  'bg-green-100 text-green-800',
  song:  'bg-pink-100 text-pink-800',
  vlog:  'bg-yellow-100 text-yellow-800',
}

function GenreBadge({ label, confidence }) {
  const cls = GENRE_BADGE_COLOR[label] ?? 'bg-gray-100 text-gray-700'
  return (
    <span className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-sm font-semibold ${cls}`}>
      {label?.toUpperCase()}
      {confidence != null && (
        <span className="text-xs opacity-60 font-normal">{Math.round(confidence * 100)}%</span>
      )}
    </span>
  )
}

export default function StylePanel({ graniteResult, style, onStyleChange }) {
  if (!style || !graniteResult) {
    return (
      <div className="text-gray-400 text-sm p-4">Loading style panel…</div>
    )
  }

  const { genre, keywords, summary, style_preset: recommendedPreset } = graniteResult

  const handlePresetClick = (presetName) => {
    onStyleChange(STYLE_PRESETS[presetName])
  }

  const handleOverride = (field, value) => {
    onStyleChange({ ...style, [field]: value })
  }

  return (
    <div className="flex flex-col gap-5">
      {/* Granite metadata */}
      <div>
        <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">
          AI Analysis
        </h3>

        {/* Genre */}
        <div className="flex items-center gap-2 mb-2">
          <span className="text-xs text-gray-500">Genre:</span>
          <GenreBadge
            label={genre?.label ?? genre}
            confidence={genre?.confidence}
          />
          {style.preset_name && style.preset_name !== 'karaoke' && (
            <span className="text-xs text-gray-400 ml-1">
              → <em>{style.preset_name}</em> style recommended
            </span>
          )}
        </div>

        {/* Summary */}
        {summary && (
          <p className="text-sm text-gray-600 italic mb-3">"{summary}"</p>
        )}

        {/* Keywords */}
        {keywords && keywords.length > 0 && (
          <div className="flex flex-wrap gap-1.5">
            {keywords.map((kw) => (
              <span
                key={kw}
                className="px-2 py-0.5 bg-gray-100 text-gray-600 rounded text-xs"
              >
                {kw}
              </span>
            ))}
          </div>
        )}
      </div>

      {/* Preset selector */}
      <div>
        <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">
          Style Preset
        </h3>
        <div className="flex flex-wrap gap-2">
          {PRESET_NAMES.map((name) => {
            const isActive = style.preset_name === name
            const isRecommended = recommendedPreset === name
            return (
              <button
                key={name}
                onClick={() => handlePresetClick(name)}
                className={[
                  'px-3 py-1.5 rounded-lg text-sm font-medium border transition-all',
                  isActive
                    ? 'bg-blue-600 border-blue-600 text-white'
                    : 'bg-white border-gray-300 text-gray-700 hover:border-blue-400',
                ].join(' ')}
              >
                {name.charAt(0).toUpperCase() + name.slice(1)}
                {isRecommended && !isActive && (
                  <span className="ml-1 text-xs text-blue-500">★</span>
                )}
              </button>
            )
          })}
        </div>
        <p className="mt-1.5 text-xs text-gray-400">
          ★ AI-recommended preset
        </p>
      </div>

      {/* Manual overrides */}
      <div>
        <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-3">
          Manual Overrides
        </h3>

        <div className="flex flex-col gap-3">
          {/* Font size */}
          <div className="flex items-center gap-3">
            <label className="text-xs text-gray-500 w-20 shrink-0">Font size</label>
            <input
              type="range"
              min={12}
              max={48}
              step={2}
              value={style.font_size}
              onChange={(e) => handleOverride('font_size', Number(e.target.value))}
              className="flex-1"
            />
            <span className="text-xs text-gray-600 w-8 text-right">{style.font_size}px</span>
          </div>

          {/* Text color */}
          <div className="flex items-center gap-3">
            <label className="text-xs text-gray-500 w-20 shrink-0">Text color</label>
            <input
              type="color"
              value={style.primary_color}
              onChange={(e) => handleOverride('primary_color', e.target.value)}
              className="w-8 h-8 rounded border border-gray-300 cursor-pointer p-0.5"
            />
            <span className="text-xs text-gray-400 font-mono">{style.primary_color}</span>
          </div>

          {/* Outline color */}
          <div className="flex items-center gap-3">
            <label className="text-xs text-gray-500 w-20 shrink-0">Outline</label>
            <input
              type="color"
              value={style.outline_color}
              onChange={(e) => handleOverride('outline_color', e.target.value)}
              className="w-8 h-8 rounded border border-gray-300 cursor-pointer p-0.5"
            />
            <span className="text-xs text-gray-400 font-mono">{style.outline_color}</span>
          </div>

          {/* Position */}
          <div className="flex items-center gap-3">
            <label className="text-xs text-gray-500 w-20 shrink-0">Position</label>
            <div className="flex gap-2">
              {['top', 'bottom'].map((pos) => (
                <button
                  key={pos}
                  onClick={() => handleOverride('position', pos)}
                  className={[
                    'px-2.5 py-1 rounded text-xs font-medium border',
                    style.position === pos
                      ? 'bg-blue-600 border-blue-600 text-white'
                      : 'bg-white border-gray-300 text-gray-600 hover:border-blue-300',
                  ].join(' ')}
                >
                  {pos.charAt(0).toUpperCase() + pos.slice(1)}
                </button>
              ))}
            </div>
          </div>

          {/* Bold toggle */}
          <div className="flex items-center gap-3">
            <label className="text-xs text-gray-500 w-20 shrink-0">Bold</label>
            <button
              onClick={() => handleOverride('bold', !style.bold)}
              className={[
                'px-2.5 py-1 rounded text-xs font-medium border',
                style.bold
                  ? 'bg-blue-600 border-blue-600 text-white'
                  : 'bg-white border-gray-300 text-gray-600 hover:border-blue-300',
              ].join(' ')}
            >
              {style.bold ? 'On' : 'Off'}
            </button>
          </div>

          {/* Background box toggle */}
          <div className="flex items-center gap-3">
            <label className="text-xs text-gray-500 w-20 shrink-0">BG box</label>
            <button
              onClick={() => handleOverride('background_box', !style.background_box)}
              className={[
                'px-2.5 py-1 rounded text-xs font-medium border',
                style.background_box
                  ? 'bg-blue-600 border-blue-600 text-white'
                  : 'bg-white border-gray-300 text-gray-600 hover:border-blue-300',
              ].join(' ')}
            >
              {style.background_box ? 'On' : 'Off'}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
