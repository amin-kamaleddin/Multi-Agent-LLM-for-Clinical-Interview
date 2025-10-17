import { useState } from 'react'
import type { AnswerResponse } from '../../services/types'
import Skeleton from '../ui/Skeleton'
import Spinner from '../ui/Spinner'

type LatestResultProps = {
  latest: AnswerResponse
  submittedAnswer: string
  disabled: boolean
  isSubmitPending: boolean
  isNextPending: boolean
  onNext: () => void
  onCrisisContinue: () => void
}

export default function LatestResult({ latest, submittedAnswer, disabled, isSubmitPending, isNextPending, onNext, onCrisisContinue }: LatestResultProps) {
  const [analysisOpen, setAnalysisOpen] = useState(false)
  const [redactionOpen, setRedactionOpen] = useState(false)

  if (isSubmitPending) {
    return (
      <div className="space-y-2">
        <Skeleton className="h-16" />
      </div>
    )
  }

  if (latest.redFlag) {
    return (
      <div className="space-y-3">
        <div className="rounded-lg border border-red-200 bg-red-50/70 p-4">
          <h2 className="text-xl font-semibold text-red-700">Crisis Alert</h2>
          {latest.redFlagMessage && <div className="mt-1 text-sm text-red-700">{latest.redFlagMessage}</div>}
        </div>
        <button onClick={onCrisisContinue} className="w-full rounded-md bg-red-600 px-3 py-2 text-white disabled:opacity-50" disabled={disabled}>
          Continue to Crisis Resources
        </button>
      </div>
    )
  }

  const accepted = String(latest.classification || '').toLowerCase().includes('yes')

  return (
    <>
      <div className={`rounded-md border p-4 ${accepted ? 'border-emerald-200 bg-emerald-50/70' : 'border-amber-200 bg-amber-50/70'}`}>
        <div className={`flex items-center gap-2 font-semibold ${accepted ? 'text-emerald-700' : 'text-amber-700'}`}>
          <svg viewBox="0 0 24 24" className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <path d="M20 6 9 17l-5-5" />
          </svg>
          <span>
            Evaluator Decision: {String(latest.classification).toUpperCase()}
            {accepted && ' - Answer accepted'}
          </span>
        </div>
      </div>

      {latest.redacted && (
        <div className="rounded-md border border-amber-200 bg-amber-50/70 p-4 text-slate-900">
          <div className="font-semibold text-amber-800">Privacy Notice: Sensitive Information Detected</div>
          <div className="text-sm text-slate-700">We detected potentially sensitive information in your response. For your privacy, this information has been redacted before processing.</div>
          <div className="mt-3 overflow-hidden rounded-md border border-slate-200">
            <button className="flex w-full items-center justify-between gap-2 bg-white px-4 py-3 text-left text-slate-800" onClick={() => setRedactionOpen((v) => !v)}>
              <span className="font-medium">See what was redacted</span>
              <svg viewBox="0 0 24 24" className={`h-5 w-5 text-slate-600 transition-transform ${redactionOpen ? 'rotate-90' : ''}`} fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                <path d="m9 18 6-6-6-6" />
              </svg>
            </button>
            {redactionOpen && (
              <div className="border-t border-slate-200 bg-white px-4 py-4 text-sm text-slate-800 space-y-3">
                <div>
                  <div className="font-semibold">Original response:</div>
                  <div className="rounded-md bg-slate-50 p-3">{latest.originalResponse}</div>
                </div>
                <div>
                  <div className="font-semibold">Redacted version (used for processing):</div>
                  <div className="rounded-md bg-slate-50 p-3">{latest.redactedResponse}</div>
                </div>
                <div className="text-slate-600">Note: Only the redacted version is stored and processed by our system.</div>
              </div>
            )}
          </div>
        </div>
      )}

      <div className="overflow-hidden rounded-md border border-slate-200">
        <button className="flex w-full items-center justify-between gap-2 bg-white px-4 py-3 text-left text-slate-800" onClick={() => setAnalysisOpen((v) => !v)}>
          <div className="flex items-center gap-2">
            <span className="font-medium">See evaluator analysis</span>
          </div>
          <svg viewBox="0 0 24 24" className={`h-5 w-5 text-slate-600 transition-transform ${analysisOpen ? 'rotate-90' : ''}`} fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <path d="m9 18 6-6-6-6" />
          </svg>
        </button>
        {analysisOpen && (
          <div className="border-t border-slate-200 bg-white px-4 py-4 text-slate-800">
            {submittedAnswer && <div className="mb-3"><span className="font-semibold">Your answer:</span> "{submittedAnswer}"</div>}
            {latest.reasoning && (
              <div>
                <span className="font-semibold">Evaluator reasoning:</span> {latest.reasoning}
              </div>
            )}
          </div>
        )}
      </div>

      <button onClick={onNext} className="flex w-full items-center justify-center gap-2 rounded-md bg-emerald-600 px-3 py-2 font-medium text-white shadow-sm transition hover:bg-emerald-700 disabled:opacity-50" disabled={disabled}>
        {isNextPending && <Spinner className="h-4 w-4" />} Next Question
      </button>
    </>
  )
}


