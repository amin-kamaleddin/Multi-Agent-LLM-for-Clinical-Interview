import { useQuery } from '@tanstack/react-query'
import { api } from '../../services/api'
import type { ModuleInfo } from '../../services/types'
import Container from '../ui/Container'
import Skeleton from '../ui/Skeleton'

export default function ModulePicker({ onStart }: { onStart: (m: ModuleInfo) => void }) {
  const { data, isLoading, isError } = useQuery({
    queryKey: ['modules'],
    queryFn: api.listModules,
  })

  return (
    <Container>
      <div className="space-y-4">
        <div className="space-y-1">
          <h1 className="text-2xl font-semibold tracking-tight text-slate-900">Select Module</h1>
          <p className="text-sm text-slate-600">Choose the interview module to begin.</p>
        </div>

        {isLoading && (
          <div className="space-y-2" aria-busy>
            <Skeleton className="h-12" />
            <Skeleton className="h-12" />
            <Skeleton className="h-12" />
          </div>
        )}
        {isError && <p className="text-red-600">Failed to load modules.</p>}
        {data && (
          <div className="space-y-2">
            {data.map((m) => (
              <button
                key={m.path}
                onClick={() => onStart(m)}
                className="w-full rounded-lg border border-slate-200 bg-white px-3 py-3 text-left transition hover:bg-emerald-50/60"
              >
                <div className="font-medium text-slate-900">{m.displayText}</div>
                <div className="text-xs text-slate-500">{m.path}</div>
              </button>
            ))}
          </div>
        )}
      </div>
    </Container>
  )
}



