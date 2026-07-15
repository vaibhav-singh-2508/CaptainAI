/**
 * SubtitleEditor — scrollable list of segments with editable corrected_text.
 *
 * Each segment shows:
 *   - Timestamp (read-only)
 *   - Language badge (EN / HI / HI-EN)
 *   - Editable textarea for corrected_text
 *   - Greyed-out original Whisper text below (side-by-side diff demo)
 *
 * Clicking a segment calls onSeek(segment.start) to seek the video player.
 */

import { useRef } from 'react'

function formatTime(seconds) {
  const h = Math.floor(seconds / 3600)
  const m = Math.floor((seconds % 3600) / 60)
  const s = Math.floor(seconds % 60)
  const ms = Math.round((seconds % 1) * 1000)
  if (h > 0) {
    return `${h}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}.${String(ms).padStart(3, '0')}`
  }
  return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}.${String(ms).padStart(3, '0')}`
}

const LANG_BADGE_STYLE = {
  en:    'bg-blue-100 text-blue-700',
  hi:    'bg-orange-100 text-orange-700',
  'hi-en': 'bg-purple-100 text-purple-700',
}

function LangBadge({ lang }) {
  const cls = LANG_BADGE_STYLE[lang] ?? 'bg-gray-100 text-gray-600'
  return (
    <span className={`inline-block px-1.5 py-0.5 rounded text-xs font-semibold uppercase tracking-wide ${cls}`}>
      {lang}
    </span>
  )
}

export default function SubtitleEditor({ segments, onTextChange, onSeek, activeSegmentId }) {
  const listRef = useRef(null)

  if (!segments || segments.length === 0) {
    return (
      <div className="flex items-center justify-center h-32 text-gray-400 text-sm">
        No subtitles loaded.
      </div>
    )
  }

  return (
    <div ref={listRef} className="flex flex-col gap-2 overflow-y-auto max-h-[60vh] pr-1">
      {segments.map((seg) => {
        const isActive = seg.id === activeSegmentId
        return (
          <div
            key={seg.id}
            className={[
              'rounded-xl border p-3 transition-colors cursor-pointer',
              isActive
                ? 'border-blue-400 bg-blue-50'
                : 'border-gray-200 bg-white hover:border-blue-200 hover:bg-gray-50',
            ].join(' ')}
            onClick={() => onSeek && onSeek(seg.start)}
          >
            {/* Header row: timestamp + language badge */}
            <div className="flex items-center justify-between mb-1.5">
              <span className="text-xs text-gray-400 font-mono">
                {formatTime(seg.start)} → {formatTime(seg.end)}
              </span>
              {seg.language && <LangBadge lang={seg.language} />}
            </div>

            {/* Editable subtitle text (field name is "text" in subtitle_data.json) */}
            <textarea
              className="w-full text-sm text-gray-800 bg-transparent resize-none border-none outline-none focus:ring-0 leading-snug"
              rows={2}
              value={seg.text}
              onChange={(e) => {
                e.stopPropagation()
                if (onTextChange) onTextChange(seg.id, e.target.value)
              }}
              onClick={(e) => e.stopPropagation()}
              spellCheck={false}
            />
          </div>
        )
      })}
    </div>
  )
}
