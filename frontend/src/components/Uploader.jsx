import { useState, useRef, useCallback } from 'react'
import axios from 'axios'

const API_BASE = 'http://localhost:8000'

const ALLOWED_EXTENSIONS = ['.mp4', '.mp3', '.mov', '.webm']
const _ALLOWED_MIME_TYPES = [
  'video/mp4',
  'video/quicktime',
  'video/webm',
  'audio/mpeg',
  'audio/mp3',
]

function getExtension(filename) {
  const dot = filename.lastIndexOf('.')
  return dot !== -1 ? filename.slice(dot).toLowerCase() : ''
}

function formatSize(bytes) {
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

// ── Language option definitions ────────────────────────────────────────────
const SPOKEN_LANGUAGE_OPTIONS = [
  { value: 'auto', label: 'Auto Detect', description: 'Let Whisper detect the language automatically' },
  { value: 'en',   label: 'English',     description: null },
  { value: 'hi',   label: 'Hindi',       description: null },
  // TODO: Future Enhancement:
  // Support Hinglish transcription and subtitle generation while preserving
  // mixed-language speech and allowing optional translation.
]

const SUBTITLE_OUTPUT_OPTIONS = [
  { value: 'original', label: 'Original Language', description: 'Subtitles in the spoken language' },
  { value: 'en',       label: 'English',            description: 'Translate to English (Hindi only)' },
]

export default function Uploader({ onUploadSuccess }) {
  const [isDragOver, setIsDragOver] = useState(false)
  const [selectedFile, setSelectedFile] = useState(null)
  const [uploadState, setUploadState] = useState('idle') // idle | uploading | success | error
  const [progress, setProgress] = useState(0)
  const [errorMessage, setErrorMessage] = useState('')
  const [uploadResult, setUploadResult] = useState(null)
  const [spokenLanguage, setSpokenLanguage] = useState('auto')
  const [subtitleOutput, setSubtitleOutput] = useState('original')
  const inputRef = useRef(null)

  const resetState = () => {
    setSelectedFile(null)
    setUploadState('idle')
    setProgress(0)
    setErrorMessage('')
    setUploadResult(null)
    setSpokenLanguage('auto')
    setSubtitleOutput('original')
  }

  const validateFileLocally = (file) => {
    const ext = getExtension(file.name)
    if (!ALLOWED_EXTENSIONS.includes(ext)) {
      return `Unsupported file type "${ext}". Allowed: ${ALLOWED_EXTENSIONS.join(', ')}`
    }
    return null
  }

  const handleFile = useCallback((file) => {
    if (!file) return
    const err = validateFileLocally(file)
    if (err) {
      setErrorMessage(err)
      setUploadState('error')
      setSelectedFile(null)
      return
    }
    setErrorMessage('')
    setUploadState('idle')
    setSelectedFile(file)
  }, [])

  const handleDragOver = (e) => {
    e.preventDefault()
    setIsDragOver(true)
  }

  const handleDragLeave = (e) => {
    e.preventDefault()
    setIsDragOver(false)
  }

  const handleDrop = (e) => {
    e.preventDefault()
    setIsDragOver(false)
    const file = e.dataTransfer.files[0]
    handleFile(file)
  }

  const handleInputChange = (e) => {
    handleFile(e.target.files[0])
    // Reset input so the same file can be re-selected after an error
    e.target.value = ''
  }

  const handleUpload = async () => {
    if (!selectedFile) return

    const formData = new FormData()
    formData.append('file', selectedFile)
    formData.append('spoken_language', spokenLanguage)
    formData.append('subtitle_output', subtitleOutput)

    setUploadState('uploading')
    setProgress(0)
    setErrorMessage('')

    try {
      const response = await axios.post(`${API_BASE}/upload`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
        onUploadProgress: (evt) => {
          if (evt.total) {
            setProgress(Math.round((evt.loaded / evt.total) * 100))
          }
        },
      })

      setUploadResult(response.data)
      setUploadState('success')
      if (onUploadSuccess) {
        onUploadSuccess(response.data)
      }
    } catch (err) {
      const detail =
        err.response?.data?.detail ||
        err.message ||
        'Upload failed. Please try again.'
      setErrorMessage(detail)
      setUploadState('error')
    }
  }

  // When spoken language is English, force subtitle output back to original
  // (English → English translation is a no-op; keep UI consistent)
  const handleSpokenLanguageChange = (value) => {
    setSpokenLanguage(value)
    if (value === 'en') {
      setSubtitleOutput('original')
    }
  }

  // Determine whether the "English" subtitle output option should be available.
  // Translation is only meaningful when Hindi is selected or auto (may be Hindi).
  const canTranslate = spokenLanguage === 'hi' || spokenLanguage === 'auto'

  return (
    <div className="w-full max-w-lg bg-white rounded-2xl shadow-sm border border-gray-200 p-8">
      <h2 className="text-xl font-semibold text-gray-800 mb-1">Upload a video or audio file</h2>
      <p className="text-sm text-gray-400 mb-6">Supported formats: MP4, MP3, MOV, WEBM</p>

        {/* Drop zone */}
        <div
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
          onClick={() => uploadState !== 'uploading' && inputRef.current?.click()}
          className={[
            'relative flex flex-col items-center justify-center gap-3',
            'border-2 border-dashed rounded-xl py-12 px-6 cursor-pointer transition-colors',
            uploadState === 'uploading'
              ? 'cursor-default border-gray-300 bg-gray-50'
              : isDragOver
              ? 'border-blue-400 bg-blue-50'
              : 'border-gray-300 hover:border-blue-400 hover:bg-blue-50',
          ].join(' ')}
        >
          <input
            ref={inputRef}
            type="file"
            accept=".mp4,.mp3,.mov,.webm"
            className="hidden"
            onChange={handleInputChange}
            disabled={uploadState === 'uploading'}
          />

          {/* Icon */}
          <svg className="w-12 h-12 text-gray-300" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1}>
            <path strokeLinecap="round" strokeLinejoin="round"
              d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
          </svg>

          {selectedFile ? (
            <div className="text-center">
              <p className="text-sm font-medium text-gray-700">{selectedFile.name}</p>
              <p className="text-xs text-gray-400">{formatSize(selectedFile.size)}</p>
            </div>
          ) : (
            <div className="text-center">
              <p className="text-sm font-medium text-gray-600">
                Drag & drop your file here, or{' '}
                <span className="text-blue-500 font-semibold">browse</span>
              </p>
              <p className="text-xs text-gray-400 mt-1">Max file size: set by server config</p>
            </div>
          )}
        </div>

        {/* ── Spoken Language ──────────────────────────────────────────── */}
        <div className="mt-5">
          <p className="text-sm font-medium text-gray-700 mb-2">Spoken Language</p>
          <div className="flex flex-col gap-2">
            {SPOKEN_LANGUAGE_OPTIONS.map((opt) => (
              <label
                key={opt.value}
                className={[
                  'flex items-start gap-3 rounded-lg border px-3 py-2.5 cursor-pointer transition-colors',
                  spokenLanguage === opt.value
                    ? 'border-blue-400 bg-blue-50'
                    : 'border-gray-200 hover:border-blue-200 hover:bg-gray-50',
                ].join(' ')}
              >
                <input
                  type="radio"
                  name="spoken_language"
                  value={opt.value}
                  checked={spokenLanguage === opt.value}
                  onChange={() => handleSpokenLanguageChange(opt.value)}
                  className="mt-0.5 accent-blue-600"
                />
                <div>
                  <span className="text-sm font-medium text-gray-800">{opt.label}</span>
                  {opt.description && (
                    <span className="ml-2 text-xs text-gray-400">{opt.description}</span>
                  )}
                </div>
              </label>
            ))}
          </div>
        </div>

        {/* ── Subtitle Output ──────────────────────────────────────────── */}
        <div className="mt-5">
          <p className="text-sm font-medium text-gray-700 mb-2">Subtitle Output</p>
          <div className="flex flex-col gap-2">
            {SUBTITLE_OUTPUT_OPTIONS.map((opt) => {
              const isDisabled = opt.value === 'en' && !canTranslate
              return (
                <label
                  key={opt.value}
                  className={[
                    'flex items-start gap-3 rounded-lg border px-3 py-2.5 transition-colors',
                    isDisabled
                      ? 'border-gray-100 bg-gray-50 cursor-not-allowed opacity-50'
                      : 'cursor-pointer ' + (
                          subtitleOutput === opt.value
                            ? 'border-blue-400 bg-blue-50'
                            : 'border-gray-200 hover:border-blue-200 hover:bg-gray-50'
                        ),
                  ].join(' ')}
                >
                  <input
                    type="radio"
                    name="subtitle_output"
                    value={opt.value}
                    checked={subtitleOutput === opt.value}
                    disabled={isDisabled}
                    onChange={() => !isDisabled && setSubtitleOutput(opt.value)}
                    className="mt-0.5 accent-blue-600"
                  />
                  <div>
                    <span className="text-sm font-medium text-gray-800">{opt.label}</span>
                    {opt.description && (
                      <span className="ml-2 text-xs text-gray-400">{opt.description}</span>
                    )}
                  </div>
                </label>
              )
            })}
          </div>
          {subtitleOutput === 'en' && spokenLanguage === 'auto' && (
            <p className="mt-2 text-xs text-amber-600 bg-amber-50 border border-amber-200 rounded px-3 py-1.5">
              Auto Detect + English output: translation will only run if the spoken language is detected as Hindi.
            </p>
          )}
        </div>

        {/* Progress bar */}
        {uploadState === 'uploading' && (
          <div className="mt-4">
            <div className="flex justify-between text-xs text-gray-500 mb-1">
              <span>Uploading…</span>
              <span>{progress}%</span>
            </div>
            <div className="w-full bg-gray-200 rounded-full h-2">
              <div
                className="bg-blue-500 h-2 rounded-full transition-all duration-200"
                style={{ width: `${progress}%` }}
              />
            </div>
          </div>
        )}

        {/* Error message */}
        {uploadState === 'error' && errorMessage && (
          <div className="mt-4 flex items-start gap-2 text-sm text-red-700 bg-red-50 border border-red-200 rounded-lg px-4 py-3">
            <svg className="w-4 h-4 mt-0.5 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
              <path fillRule="evenodd"
                d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7 4a1 1 0 11-2 0 1 1 0 012 0zm-1-9a1 1 0 00-1 1v4a1 1 0 102 0V6a1 1 0 00-1-1z"
                clipRule="evenodd" />
            </svg>
            <span>{errorMessage}</span>
          </div>
        )}

        {/* Success message */}
        {uploadState === 'success' && uploadResult && (
          <div className="mt-4 text-sm text-green-700 bg-green-50 border border-green-200 rounded-lg px-4 py-3">
            <div className="flex items-center gap-2 mb-1">
              <svg className="w-4 h-4 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
                <path fillRule="evenodd"
                  d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z"
                  clipRule="evenodd" />
              </svg>
              <span className="font-semibold">Upload successful</span>
            </div>
            <p className="text-xs text-green-600">
              <span className="font-medium">File:</span> {uploadResult.filename}
            </p>
            <p className="text-xs text-green-600">
              <span className="font-medium">Duration:</span> {uploadResult.duration_seconds.toFixed(2)}s
            </p>
            <p className="text-xs text-green-600 font-mono break-all">
              <span className="font-medium font-sans">Job ID:</span> {uploadResult.job_id}
            </p>
          </div>
        )}

        {/* Action buttons */}
        <div className="mt-6 flex gap-3">
          {uploadState !== 'success' ? (
            <button
              onClick={handleUpload}
              disabled={!selectedFile || uploadState === 'uploading'}
              className={[
                'flex-1 py-2.5 px-4 rounded-lg text-sm font-semibold transition-colors',
                !selectedFile || uploadState === 'uploading'
                  ? 'bg-gray-100 text-gray-400 cursor-not-allowed'
                  : 'bg-blue-600 text-white hover:bg-blue-700 active:bg-blue-800',
              ].join(' ')}
            >
              {uploadState === 'uploading' ? 'Uploading…' : 'Upload'}
            </button>
          ) : (
            <button
              onClick={resetState}
              className="flex-1 py-2.5 px-4 rounded-lg text-sm font-semibold bg-gray-100 text-gray-700 hover:bg-gray-200 transition-colors"
            >
              Upload another file
            </button>
          )}
      </div>
    </div>
  )
}
