import { createContext, useContext, useEffect, useRef, useState, ReactNode } from 'react'
import api, { User, CompanyBrief, CompanyDetail } from '@/api/index'

type CompanyCreate = {
  name: string
  legal_name?: string | null
  gstin?: string | null
  pan?: string | null
  email?: string | null
  phone?: string | null
  address_line1?: string | null
  city?: string | null
  state_code?: string | null
  postal_code?: string | null
  financial_year_start_month?: number
}

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
  selectCompany: (company: CompanyBrief) => Promise<void>
  createCompany: (data: CompanyCreate) => Promise<void>
  refreshCompanies: () => Promise<void>
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
  const companyRequest = useRef(0)

  const loadCompanyDetail = async (companyId: string) => {
    const request = ++companyRequest.current
    try {
      const res = await api.get<CompanyDetail>('/companies/current', { headers: { 'X-Company-Id': companyId } })
      if (request !== companyRequest.current) return
      setCompanyDetail(res.data)
      setPermissions(res.data.permissions ?? [])
      setIsOwner(!!res.data.is_owner)
    } catch {
      if (request !== companyRequest.current) return
      setCompanyDetail(null)
      setPermissions([])
      setIsOwner(false)
    }
  }

  const activateCompany = async (company: CompanyBrief | null) => {
    setSelectedCompanyState(company)
    setCompanyDetail(null)
    setPermissions([])
    setIsOwner(false)
    if (!company) {
      ++companyRequest.current
      localStorage.removeItem('selected_company_id')
      return
    }
    localStorage.setItem('selected_company_id', company.id)
    await loadCompanyDetail(company.id)
  }

  const applyMe = async (data: { user: User; companies: CompanyBrief[] }, preferredId?: string) => {
    const list = data.companies ?? []
    setUser(data.user)
    setCompanies(list)
    const chosen = list.find((c) => c.id === preferredId) ?? list[0] ?? null
    await activateCompany(chosen)
  }

  useEffect(() => {
    if (!localStorage.getItem('access_token')) {
      setLoading(false)
      return
    }
    api.get<{ user: User; companies: CompanyBrief[] }>('/auth/me')
      .then((res) => applyMe(res.data, localStorage.getItem('selected_company_id') ?? undefined))
      .catch(() => logout())
      .finally(() => setLoading(false))
  }, [])

  const login = async (email: string, password: string) => {
    const res = await api.post<{ access_token: string; refresh_token: string }>('/auth/login', { email, password })
    localStorage.setItem('access_token', res.data.access_token)
    localStorage.setItem('refresh_token', res.data.refresh_token)
    const me = await api.get<{ user: User; companies: CompanyBrief[] }>('/auth/me')
    await applyMe(me.data, localStorage.getItem('selected_company_id') ?? undefined)
  }

  const register = async (data: { email: string; password: string; full_name: string; phone?: string }) => {
    await api.post('/auth/register', data)
  }

  const refresh = async (refreshToken: string) => {
    const res = await api.post<{ access_token: string; refresh_token: string }>('/auth/refresh', { refresh_token: refreshToken })
    localStorage.setItem('access_token', res.data.access_token)
    localStorage.setItem('refresh_token', res.data.refresh_token)
  }

  const logout = () => {
    ++companyRequest.current
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
    if (!companies.some((c) => c.id === company.id)) return
    await activateCompany(company)
  }

  const createCompany = async (data: CompanyCreate) => {
    const res = await api.post<CompanyBrief>('/companies', data)
    setCompanies((current) => [...current, res.data])
    await activateCompany(res.data)
  }

  const refreshCompanies = async () => {
    const me = await api.get<{ user: User; companies: CompanyBrief[] }>('/auth/me')
    await applyMe(me.data, selectedCompany?.id)
  }

  return (
    <AuthContext.Provider value={{ user, companies, isAuthenticated: !!user, loading, login, register, logout, refresh, selectedCompany, selectCompany, createCompany, refreshCompanies, companyDetail, permissions, isOwner }}>
      {children}
    </AuthContext.Provider>
  )
}
