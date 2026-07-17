/**
 * ExportButtons — triggers POST /export/{job_id} for SRT, TXT, and MP4 exports.
 *
 * Sub-task 7: All three export formats are now fully implemented.
 *   - Export SRT: calls POST /export with formats=["srt"]
 *   - Export TXT: calls POST /export with formats=["txt"]
 *   - Export MP4: calls POST /export with formats=["mp4"] — runs FFmpeg burn-in
 *                 on the backend; may take 30–90 seconds for longer videos.
 *
 * The current segments and style (including any manual overrides the user made
 * in StylePanel) are sent with every export request so the output exactly
 * matches what the user configured.
 */

import { useState } from 'react'
import axios from 'axios'

const API_BASE = 'http://localhost:8000'

function DownloadIcon() {
  return (
    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
    </svg>
  )
}

function Spinner() {
  return (
    <svg className="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth={4} />
      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
    </svg>
  )
}

function CheckIcon() {
  return (
    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
    </svg>
  )
}

export default function ExportButtons({ jobId, segments, style }) {
  const [loadingSrt, setLoadingSrt] = useState(false)
  const [loadingTxt, setLoadingTxt] = useState(false)
  const [loadingMp4, setLoadingMp4] = useState(false)
  const [successSrt, setSuccessSrt] = useState(false)
  const [successTxt, setSuccessTxt] = useState(false)
  const [successMp4, setSuccessMp4] = useState(false)
  const [exportError, setExportError] = useState(null)

  const triggerDownload = (url, filename) => {
    const a = document.createElement('a')
    a.href = url
    a.download = filename
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
  }

  const handleExport = async (formats, setLoading, setSuccess, filename) => {
    if (!jobId || !segments || !style) return
    setLoading(true)
    setSuccess(false)
    setExportError(null)

    try {
      const response = await axios.post(`${API_BASE}/export/${jobId}`, {
        segments,
        style: {
          preset_name:    style.preset_name,
          font_name:      style.font_name,
          font_size:      style.font_size,
          primary_color:  style.primary_color,
          outline_color:  style.outline_color,
          position:       style.position,
          background_box: style.background_box,
          bold:           style.bold,
        },
        formats,
      })

      const downloadUrls = response.data?.download_urls ?? {}
      const fmt = formats[0]
      const path = downloadUrls[fmt]

      if (path) {
        triggerDownload(`${API_BASE}${path}`, filename)
        setSuccess(true)
        // Clear the success indicator after 3 seconds
        setTimeout(() => setSuccess(false), 3000)
      } else {
        setExportError(`Export succeeded but no download URL was returned for ${fmt}.`)
      }
    } catch (err) {
      const raw = err.response?.data?.detail
      let detail
      if (Array.isArray(raw)) {
        // FastAPI validation error: array of { loc, msg, type } objects
        detail = raw.map((e) => `${e.loc?.slice(1).join(' → ') ?? 'field'}: ${e.msg}`).join('; ')
      } else if (typeof raw === 'string') {
        detail = raw
      } else {
        detail = err.message || 'Export failed.'
      }
      setExportError(detail)
    } finally {
      setLoading(false)
    }
  }

  const canExport = !!(jobId && segments?.length && style)

  return (
    <div className="flex flex-col gap-3">
      <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wider">Export</h3>

      <div className="flex flex-wrap gap-2">
        {/* Export SRT */}
        <button
          onClick={() => handleExport(['srt'], setLoadingSrt, setSuccessSrt, 'subtitles.srt')}
          disabled={!canExport || loadingSrt}
          title="Download SRT subtitle file"
          className={[
            'flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium border transition-all',
            successSrt
              ? 'bg-green-50 border-green-400 text-green-700'
              : canExport && !loadingSrt
              ? 'bg-white border-gray-300 text-gray-700 hover:border-blue-400 hover:text-blue-600'
              : 'bg-gray-50 border-gray-200 text-gray-400 cursor-not-allowed',
          ].join(' ')}
        >
          {loadingSrt ? <Spinner /> : successSrt ? <CheckIcon /> : <DownloadIcon />}
          Export SRT
        </button>

        {/* Export TXT */}
        <button
          onClick={() => handleExport(['txt'], setLoadingTxt, setSuccessTxt, 'transcript.txt')}
          disabled={!canExport || loadingTxt}
          title="Download plain-text transcript"
          className={[
            'flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium border transition-all',
            successTxt
              ? 'bg-green-50 border-green-400 text-green-700'
              : canExport && !loadingTxt
              ? 'bg-white border-gray-300 text-gray-700 hover:border-blue-400 hover:text-blue-600'
              : 'bg-gray-50 border-gray-200 text-gray-400 cursor-not-allowed',
          ].join(' ')}
        >
          {loadingTxt ? <Spinner /> : successTxt ? <CheckIcon /> : <DownloadIcon />}
          Export TXT
        </button>

        {/* Export MP4 — FFmpeg burn-in (Sub-task 7) */}
        <button
          onClick={() => handleExport(['mp4'], setLoadingMp4, setSuccessMp4, 'output.mp4')}
          disabled={!canExport || loadingMp4}
          title="Burn subtitles into the video and download MP4 (may take 30–90 seconds)"
          className={[
            'flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium border transition-all',
            successMp4
              ? 'bg-green-50 border-green-400 text-green-700'
              : loadingMp4
              ? 'bg-blue-50 border-blue-300 text-blue-600 cursor-wait'
              : canExport
              ? 'bg-blue-600 border-blue-600 text-white hover:bg-blue-700'
              : 'bg-gray-50 border-gray-200 text-gray-400 cursor-not-allowed',
          ].join(' ')}
        >
          {loadingMp4 ? <Spinner /> : successMp4 ? <CheckIcon /> : <DownloadIcon />}
          {loadingMp4 ? 'Processing…' : successMp4 ? 'Done!' : 'Export MP4'}
        </button>
      </div>

      {/* MP4 encoding hint */}
      {loadingMp4 && (
        <p className="text-xs text-blue-600 bg-blue-50 border border-blue-200 rounded-lg px-3 py-2">
          Burning subtitles into video… This may take 30–90 seconds depending on video length.
        </p>
      )}

      {/* Error */}
      {exportError && (
        <div className="text-sm text-red-700 bg-red-50 border border-red-200 rounded-lg px-3 py-2">
          {exportError}
        </div>
      )}
    </div>
  )
}
