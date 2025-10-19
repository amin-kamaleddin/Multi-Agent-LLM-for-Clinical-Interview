import { useState } from 'react'
import VoiceRecordControl from '../voice/VoiceRecordControl'
import { useElevenLabsRealtime } from '../../hooks/useElevenLabsRealtime'
import Spinner from '../ui/Spinner'

type AnswerFormProps = {
  responseType: string
  onSubmit: (answer: string) => void
  disabled: boolean
  isSubmitPending: boolean
  onVoiceStart?: () => void
  onVoiceEnd?: () => void
}

export default function AnswerForm({ responseType, onSubmit, disabled, isSubmitPending, onVoiceStart, onVoiceEnd }: AnswerFormProps) {
  const [answerInput, setAnswerInput] = useState('')
  const { start, stop, isRecording } = useElevenLabsRealtime({
    onFinal: (t) => setAnswerInput((prev) => (prev ? `${prev} ${t}` : t)),
  })

  const canShowQuickYesNo = !(responseType === 'descriptive' || responseType === 'quantity' || responseType === 'choice')

  return (
    <div className="space-y-3">
      {canShowQuickYesNo && (
        <div className="grid grid-cols-2 gap-2">
          <button onClick={() => !disabled && onSubmit('Yes')} className="rounded-md bg-slate-100 px-3 py-2 text-slate-900 transition hover:bg-slate-200 disabled:opacity-50 cursor-pointer" disabled={disabled}>
            Yes
          </button>
          <button onClick={() => !disabled && onSubmit('No')} className="rounded-md bg-slate-100 px-3 py-2 text-slate-900 transition hover:bg-slate-200 disabled:opacity-50 cursor-pointer" disabled={disabled}>
            No
          </button>
        </div>
      )}

      <textarea className="min-h-28 w-full rounded-md border border-slate-200 bg-white px-3 py-2 outline-none focus:border-emerald-400 disabled:bg-slate-50" disabled={disabled} value={answerInput} onChange={(e) => setAnswerInput(e.target.value)} placeholder="Your answer" />
      <VoiceRecordControl
        recording={isRecording}
        disabled={disabled}
        onStart={async () => {
          if (disabled) return
          try {
            await start()
            onVoiceStart?.()
          } catch {
            // no-op
          }
        }}
        onStop={async () => {
          try {
            await stop()
          } finally {
            onVoiceEnd?.()
          }
        }}
      />
      <div className="grid grid-cols-2 gap-2">
        <button onClick={() => setAnswerInput('')} className="rounded-md border border-slate-200 px-3 py-2 text-slate-900 disabled:opacity-50 cursor-pointer" disabled={disabled}>
          Cancel / Reset
        </button>
        <button onClick={() => answerInput.trim() && onSubmit(answerInput.trim())} className="flex items-center justify-center gap-2 rounded-md bg-emerald-600 px-3 py-2 font-medium text-white shadow-sm transition hover:bg-emerald-700 disabled:opacity-50 cursor-pointer" disabled={disabled || !answerInput.trim()}>
          {isSubmitPending && <Spinner className="h-4 w-4" />} Submit answer
        </button>
      </div>
    </div>
  )
}


