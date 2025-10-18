import { useEffect, useRef, useState } from 'react'
import { BASE_URL } from '../../services/api'

type Props = {
  text: string
  uiLocked?: boolean
  onLock?: () => void
  onUnlock?: () => void
  label?: string
}

export default function AudioPlayControl({ text, uiLocked, onLock, onUnlock, label }: Props) {
  const [loading, setLoading] = useState(false)
  const [playing, setPlaying] = useState(false)
  const [progress, setProgress] = useState(0)
  const [indeterminate, setIndeterminate] = useState(false)
  const audioRef = useRef<HTMLAudioElement | null>(null)
  const rafRef = useRef<number | null>(null)

  useEffect(() => {
    return () => {
      if (rafRef.current) cancelAnimationFrame(rafRef.current)
      if (audioRef.current) {
        try {
          audioRef.current.pause()
          audioRef.current.currentTime = 0
          URL.revokeObjectURL(audioRef.current.src)
        } catch {
          // ignore cleanup errors
        }
      }
    }
  }, [])

  const tick = () => {
    const a = audioRef.current
    if (!a) return
    const dur = a.duration || 0
    const cur = a.currentTime || 0
    const finite = Number.isFinite(dur) && dur > 0
    setIndeterminate(!finite)
    if (finite) setProgress(Math.min(100, (cur / dur) * 100))
    if (!a.paused) rafRef.current = requestAnimationFrame(tick)
  }

  const stopPlayback = () => {
    if (audioRef.current) {
      audioRef.current.pause()
      audioRef.current.currentTime = 0
    }
    setPlaying(false)
    onUnlock?.()
  }

  const handleClick = async () => {
    if (!text || loading) return
    if (playing) {
      stopPlayback()
      return
    }
    // reuse audio if present
    if (audioRef.current) {
      await audioRef.current.play()
      setPlaying(true)
      onLock?.()
      rafRef.current = requestAnimationFrame(tick)
      return
    }
    setLoading(true)
    try {
      const audio = new Audio(`${BASE_URL}/api/voice/tts?` + new URLSearchParams({ text }))
      audioRef.current = audio
      audio.onended = () => stopPlayback()
      audio.onloadedmetadata = () => {
        const dur = audio.duration || 0
        const finite = Number.isFinite(dur) && dur > 0
        setIndeterminate(!finite)
      }
      audio.onplay = () => {
        setPlaying(true)
        onLock?.()
        rafRef.current = requestAnimationFrame(tick)
      }
      audio.onpause = () => setPlaying(false)
      await audio.play()
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="w-full rounded-md border border-slate-200 bg-white p-3">
      <div className="flex items-center gap-3">
        <button onClick={handleClick} disabled={!!uiLocked && !playing} className="rounded-full bg-slate-900 text-white w-9 h-9 flex items-center justify-center disabled:opacity-50">
          {loading ? (
            <span className="animate-pulse">···</span>
          ) : playing ? (
            <span>⏹</span>
          ) : (
            <span>▶</span>
          )}
        </button>
        <div className="flex-1">
          <div className="text-sm text-slate-700">{label || 'Audio playback'}</div>
          {indeterminate && playing ? (
            <div className="mt-2 h-2 w-full overflow-hidden rounded bg-slate-100">
              <div className="h-2 w-full animate-pulse bg-emerald-400" />
            </div>
          ) : (
            <div className="mt-2 h-2 w-full overflow-hidden rounded bg-slate-100">
              <div className="h-2 bg-emerald-500 transition-all" style={{ width: `${progress}%` }} />
            </div>
          )}
        </div>
      </div>
    </div>
  )
}


