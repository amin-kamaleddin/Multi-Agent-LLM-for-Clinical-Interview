import type { AnswerResponse } from '../../services/types'
import { BASE_URL } from '../../services/api'

type FinishedViewProps = {
  latest: AnswerResponse | null
  threadId: string
  diagnosis: Record<string, any> | null
}

export default function FinishedView({ latest, threadId, diagnosis }: FinishedViewProps) {
  if (latest?.redFlag) {
    return (
      <div className="space-y-3">
        <div className="rounded-lg border border-red-200 bg-red-50/70 p-4">
          <h2 className="text-xl font-semibold text-red-700">🚨 Crisis Alert</h2>
          <p className="mt-1 text-slate-800">If you are in immediate danger, call 911 or local emergency services.</p>
          <ul className="mt-2 list-disc pl-6 text-sm text-slate-800">
            <li>Emergency Services: 911</li>
            <li>National Suicide Prevention Lifeline: 988</li>
          </ul>
          <p className="mt-2 text-slate-800">The interview has been stopped for your safety.</p>
        </div>
        <a
          className="inline-block rounded-md bg-slate-800 px-3 py-2 text-white"
          href={`${BASE_URL}/sessions/${threadId}/log.csv`}
        >
          Download conversation log (CSV)
        </a>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="rounded-md border border-emerald-200 bg-emerald-50/70 p-3 text-emerald-800">Interview completed.</div>

      {diagnosis && (
        <div className="space-y-4">
          <h2 className="text-2xl font-bold tracking-tight text-slate-900">Diagnosis</h2>

          {(() => {
            const entries = Object.entries(diagnosis as any)
            const allMet = entries.every(([, d]: any) => Boolean(d?.diagnosis))
            const msg = allMet
              ? 'Meets all required criteria based on interview responses.'
              : 'Does not meet all required criteria based on interview responses.'
            return <div className="rounded-md border border-sky-200 bg-sky-50 p-3 text-sky-800">{msg}</div>
          })()}

          <div className="space-y-6">
            {Object.entries(diagnosis).map(([group, data]: any) => (
              <div key={group} className="space-y-3">
                <h3 className="text-xl font-semibold text-slate-900">{group}</h3>
                <ul className="list-disc space-y-1 pl-6 text-slate-900">
                  <li>
                    <span className="font-semibold">Result:</span> {data.diagnosis ? 'Met' : 'Not met'}
                  </li>
                  {data.timeFrame && (
                    <li>
                      <span className="font-semibold">Time frame:</span> {data.timeFrame}
                    </li>
                  )}
                </ul>
                <div className="space-y-2">
                  <div className="font-semibold text-slate-900">Reasoning:</div>
                  <p className="whitespace-pre-wrap text-slate-700">{data.reasoning}</p>
                </div>
                <hr className="border-slate-200" />
              </div>
            ))}
          </div>
        </div>
      )}

      <a
        className="inline-block rounded-md border border-slate-300 bg-white px-3 py-2 text-slate-800 shadow-sm hover:bg-slate-50"
        href={`${BASE_URL}/sessions/${threadId}/log.csv`}
      >
        Download conversation log (CSV)
      </a>
    </div>
  )
}


