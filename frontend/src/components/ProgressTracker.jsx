/**
 * ProgressTracker — multi-stage step indicator driven by SSE pct/stage.
 *
 * Stages in order:
 *   queued → extracting_audio → transcribing → processing_granite
 *   → composing_subtitles → ready
 */

const STAGES = [
  { key: 'upload_complete',    label: 'Upload Complete',      pctThreshold: 0   },
  { key: 'extracting_audio',   label: 'Extracting Audio',     pctThreshold: 10  },
  { key: 'transcribing',       label: 'Transcribing',         pctThreshold: 30  },
  { key: 'processing_granite', label: 'Processing Granite',   pctThreshold: 60  },
  { key: 'composing_subtitles',label: 'Composing Subtitles',  pctThreshold: 75  },
  { key: 'ready',              label: 'Ready',                pctThreshold: 100 },
]

function getStepStatus(stepPct, currentPct, stage) {
  if (stage === 'error') return 'error'
  if (currentPct > stepPct) return 'done'
  if (currentPct === stepPct) return 'active'
  return 'pending'
}

export default function ProgressTracker({ stage, pct, error }) {
  return (
    <div className="w-full max-w-2xl mx-auto px-4">
      {/* Progress bar */}
      <div className="w-full bg-gray-200 rounded-full h-2 mb-6">
        <div
          className={[
            'h-2 rounded-full transition-all duration-500',
            stage === 'error' ? 'bg-red-500' : 'bg-blue-600',
          ].join(' ')}
          style={{ width: `${pct}%` }}
        />
      </div>

      {/* Stage steps */}
      <div className="flex items-start justify-between">
        {STAGES.map((step, idx) => {
          const status = getStepStatus(step.pctThreshold, pct, stage)
          return (
            <div key={step.key} className="flex flex-col items-center flex-1">
              {/* Connector line (not before first item) */}
              <div className="relative flex items-center w-full justify-center">
                {idx > 0 && (
                  <div
                    className={[
                      'absolute right-1/2 top-1/2 -translate-y-1/2 h-0.5 w-full',
                      status === 'done' ? 'bg-blue-500' : 'bg-gray-300',
                    ].join(' ')}
                  />
                )}
                {/* Circle */}
                <div
                  className={[
                    'relative z-10 w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold border-2 transition-all',
                    status === 'done'
                      ? 'bg-blue-600 border-blue-600 text-white'
                      : status === 'active'
                      ? 'bg-white border-blue-600 text-blue-600 animate-pulse'
                      : status === 'error'
                      ? 'bg-red-500 border-red-500 text-white'
                      : 'bg-white border-gray-300 text-gray-400',
                  ].join(' ')}
                >
                  {status === 'done' ? '✓' : idx + 1}
                </div>
              </div>
              {/* Label */}
              <span
                className={[
                  'mt-1.5 text-center text-xs leading-tight',
                  status === 'done'
                    ? 'text-blue-600 font-medium'
                    : status === 'active'
                    ? 'text-blue-700 font-semibold'
                    : 'text-gray-400',
                ].join(' ')}
              >
                {step.label}
              </span>
            </div>
          )
        })}
      </div>

      {/* Error message */}
      {stage === 'error' && error && (
        <div className="mt-4 text-sm text-red-700 bg-red-50 border border-red-200 rounded-lg px-4 py-3">
          <span className="font-semibold">Pipeline error: </span>{error}
        </div>
      )}

      {/* Pct label while running */}
      {stage && stage !== 'ready' && stage !== 'error' && (
        <p className="mt-3 text-center text-sm text-gray-500">
          {pct}% complete — {stage.replace(/_/g, ' ')}…
        </p>
      )}
    </div>
  )
}
