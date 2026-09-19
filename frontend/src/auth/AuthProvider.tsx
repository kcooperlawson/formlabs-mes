import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { createContext, type ReactNode, useContext, useState } from 'react'
import { ApiError } from '../api/client'
import { authApi, type LoginRequest, type User } from '../api/auth'

interface AuthContextValue {
  user: User | null
  isLoading: boolean
  login: (body: LoginRequest) => Promise<void>
  loginError: string | null
  isLoggingIn: boolean
  logout: () => void
  /** True for the rest of this browser session's life after a real sign-in
   * (never after a page-reload session restore) - LoginRecap reads this
   * once to decide whether to show, then clears it, so it never asks
   * again until the next actual login. */
  justLoggedIn: boolean
  clearJustLoggedIn: () => void
}

const AuthContext = createContext<AuthContextValue | null>(null)

// GET /api/auth/me, once, on mount - this single query IS the entire
// session-restore mechanism (replaces Streamlit's check_authentication()
// and its cookie-round-trip dance). A 401 just means "not signed in", not
// an error worth retrying or surfacing.
export function AuthProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient()
  const [justLoggedIn, setJustLoggedIn] = useState(false)

  const meQuery = useQuery({
    queryKey: ['auth', 'me'],
    queryFn: authApi.me,
    retry: false,
  })

  const loginMutation = useMutation({
    mutationFn: authApi.login,
    onSuccess: (user) => {
      queryClient.setQueryData(['auth', 'me'], user)
      setJustLoggedIn(true)
    },
  })

  const logoutMutation = useMutation({
    mutationFn: authApi.logout,
    onSuccess: () => queryClient.setQueryData(['auth', 'me'], null),
  })

  const value: AuthContextValue = {
    user: meQuery.data ?? null,
    isLoading: meQuery.isLoading,
    login: async (body) => {
      await loginMutation.mutateAsync(body)
    },
    loginError:
      loginMutation.error instanceof ApiError ? loginMutation.error.message : null,
    isLoggingIn: loginMutation.isPending,
    logout: () => logoutMutation.mutate(),
    justLoggedIn,
    clearJustLoggedIn: () => setJustLoggedIn(false),
  }

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth() called outside <AuthProvider>')
  return ctx
}
