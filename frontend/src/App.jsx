/**
 * App.jsx — CaptainAI main workflow controller.
 *
 * View states:
 *   "upload"      — Uploader page (initial state)
 *   "processing"  — ProgressTracker while SSE pipeline runs
 *   "editor"      — Full editor: SubtitleEditor + PreviewPlayer + StylePanel + ExportButtons
 *
 * Flow:
 *   1. User uploads → POST /upload → receive job_id
 *   2. POST /process/{job_id} starts the pipeline
 *   3. GET /status/{job_id} SSE stream → ProgressTracker updates
 *   4. On "ready" stage → editor view renders with all data
 *   5. User edits subtitles, adjusts style, previews, exports
 *   6. "Upload New Video" button → reset all state → back to upload
 */

import { useState, useEffect, useRef, useCallback } from 'react'
import axios from 'axios'

import Uploader from './components/Uploader'
import ProgressTracker from './components/ProgressTracker'
import SubtitleEditor from './components/SubtitleEditor'
import PreviewPlayer from './components/PreviewPlayer'
import StylePanel from './components/StylePanel'
import ExportButtons from './components/ExportButtons'
import { useJobStatus } from './hooks/useJobStatus'
import { useSubtitleEditor } from './hooks/useSubtitleEditor'

const API_BASE = 'http://localhost:8000'

// ── Helpers ────────────────────────────────────────────────────────────────

function findActiveSegmentId(segments, currentTime) {
  const seg = segments.find((s) => currentTime >= s.start && currentTime < s.end)
  return seg ? seg.id : null
}

function getVideoUrl(jobId, uploadResult) {
  if (!jobId || !uploadResult) return null
  const ext = uploadResult.filename?.split('.').pop() ?? 'mp4'
  return `${API_BASE}/download/${jobId}/original.${ext}`
}

// ── Layout components ──────────────────────────────────────────────────────

function Header({ onReset, showReset }) {
  return (
    <header className="bg-white border-b border-gray-200 px-6 py-3 flex items-center justify-between">
      <div className="flex items-center gap-3">
        {/* CaptainAI branding */}
        <div className="flex items-center gap-2">
          <svg className="w-7 h-7 text-blue-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
            <path strokeLinecap="round" strokeLinejoin="round"
              d="M15.75 9V5.25A2.25 2.25 0 0013.5 3h-6a2.25 2.25 0 00-2.25 2.25v13.5A2.25 2.25 0 007.5 21h6a2.25 2.25 0 002.25-2.25V15M12 9l3 3m0 0l-3 3m3-3H2.25" />
          </svg>
          <span className="text-lg font-bold text-gray-900 tracking-tight">CaptainAI</span>
        </div>
        <span className="hidden sm:inline text-gray-300">|</span>
        <span className="hidden sm:inline text-sm text-gray-400">AI Subtitle Intelligence · IBM Granite (Ollama)</span>
      </div>

      {showReset && (
        <button
          onClick={onReset}
          className="flex items-center gap-1.5 text-sm text-gray-500 hover:text-gray-800 transition-colors px-3 py-1.5 rounded-lg hover:bg-gray-100"
        >
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
          </svg>
          Upload New Video
        </button>
      )}
    </header>
  )
}

// ── Main App ───────────────────────────────────────────────────────────────

