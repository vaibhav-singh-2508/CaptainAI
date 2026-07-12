/**
 * PreviewPlayer — HTML5 video with CSS-overlay subtitle rendering.
 *
 * Subtitles are rendered as a positioned div absolutely overlaid on the video.
 * On each `timeupdate` event, the active segment (start <= currentTime < end)
 * is found and its corrected_text is displayed with styles from the StylePreset.
 *
 * No FFmpeg. No server round-trip. Purely browser-side.
 *
 * Props:
 *   videoUrl   — backend URL for the original video file
 *   segments   — array of Segment objects
 *   style      — StylePreset object
 *   seekTo     — number (seconds) — when this changes, the video is seeked
 *   onTimeUpdate(time) — called with current video time on each timeupdate
 */

import { useEffect, useRef, useState } from 'react'

function buildSubtitleStyle(style) {
  if (!style) return {}

  const positionClass = style.position === 'top' ? 'top' : 'bottom'

  return {
    fontFamily: style.font_name || 'Arial',
    fontSize: `${style.font_size || 22}px`,
    color: style.primary_color || '#FFFFFF',
    fontWeight: style.bold ? 'bold' : 'normal',
    textShadow: style.outline_color
      ? `1px 1px 2px ${style.outline_color}, -1px -1px 2px ${style.outline_color},
         1px -1px 2px ${style.outline_color}, -1px 1px 2px ${style.outline_color}`
      : '1px 1px 2px #000',
    backgroundColor: style.background_box
      ? 'rgba(0,0,0,0.6)'
      : 'transparent',
    padding: style.background_box ? '4px 10px' : '0',
    borderRadius: style.background_box ? '4px' : '0',
    maxWidth: '85%',
    textAlign: 'center',
    lineHeight: '1.3',
    pointerEvents: 'none',
    position: 'absolute',
    left: '50%',
    transform: 'translateX(-50%)',
    [positionClass]: '5%',
  }
}

export default function PreviewPlayer({ videoUrl, segments, style, seekTo, onTimeUpdate }) {
  const videoRef = useRef(null)
  const [activeText, setActiveText] = useState('')
  const [currentStyle, setCurrentStyle] = useState(style)

  // Sync style updates to local state
  useEffect(() => {
    setCurrentStyle(style)
  }, [style])

  // Seek when seekTo prop changes
  useEffect(() => {
    if (videoRef.current && seekTo !== undefined && seekTo !== null) {
      videoRef.current.currentTime = seekTo
    }
  }, [seekTo])

  const handleTimeUpdate = () => {
    const video = videoRef.current
    if (!video || !segments || segments.length === 0) {
      setActiveText('')
      return
    }

    const t = video.currentTime
    const active = segments.find((s) => t >= s.start && t < s.end)
    setActiveText(active ? active.corrected_text : '')

    if (onTimeUpdate) onTimeUpdate(t)
  }

  const subtitleStyle = buildSubtitleStyle(currentStyle)

  return (
    <div className="relative w-full bg-black rounded-xl overflow-hidden">
      {videoUrl ? (
        <video
          ref={videoRef}
          src={videoUrl}
          controls
          className="w-full block"
          onTimeUpdate={handleTimeUpdate}
          onLoadedMetadata={() => setActiveText('')}
        />
      ) : (
        <div className="flex items-center justify-center h-48 text-gray-500 text-sm">
          No video loaded.
        </div>
      )}

      {/* Subtitle overlay */}
      {activeText && (
        <div style={subtitleStyle}>
          {activeText}
        </div>
      )}
    </div>
  )
}
