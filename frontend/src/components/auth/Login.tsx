/* eslint-disable @typescript-eslint/no-explicit-any */
import { useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { api } from '../../services/api'
import Container from '../ui/Container'

export default function Login({ onSuccess }: { onSuccess: () => void }) {
  const [password, setPassword] = useState('')
  const login = useMutation({
    mutationFn: (pwd: string) => api.login(pwd),
    onSuccess: () => onSuccess(),
  })

  return (
    <Container>
      <div className="space-y-4">
        <div className="space-y-1">
          <h1 className="text-2xl font-semibold tracking-tight text-slate-900">MINI Interview</h1>
          <p className="text-sm text-slate-600">Enter the application password to continue.</p>
        </div>

        <div className="space-y-2">
          <input
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            type="password"
            className="w-full rounded-md border border-slate-200 bg-white px-3 py-2 outline-none ring-0 focus:border-emerald-400"
            placeholder="Password"
          />
          <button
            onClick={() => login.mutate(password)}
            className="w-full rounded-md bg-emerald-600 px-3 py-2 font-medium text-white shadow-sm transition hover:bg-emerald-700 disabled:opacity-50"
            disabled={login.isPending}
          >
            {login.isPending ? 'Checking...' : 'Access Application'}
          </button>
          {login.isError && <p className="text-sm text-red-600">Invalid password or server error.</p>}
        </div>
      </div>
    </Container>
  )
}



