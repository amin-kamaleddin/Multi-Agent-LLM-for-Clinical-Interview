import Spinner from './Spinner'

export default function LoadingOverlay({ label }: { label: string }) {
  return (
    <div className="fixed inset-0 z-40 flex items-start justify-center p-6 pointer-events-none">
      <div className="w-full max-w-3xl">
        <div className="relative">
          <div className="absolute -top-4 left-1/2 -translate-x-1/2 flex items-center gap-2 rounded-full bg-white/95 px-4 py-2 shadow-md ring-1 ring-slate-200">
            <Spinner />
            <span className="text-sm text-slate-700">{label}</span>
          </div>
        </div>
      </div>
    </div>
  )
}



