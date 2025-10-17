import type { ModuleInfo } from '../../services/types'

type SidebarProps = {
  open: boolean
  modules?: ModuleInfo[]
  selected: ModuleInfo | null
  onSelect: (m: ModuleInfo | null) => void
  isLoading: boolean
  isError: boolean
  onStartReset: () => void
  onCollapse: () => void
}

export default function Sidebar({ open, modules, selected, onSelect, isLoading, isError, onStartReset, onCollapse }: SidebarProps) {
  return (
    <div className={`${open ? 'translate-x-0' : '-translate-x-full'} fixed left-0 top-0 z-10 flex h-screen w-80 transform flex-col justify-between border-r border-slate-200 bg-white p-4 transition-transform duration-300`}>
      <button aria-label="Collapse sidebar" title="Collapse sidebar" onClick={onCollapse} className="absolute right-4 top-4 inline-flex h-9 w-9 items-center justify-center rounded-md border border-slate-200 bg-white text-slate-700 shadow-sm hover:bg-slate-50">
        <svg viewBox="0 0 24 24" className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          <path d="m15 18-6-6 6-6" />
        </svg>
      </button>
      <div className="space-y-4">
        <div className="flex items-center justify-between text-slate-900">
          <h2 className="text-lg font-semibold">Setup</h2>
        </div>

        <div className="space-y-2">
          <label className="text-sm font-medium text-slate-700">Select module</label>
          <div className="relative">
            <select className="w-full appearance-none rounded-md border border-slate-200 bg-white px-3 pr-9 py-2 text-sm text-slate-900 outline-none focus:border-emerald-400" disabled={isLoading || isError || !modules} value={selected?.path || ''} onChange={(e) => onSelect(modules?.find((x) => x.path === e.target.value) || null)}>
              {modules?.map((m) => (
                <option key={m.path} value={m.path}>
                  {m.displayText}
                </option>
              ))}
            </select>
            <svg className="pointer-events-none absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-500" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              <path d="m6 9 6 6 6-6" />
            </svg>
          </div>
        </div>

        <button onClick={onStartReset} className="w-full rounded-md bg-red-500 px-3 py-2 text-white shadow-sm transition hover:bg-red-600 disabled:opacity-50 cursor-pointer" disabled={!selected}>
          Start / Reset Interview
        </button>
      </div>

      <div className="text-xs text-slate-500">
        Give feedback: <a className="underline" href="https://docs.google.com/forms/d/1kwnEcoh_XnVidUVthPu66d3Wr2w8beN3ywQ8NvkLmMQ/edit" target="_blank" rel="noreferrer">Feedback Form</a>
      </div>
    </div>
  )
}


