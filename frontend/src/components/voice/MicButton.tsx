import React from 'react'

type Props = {
  recording: boolean
  onStart: () => void
  onStop: () => void
}

export default function MicButton({ recording, onStart, onStop }: Props) {
  const handleClick = () => {
    if (recording) onStop()
    else onStart()
  }

  return (
    <button
      onClick={handleClick}
      className={`rounded-md px-3 py-2 ${recording ? 'bg-red-600 text-white' : 'bg-slate-100 text-slate-900'} transition hover:opacity-90`}
      aria-pressed={recording}
    >
      {recording ? '⏹️ Stop Recording' : '🎤 Click to Speak'}
    </button>
  )
}


