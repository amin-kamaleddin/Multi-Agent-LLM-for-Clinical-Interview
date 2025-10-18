/* eslint-disable @typescript-eslint/no-explicit-any */
import { useEffect, useMemo, useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import type { CreateSessionResponse, AnswerResponse } from '../../services/types'
import { api } from '../../services/api'
import Container from '../ui/Container'
import Spinner from '../ui/Spinner'
import Skeleton from '../ui/Skeleton'
import LoadingOverlay from '../ui/LoadingOverlay'
import ProgressHeader from './ProgressHeader'
import QuestionCard from './QuestionCard'
// SpeakButton replaced by AudioPlayControl
import AudioPlayControl from '../voice/AudioPlayControl'
import LatestResult from './LatestResult'
import AnswerForm from './AnswerForm'
import FinishedView from './FinishedView'

export default function Interview({ modulePath }: { modulePath: string }) {
  const [threadId, setThreadId] = useState<string | null>(null)
  const [question, setQuestion] = useState('')
  const [responseType, setResponseType] = useState('')
  const [questionId, setQuestionId] = useState('')
  const [moduleName, setModuleName] = useState('')
  const [progress, setProgress] = useState(0)
  const [latest, setLatest] = useState<AnswerResponse | null>(null)
  const [submittedAnswer, setSubmittedAnswer] = useState('')
  const [finished, setFinished] = useState(false)
  const [diagnosis, setDiagnosis] = useState<Record<string, any> | null>(null)
  const [uiLocked, setUiLocked] = useState(false)

  const createSession = useMutation({
    mutationFn: () => api.createSession({ modulePath }),
    onSuccess: (res: CreateSessionResponse) => {
      setThreadId(res.threadId)
      setQuestion(res.question)
      setResponseType(res.responseType)
      setQuestionId(res.questionId)
      setModuleName(res.moduleName)
      setProgress(res.progress)
      setLatest(null)
      setFinished(false)
      setDiagnosis(null)
    },
  })

  useEffect(() => {
    createSession.mutate()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [modulePath])

  const submit = useMutation({
    mutationFn: (payload: { threadId: string; answer: string }) => api.submitAnswer(payload.threadId, payload.answer),
    onSuccess: (res, vars: { threadId: string; answer: string }) => {
      setLatest(res)
      setSubmittedAnswer(vars?.answer || '')
    },
  })

  const goNext = useMutation({
    mutationFn: (tid: string) => api.goNext(tid),
    onSuccess: (res) => {
      if (res.finished) {
        setFinished(true)
        setDiagnosis(res.diagnosis ?? null)
      } else {
        setQuestion(res.question || '')
        setResponseType(res.responseType || '')
        setQuestionId(res.questionId || '')
        setProgress(res.progress || 0)
        setLatest(null)
      }
    },
  })

  const disabled = useMemo(() => submit.isPending || goNext.isPending || !threadId || uiLocked, [submit.isPending, goNext.isPending, threadId, uiLocked])
  const busyLabel = submit.isPending
    ? 'Evaluating your answer...'
    : goNext.isPending
    ? 'Preparing next question...'
    : ''

  if (createSession.isPending)
    return (
      <Container>
        <div className="flex items-center gap-3">
          <Spinner />
          <p className="text-slate-700">Preparing first question...</p>
        </div>
        <Skeleton className="h-24" />
        <Skeleton className="h-10" />
      </Container>
    )
  if (createSession.isError) return <Container><p className="text-red-600">Failed to start session.</p></Container>
  if (!threadId) return null

  if (finished) {
    return (
      <Container>
        <FinishedView latest={latest} threadId={threadId} diagnosis={diagnosis} />
      </Container>
    )
  }

  return (
    <Container>
      <ProgressHeader moduleName={moduleName} questionId={questionId} progress={progress} />

      <div className="space-y-3">
        <QuestionCard question={question} loading={goNext.isPending} />
        {question && (
          <AudioPlayControl text={question} uiLocked={uiLocked} onLock={() => setUiLocked(true)} onUnlock={() => setUiLocked(false)} label="Read question aloud" />
        )}
      </div>

      {latest ? (
        <div className="space-y-3">
          <LatestResult
            latest={latest}
            submittedAnswer={submittedAnswer}
            disabled={disabled}
            isSubmitPending={submit.isPending}
            isNextPending={goNext.isPending}
            onNext={() => threadId && goNext.mutate(threadId)}
            onCrisisContinue={() => setFinished(true)}
          />
        </div>
      ) : (
        <AnswerForm
          responseType={responseType}
          disabled={disabled || !threadId}
          isSubmitPending={submit.isPending}
          onSubmit={(answer) => threadId && submit.mutate({ threadId, answer })}
          onVoiceStart={() => setUiLocked(true)}
          onVoiceEnd={() => setUiLocked(false)}
        />
      )}

      {(submit.isPending || goNext.isPending) && <LoadingOverlay label={busyLabel} />}
    </Container>
  )
}



