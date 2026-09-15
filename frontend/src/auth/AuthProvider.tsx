import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { createContext, type ReactNode, useContext } from 'react'
import { ApiError } from '../api/client'
import { authApi, type LoginRequest, type User } from '../api/auth'

interface AuthContextValue {
  user: User | null
  isLoading: boolean
  login: (body: LoginRequest) => Promise<void>
  loginError: string | null
  isLoggingIn: boolean
  logout: () => void
}

const AuthContext = createContext<AuthContextValue | null>(null)

// GET /api/auth/me, once, on mount - this single query IS the entire
// session-restore mechanism (replaces Streamlit's check_authentication()
// and its cookie-round-trip dance). A 401 just means "not signed in", not
// an error worth retrying or surfacing.
export function AuthProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient()

  const meQuery = useQuery({
    queryKey: ['auth', 'me'],
    queryFn: authApi.me,
    retry: false,
  })

  const loginMutation = useMutation({
    mutationFn: authApi.login,
    onSuccess: (user) => queryClient.setQueryData(['auth', 'me'], user),
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
  }

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth() called outside <AuthProvider>')
  return ctx
}
