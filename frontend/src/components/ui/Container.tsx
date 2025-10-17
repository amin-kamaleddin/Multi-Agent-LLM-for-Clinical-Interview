import type { ReactNode } from 'react'

export default function Container({ children }: { children: ReactNode }) {
  return (
    <div className="min-h-screen w-full bg-white">
      <div className="mx-auto max-w-3xl px-4 py-6 md:px-6 md:py-10">
        <div className="rounded-2xl border border-slate-100 bg-white/95 shadow-xl backdrop-blur-sm">
          <div className="p-6 md:p-8 space-y-4">
            {children}
          </div>
        </div>
      </div>
    </div>
  )
}



