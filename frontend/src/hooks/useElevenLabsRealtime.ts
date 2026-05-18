import { useCallback, useRef, useState } from 'react'
import { postTranscription } from '../services/voice'

export function useElevenLabsRealtime(opts?: {
  onFinal?: (text: string) => void
}) {
  const mediaRecorderRef = useRef<MediaRecorder | null>(null)
  const chunksRef = useRef<BlobPart[]>([])
  const [isRecording, setIsRecording] = useState(false)

  const start = useCallback(async () => {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
    const mr = new MediaRecorder(stream, { mimeType: 'audio/webm' })
    mediaRecorderRef.current = mr
    chunksRef.current = []
    mr.ondataavailable = (e) => {
      if (e.data && e.data.size > 0) chunksRef.current.push(e.data)
    }
    mr.onstop = async () => {
      const blob = new Blob(chunksRef.current, { type: 'audio/webm' })
      try {
        const text = await postTranscription(blob)
        if (text) opts?.onFinal?.(text)
      } catch {
        // swallow; UI can show errors if needed
      } finally {
        chunksRef.current = []
      }
    }
    mr.start()
    setIsRecording(true)
  }, [])

  const stop = useCallback(() => {
    setIsRecording(false)
    mediaRecorderRef.current?.stop()
    mediaRecorderRef.current = null
  }, [])

  return { start, stop, isRecording }
}


