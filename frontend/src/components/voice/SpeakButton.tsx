import { useEffect, useRef, useState } from 'react'
import { BASE_URL } from '../../services/api'

export default function SpeakButton({ text, uiLocked, onLock, onUnlock }: { text: string; uiLocked?: boolean; onLock?: () => void; onUnlock?: () => void }) {
  const [loading, setLoading] = useState(false)
  const [playing, setPlaying] = useState(false)
  const audioRef = useRef<HTMLAudioElement | null>(null)

  useEffect(() => {
    return () => {
      if (audioRef.current) {
        try {
          audioRef.current.pause()
          audioRef.current.currentTime = 0
          // Revoke object URL created in requestTTS
          URL.revokeObjectURL(audioRef.current.src)
        } catch {/* noop */}
      }
    }
  }, [])

  const handleClick = async () => {
    if (!text || loading) return
    // If already playing, stop
    if (playing && audioRef.current) {
      audioRef.current.pause()
      audioRef.current.currentTime = 0
      setPlaying(false)
      onUnlock?.()
      return
    }
    // If we have audio cached, just play
    if (audioRef.current) {
      await audioRef.current.play()
      setPlaying(true)
      onLock?.()
      return
    }
    // Else stream via URL for faster start
    setLoading(true)
    try {
      const audio = new Audio(`${BASE_URL}/api/voice/tts?` + new URLSearchParams({ text }))
      audioRef.current = audio
      audio.onended = () => setPlaying(false)
      await audio.play()
      setPlaying(true)
      onLock?.()
    } finally {
      setLoading(false)
    }
  }

  return (
    <button onClick={handleClick} disabled={!!uiLocked && !playing} className="rounded-md bg-slate-100 px-3 py-2 text-slate-900 transition hover:bg-slate-200 disabled:opacity-50">
      {loading ? 'Loading audio…' : playing ? '⏹️ Stop' : '🔊 Play'}
    </button>
  )
}


