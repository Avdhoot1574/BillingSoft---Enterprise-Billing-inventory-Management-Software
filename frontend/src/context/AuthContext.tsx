import { createContext, useContext, useEffect, useState, ReactNode } from 'react'
import api, { User, CompanyBrief, CompanyDetail } from '@/api/index'

type AuthContextType = {
  user: User | null
  companies: CompanyBrief[]
  isAuthenticated: boolean
  loading: boolean
  login: (email: string, password: string) => Promise<void>
  register: (data: { email: string; password: string; full_name: string; phone?: string }) => Promise<void>
  logout: () => void
  refresh: (refreshToken: string) => Promise<void>
  selectedCompany: CompanyBrief | null
  selectCompany: (company: CompanyBrief) => void
  companyDetail: CompanyDetail | null
  permissions: string[]
  isOwner: boolean
}

const AuthContext = createContext<AuthContextType | undefined>(undefined)

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [companies, setCompanies] = useState<CompanyBrief[]>([])
  const [loading, setLoading] = useState(true)
  const [selectedCompany, setSelectedCompanyState] = useState<CompanyBrief | null>(null)
  const [companyDetail, setCompanyDetail] = useState<CompanyDetail | null>(null)
  const [permissions, setPermissions] = useState<string[]>([])
  const [isOwner, setIsOwner] = useState(false)

  useEffect(() => {
    const token = localStorage.getItem('access_token')
    if (token) {
      api
        .get('/auth/me')
        .then((res) => {
          const data = res.data as { user: User; companies: CompanyBrief[] }
          setUser(data.user)
          setCompanies(data.companies ?? [])
          const stored = localStorage.getItem('selected_company_id')
          if (stored && data.companies.some((c) => c.id === stored)) {
            const c = data.companies.find((c) => c.id === stored)!
            setSelectedCompanyState(c)
            loadCompanyDetail(c.id)
          } else if (data.companies.length > 0) {
            const c = data.companies[0]
            setSelectedCompanyState(c)
            localStorage.setItem('selected_company_id', c.id)
            loadCompanyDetail(c.id)
          }
        })
        .catch(() => {
          logout()
        })
        .finally(() => setLoading(false))
    } else {
      setLoading(false)
    }
  }, [])

  const loadCompanyDetail = async (_companyId: string) => {
    try {
      const res = await api.get(`/companies/current`)
      const data = res.data as CompanyDetail
      setCompanyDetail(data)
      setPermissions(data.permissions ?? [])
      setIsOwner(!!data.is_owner)
    } catch (e) {
      setPermissions([])
      setIsOwner(false)
    }
  }

  const login = async (email: string, password: string) => {
    const res = await api.post('/auth/login', { email, password })
    const data = res.data as { access_token: string; refresh_token: string }
    localStorage.setItem('access_token', data.access_token)
    localStorage.setItem('refresh_token', data.refresh_token)
    const me = await api.get('/auth/me')
    const meData = me.data as { user: User; companies: CompanyBrief[] }
    setUser(meData.user)
    setCompanies(meData.companies ?? [])
    if (meData.companies.length > 0) {
      const c = meData.companies[0]
      setSelectedCompanyState(c)
      localStorage.setItem('selected_company_id', c.id)
      await loadCompanyDetail(c.id)
    }
  }

  const register = async (data: { email: string; password: string; full_name: string; phone?: string }) => {
    await api.post('/auth/register', data)
  }

  const refresh = async (refreshToken: string) => {
    const res = await api.post('/auth/refresh', { refresh_token: refreshToken })
    const data = res.data as { access_token: string; refresh_token: string }
    localStorage.setItem('access_token', data.access_token)
    localStorage.setItem('refresh_token', data.refresh_token)
  }

  const logout = () => {
    localStorage.removeItem('access_token')
    localStorage.removeItem('refresh_token')
    localStorage.removeItem('selected_company_id')
    setUser(null)
    setCompanies([])
    setSelectedCompanyState(null)
    setCompanyDetail(null)
    setPermissions([])
    setIsOwner(false)
    window.location.href = '/login'
  }

  const selectCompany = async (company: CompanyBrief) => {
    setSelectedCompanyState(company)
    localStorage.setItem('selected_company_id', company.id)
    await loadCompanyDetail(company.id)
  }

  return (
    <AuthContext.Provider value={{ user, companies, isAuthenticated: !!user, loading, login, register, logout, refresh, selectedCompany, selectCompany, companyDetail, permissions, isOwner }}>
      {children}
    </AuthContext.Provider>
  )
}



