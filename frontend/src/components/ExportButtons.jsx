/**
 * ExportButtons — triggers POST /export/{job_id} for SRT and TXT exports.
 *
 * Sub-task 6 scope:
 *   - Export SRT: calls POST /export with formats=["srt"]
 *   - Export TXT: calls POST /export with formats=["txt"]
 *   - Export MP4 button is shown but marked "Coming soon" (Sub-task 7)
 *
 * No FFmpeg burn-in in this sub-task.
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

export default function ExportButtons({ jobId, segments, style }) {
  const [loadingSrt, setLoadingSrt] = useState(false)
  const [loadingTxt, setLoadingTxt] = useState(false)
  const [exportError, setExportError]  = useState(null)

  const triggerDownload = (url, filename) => {
    const a = document.createElement('a')
    a.href = url
    a.download = filename
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
  }

  const handleExport = async (formats, setLoading, filename) => {
    if (!jobId || !segments || !style) return
    setLoading(true)
    setExportError(null)

    try {
      const response = await axios.post(`${API_BASE}/export/${jobId}`, {
        segments,
        style: {
          preset_name:   style.preset_name,
          font_name:     style.font_name,
          font_size:     style.font_size,
          primary_color: style.primary_color,
          outline_color: style.outline_color,
          position:      style.position,
          background_box: style.background_box,
          bold:          style.bold,
        },
        formats,
      })

      const downloadUrls = response.data?.download_urls ?? {}
      const fmt = formats[0]
      const path = downloadUrls[fmt]

      if (path) {
        triggerDownload(`${API_BASE}${path}`, filename)
      } else {
        setExportError(`Export succeeded but no download URL was returned for ${fmt}.`)
      }
    } catch (err) {
      const detail = err.response?.data?.detail || err.message || 'Export failed.'
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
          onClick={() => handleExport(['srt'], setLoadingSrt, 'subtitles.srt')}
          disabled={!canExport || loadingSrt}
          className={[
            'flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium border transition-all',
            canExport && !loadingSrt
              ? 'bg-white border-gray-300 text-gray-700 hover:border-blue-400 hover:text-blue-600'
              : 'bg-gray-50 border-gray-200 text-gray-400 cursor-not-allowed',
          ].join(' ')}
        >
          {loadingSrt ? <Spinner /> : <DownloadIcon />}
          Export SRT
        </button>

        {/* Export TXT */}
        <button
          onClick={() => handleExport(['txt'], setLoadingTxt, 'transcript.txt')}
          disabled={!canExport || loadingTxt}
          className={[
            'flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium border transition-all',
            canExport && !loadingTxt
              ? 'bg-white border-gray-300 text-gray-700 hover:border-blue-400 hover:text-blue-600'
              : 'bg-gray-50 border-gray-200 text-gray-400 cursor-not-allowed',
          ].join(' ')}
        >
          {loadingTxt ? <Spinner /> : <DownloadIcon />}
          Export TXT
        </button>

        {/* Export MP4 — Sub-task 7 */}
        <button
          disabled
          title="MP4 burn-in will be available in Sub-task 7"
          className="flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium border border-gray-200 bg-gray-50 text-gray-400 cursor-not-allowed"
        >
          <DownloadIcon />
          Export MP4
          <span className="text-xs bg-gray-200 text-gray-500 px-1.5 py-0.5 rounded ml-1">Soon</span>
        </button>
      </div>

      {/* Error */}
      {exportError && (
        <div className="text-sm text-red-700 bg-red-50 border border-red-200 rounded-lg px-3 py-2">
          {exportError}
        </div>
      )}
    </div>
  )
}
