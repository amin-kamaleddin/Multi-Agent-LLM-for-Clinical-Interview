import { BASE_URL } from './api'

export async function requestTTS(text: string, voiceId?: string): Promise<HTMLAudioElement> {
  const res = await fetch(`${BASE_URL}/api/voice/tts`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text, voiceId }),
  })
  if (!res.ok) throw new Error('TTS request failed')
  const blob = await res.blob()
  const url = URL.createObjectURL(blob)
  const audio = new Audio(url)
  return audio
}

export async function postTranscription(blob: Blob): Promise<string> {
  const fd = new FormData()
  fd.append('file', blob, 'audio.webm')
  const res = await fetch(`${BASE_URL}/api/voice/transcribe`, { method: 'POST', body: fd })
  if (!res.ok) throw new Error('Transcription failed')
  const data = await res.json()
  return String(data?.text || '')
}


