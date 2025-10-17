import Skeleton from '../ui/Skeleton'

type QuestionCardProps = {
  question: string
  loading: boolean
}

export default function QuestionCard({ question, loading }: QuestionCardProps) {
  return (
    <div className="rounded-md border border-slate-200 bg-white p-4 min-h-24">
      {loading ? (
        <div className="space-y-2">
          <Skeleton className="h-4" />
          <Skeleton className="h-4 w-2/3" />
          <Skeleton className="h-4 w-1/3" />
        </div>
      ) : (
        <div className="whitespace-pre-wrap text-slate-900">{question}</div>
      )}
    </div>
  )
}


