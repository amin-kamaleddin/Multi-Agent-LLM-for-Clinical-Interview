type ProgressHeaderProps = {
  moduleName: string
  questionId: string
  progress: number
}

export default function ProgressHeader({ moduleName, questionId, progress }: ProgressHeaderProps) {
  return (
    <div>
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-slate-900">MINI Interview</h1>
          <div className="text-sm text-slate-600">Module: {moduleName} • QID: {questionId}</div>
        </div>
        <div className="text-sm font-medium text-slate-900">{Math.round(progress * 100)}%</div>
      </div>

      <div className="mt-2" aria-label="Progress bar">
        <div className="h-2 w-full rounded-full bg-slate-200">
          <div className="h-2 rounded-full bg-emerald-600 transition-all" style={{ width: `${Math.round(progress * 100)}%` }} />
        </div>
        <div className="sr-only">Progress: {Math.round(progress * 100)}%</div>
      </div>
    </div>
  )
}


