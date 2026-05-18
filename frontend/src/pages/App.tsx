import { useEffect, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import type { ModuleInfo } from '../services/types'
import { api } from '../services/api'
import Login from '../components/auth/Login'
import Interview from '../components/interview/Interview'
import Sidebar from '../components/app/Sidebar'
import LandingScreen from '../components/app/LandingScreen'

export default function App() {
  const [authed, setAuthed] = useState(false)
  const [selected, setSelected] = useState<ModuleInfo | null>(null)
  const [activeModule, setActiveModule] = useState<ModuleInfo | null>(null)
  const [sessionKey, setSessionKey] = useState(0)
  const [started, setStarted] = useState(false)
  const [sidebarOpen, setSidebarOpen] = useState(true)

  const { data: modules, isLoading, isError } = useQuery({
    queryKey: ['modules'],
    queryFn: api.listModules,
    enabled: authed,
  })

  useEffect(() => {
    if (modules && modules.length > 0 && !selected) {
      setSelected(modules[0])
    }
  }, [modules, selected])

  const onStartReset = () => {
    if (selected) {
      setActiveModule(selected)
      setStarted(true)
      setSessionKey((k) => k + 1)
    }
  }

  const sidebar = (
    <Sidebar
      open={sidebarOpen}
      modules={modules}
      selected={selected}
      onSelect={(m) => setSelected(m)}
      isLoading={isLoading}
      isError={isError}
      onStartReset={onStartReset}
      onCollapse={() => setSidebarOpen(false)}
    />
  )

  if (!authed) return <Login onSuccess={() => setAuthed(true)} />

  return (
    <div className="min-h-screen w-full bg-white">
      {sidebar}
      {!sidebarOpen && (
        <button
          aria-label="Expand sidebar"
          title="Expand sidebar"
          onClick={() => setSidebarOpen(true)}
          className="fixed left-4 top-4 z-20 inline-flex h-9 w-9 items-center justify-center rounded-md border border-slate-200 bg-white text-slate-700 shadow-sm transition-all duration-300 hover:bg-slate-50"
        >
          <svg viewBox="0 0 24 24" className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <path d="m9 18 6-6-6-6" />
          </svg>
        </button>
      )}
      <div className={`${sidebarOpen ? 'pl-80' : 'pl-6'} pr-6 py-6 transition-all duration-300 md:py-8 md:pr-8`}>
        {!started ? (
          <div className="mx-auto max-w-3xl">
            <LandingScreen />
          </div>
        ) : (
          activeModule && (
            <div className="mx-auto max-w-3xl">
              <Interview key={sessionKey} modulePath={activeModule.path} />
            </div>
          )
        )}
      </div>
    </div>
  )
}