export default function App() {
  // View state
  const [view, setView] = useState('upload') // 'upload' | 'processing' | 'editor'

  // Upload result (contains job_id, filename, duration)
  const [uploadResult, setUploadResult] = useState(null)
  const [jobId, setJobId] = useState(null)

  // Video seek state (a ref-style counter to trigger PreviewPlayer seek)
  const [seekTo, setSeekTo] = useState(null)
  const [currentVideoTime, setCurrentVideoTime] = useState(0)

  // SSE pipeline status
  const { stage, pct, result: sseResult, error: sseError } = useJobStatus(jobId)

  // Subtitle editor state
  const {
    segments,
    style,
    updateSegmentText,
    setStyle,
    initFromResult,
    reset: resetEditor,
  } = useSubtitleEditor()

  // ── When SSE reaches "ready", initialise the editor ──────────────────────
  const initialised = useRef(false)
  useEffect(() => {
    if (stage === 'ready' && sseResult && !initialised.current) {
      initialised.current = true
      initFromResult(sseResult)
      setView('editor')
    }
  }, [stage, sseResult, initFromResult])

  // ── Handlers ──────────────────────────────────────────────────────────────

  const handleUploadSuccess = useCallback(async (uploadData) => {
    setUploadResult(uploadData)
    const id = uploadData.job_id
    setJobId(id)
    setView('processing')
    initialised.current = false

    // Start the pipeline immediately after a successful upload
    try {
      await axios.post(`${API_BASE}/process/${id}`)
    } catch (err) {
      console.error('Failed to start pipeline:', err)
    }
  }, [])

  const handleReset = useCallback(() => {
    setJobId(null)
    setUploadResult(null)
    setSeekTo(null)
    setCurrentVideoTime(0)
    initialised.current = false
    resetEditor()
    setView('upload')
  }, [resetEditor])

  const handleSegmentSeek = useCallback((startTime) => {
    setSeekTo(startTime)
  }, [])

  const handleTimeUpdate = useCallback((time) => {
    setCurrentVideoTime(time)
  }, [])

  // ── Derived ───────────────────────────────────────────────────────────────

  const activeSegmentId = findActiveSegmentId(segments, currentVideoTime)
  const videoUrl = getVideoUrl(jobId, uploadResult)
  const graniteResult = sseResult?.granite_result ?? null

  // ── Render ────────────────────────────────────────────────────────────────

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col">
      <Header
        onReset={handleReset}
        showReset={view !== 'upload'}
      />

      <main className="flex-1 flex flex-col">
        {/* ── Upload view ─────────────────────────────────────────────── */}
        {view === 'upload' && (
          <div className="flex-1 flex flex-col items-center justify-center p-6">
            <Uploader onUploadSuccess={handleUploadSuccess} />
            {/* Attribution footer */}
            <p className="mt-6 text-xs text-gray-400 text-center">
              Powered by IBM Granite via Ollama · Built with CaptainAI
            </p>
          </div>
        )}

        {/* ── Processing view ──────────────────────────────────────────── */}
        {view === 'processing' && (
          <div className="flex-1 flex flex-col items-center justify-center p-8 gap-8">
            <div className="text-center">
              <h2 className="text-2xl font-bold text-gray-800 mb-1">Processing your file…</h2>
              <p className="text-gray-500 text-sm">
                {uploadResult?.filename && (
                  <span className="font-medium text-gray-700">{uploadResult.filename}</span>
                )}
                {uploadResult?.duration_seconds && (
                  <span className="text-gray-400"> · {uploadResult.duration_seconds.toFixed(1)}s</span>
                )}
              </p>
            </div>

            <ProgressTracker stage={stage} pct={pct} error={sseError} />

            {/* Granite/Ollama attribution badge */}
            <div className="mt-4 flex items-center gap-2 text-xs text-gray-400 border border-gray-200 rounded-full px-4 py-1.5 bg-white">
              <svg className="w-4 h-4 text-blue-500" fill="currentColor" viewBox="0 0 24 24">
                <circle cx="12" cy="12" r="10"/>
              </svg>
              AI processing by IBM Granite (local Ollama)
            </div>
          </div>
        )}

        {/* ── Editor view ──────────────────────────────────────────────── */}
        {view === 'editor' && (
          <div className="flex-1 grid grid-cols-1 lg:grid-cols-[1fr_380px] gap-0 h-full min-h-0">

            {/* ── Left column: video + subtitle editor ─────────────────── */}
            <div className="flex flex-col gap-4 p-4 overflow-y-auto">
              {/* Video preview */}
              <div className="bg-white rounded-2xl border border-gray-200 overflow-hidden">
                <div className="px-4 pt-4 pb-2 border-b border-gray-100">
                  <h2 className="text-sm font-semibold text-gray-700">Preview</h2>
                  {uploadResult?.filename && (
                    <p className="text-xs text-gray-400 mt-0.5 truncate">{uploadResult.filename}</p>
                  )}
                </div>
                <div className="p-4">
                  <PreviewPlayer
                    videoUrl={videoUrl}
                    segments={segments}
                    style={style}
                    seekTo={seekTo}
                    onTimeUpdate={handleTimeUpdate}
                  />
                </div>
              </div>

              {/* Subtitle editor */}
              <div className="bg-white rounded-2xl border border-gray-200">
                <div className="px-4 pt-4 pb-2 border-b border-gray-100 flex items-center justify-between">
                  <div>
                    <h2 className="text-sm font-semibold text-gray-700">Subtitle Editor</h2>
                    <p className="text-xs text-gray-400 mt-0.5">
                      Click a segment to seek · Edit text freely · Timestamps are read-only
                    </p>
                  </div>
                  <span className="text-xs bg-gray-100 text-gray-500 px-2 py-1 rounded-full">
                    {segments.length} segments
                  </span>
                </div>
                <div className="p-4">
                  <SubtitleEditor
                    segments={segments}
                    onTextChange={updateSegmentText}
                    onSeek={handleSegmentSeek}
                    activeSegmentId={activeSegmentId}
                  />
                </div>
              </div>
            </div>

            {/* ── Right column: style panel + export ───────────────────── */}
            <div className="flex flex-col gap-4 p-4 lg:border-l border-gray-200 overflow-y-auto bg-white">
              {/* Style panel */}
              <StylePanel
                graniteResult={graniteResult}
                style={style}
                onStyleChange={setStyle}
              />

              <div className="border-t border-gray-100 pt-4">
                <ExportButtons
                  jobId={jobId}
                  segments={segments}
                  style={style}
                />
              </div>

              {/* Watermark / attribution */}
              <div className="mt-auto pt-6 border-t border-gray-100 text-center">
                <p className="text-xs text-gray-400">
                  Subtitles powered by{' '}
                  <span className="font-semibold text-blue-500">IBM Granite</span>
                  {' '}via{' '}
                  <span className="font-semibold">Ollama</span>
                </p>
                <p className="text-xs text-gray-300 mt-0.5">CaptainAI · IBM Challenge Submission</p>
              </div>
            </div>
          </div>
        )}
      </main>
    </div>
  )
}
