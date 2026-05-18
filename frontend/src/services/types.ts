export type ModuleInfo = {
  id: string
  name: string
  displayText: string
  path: string
}

export type CreateSessionRequest = {
  modulePath: string
  apiKey?: string
}

export type CreateSessionResponse = {
  threadId: string
  question: string
  responseType: string
  progress: number
  questionId: string
  moduleName: string
}

export type AnswerResponse = {
  classification: string
  reasoning: string
  redFlag: boolean
  redFlagMessage?: string
  redacted?: boolean
  originalResponse?: string
  redactedResponse?: string | null
}

export type NextResponse = {
  finished: boolean
  question?: string
  responseType?: string
  progress?: number
  questionId?: string
  moduleName?: string
  diagnosis?: Record<string, any>
}

