type Props = {
  recording: boolean
  disabled?: boolean
  onStart: () => void
  onStop: () => void
}

export default function VoiceRecordControl({ recording, disabled, onStart, onStop }: Props) {
  const handleClick = () => {
    if (recording) {
      onStop()
    } else if (!disabled) {
      onStart()
    }
  }

  return (
    <div className="w-full rounded-md border border-slate-200 bg-white p-3">
      <div className="flex items-center gap-3">
        <button
          onClick={handleClick}
          aria-pressed={recording}
          disabled={!recording && !!disabled}
          className={`rounded-full w-10 h-10 flex items-center justify-center text-white shadow-sm transition disabled:opacity-50 ${
            recording ? 'bg-red-600 hover:bg-red-700' : 'bg-slate-900 hover:bg-slate-800'
          }`}
          title={recording ? 'Stop recording' : 'Click to speak'}
        >
          {recording ? (
            <span>⏹</span>
          ) : (
            <span>🎙️</span>
          )}
        </button>
        <div className="flex-1">
          <div className="text-sm font-medium text-slate-800">
            {recording ? 'Recording… Click to stop' : 'Click to Speak'}
          </div>
          <div className="mt-2 h-2 w-full overflow-hidden rounded bg-slate-100">
            {recording ? (
              <div className="h-2 w-full animate-pulse bg-red-500" />
            ) : (
              <div className="h-2 w-0 bg-transparent" />
            )}
          </div>
        </div>
      </div>
    </div>
  )
}


