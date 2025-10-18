import { useMemo } from 'react'

export default function LandingScreen() {
  const hint = useMemo(
    () => "Select a module in the sidebar and click 'Start / Reset Interview'.",
    []
  )
  return (
    <div className="space-y-6">
      <div className="space-y-2">
        <h1 className="text-3xl font-semibold tracking-tight text-slate-900">Structured Clinical Interview and Assessment</h1>
        <p className="text-slate-700">
        The structured clinical interview is traditionally administered by clinicians to assess patients and visitors to the clinic. With this platform, we are automating the interview and assessment process using an agentic AI system. The
          goal is to make the assessment process faster, more scalable, and easier to use, while maintaining clinical
          rigor and reliability.
        </p>
        <p className="text-sm text-slate-600">⚠️ This is currently a proof of concept and should not be considered a replacement for diagnosis or evaluation by a qualified human clinician.</p>
        <p className="text-sm text-slate-600">We strongly encourage users not to share personal or sensitive information on this platform.</p>
      </div>
      <div className="rounded-md border border-emerald-200 bg-emerald-50/70 p-4 text-slate-800">{hint}</div>
    </div>
  )
}


