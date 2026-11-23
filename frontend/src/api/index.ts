import axios, { AxiosError, InternalAxiosRequestConfig } from 'axios'

const API_BASE = import.meta.env.VITE_API_BASE ?? '/api/v1'

export type User = {
  id: string
  email: string
  full_name: string
  phone: string | null
}

export type CompanyBrief = {
  id: string
  tenant_id: string
  name: string
  gstin: string | null
  state_code: string | null
  is_owner: boolean
}

export type CompanyDetail = {
  id: string
  tenant_id: string
  name: string
  legal_name: string | null
  gstin: string | null
  pan: string | null
  email: string | null
  phone: string | null
  address_line1: string | null
  address_line2: string | null
  city: string | null
  district: string | null
  state_code: string | null
  postal_code: string | null
  country_code: string
  currency_code: string
  financial_year_start_month: number
  timezone: string
  is_owner: boolean
  permissions: string[]
}

export type Member = {
  membership_id: string
  user_id: string
  email: string
  full_name: string
  status: string
  is_owner: boolean
  roles: string[]
}

export type Role = {
  id: string
  name: string
  description: string | null
  is_system_role: boolean
}

export type PartyKind = 'customer' | 'supplier' | 'both'

export type PartyAddress = {
  id?: string
  address_type: 'billing' | 'shipping' | 'other'
  line1: string
  line2: string | null
  city: string | null
  district: string | null
  state_code: string | null
  state_name: string | null
  postal_code: string | null
  country_code: string
  is_default: boolean
}

export type Party = {
  id: string
  company_id: string
  code: string | null
  name: string
  legal_name: string | null
  kind: PartyKind
  gstin: string | null
  pan: string | null
  tax_registration_type: string
  email: string | null
  phone: string | null
  alternate_phone: string | null
  opening_balance: number
  opening_balance_side: string | null
  credit_limit: number | null
  payment_terms_days: number
  notes: string | null
  is_archived: boolean
  created_at: string
  updated_at: string
  addresses: PartyAddress[]
}

export type TaxRate = {
  id: string
  name: string
  tax_type: string
  rate_percent: number
  cgst_percent: number
  sgst_percent: number
  igst_percent: number
  cess_percent: number
  effective_from: string | null
  effective_to: string | null
  is_active: boolean
}

export type Unit = {
  id: string
  name: string
  abbreviation: string
  decimal_places: number
}

export type Category = {
  id: string
  name: string
  parent_id: string | null
}

export type Item = {
  id: string
  name: string
  unit_id: string
  category_id: string | null
  tax_rate_id: string | null
  sku: string | null
  description: string | null
  kind: string
  hsn_sac: string | null
  barcode: string | null
  sale_price: number
  purchase_price: number
  track_inventory: boolean
  is_archived: boolean
}

export type Warehouse = {
  id: string
  name: string
  code: string | null
  address: string | null
  is_default: boolean
  is_active: boolean
}

export type UnitConversion = {
  id: string
  from_unit_id: string
  to_unit_id: string
  factor: number
}

export type InvoiceLine = {
  id?: string
  item_id?: string | null
  item_name: string
  sku: string | null
  hsn_sac: string | null
  unit_name: string
  quantity: number
  unit_price: number
  discount_percent: number
  tax_rate_percent: number
  warehouse_id?: string | null
}

export type Invoice = {
  id: string
  invoice_number: string | null
  invoice_date: string
  due_date: string | null
  status: string
  payment_status: string
  customer_name_snapshot: string
  subtotal: number
  discount_total: number
  taxable_total: number
  cgst_total: number
  sgst_total: number
  igst_total: number
  cess_total: number
  other_charges: number
  grand_total: number
  paid_total: number
}

export type ApiError = {
  code: string
  message: string
  details: any
  request_id: string | null
}

class ApiErrorClass extends Error {
  status: number
  code: string
  details: any
  request_id: string | null
  constructor(status: number, code: string, message: string, details: any, request_id: string | null) {
    super(message)
    this.status = status
    this.code = code
    this.details = details
    this.request_id = request_id
    this.name = 'ApiError'
  }
}

const api = axios.create({
  baseURL: API_BASE,
  headers: {
    'Content-Type': 'application/json',
  },
})

api.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  const token = localStorage.getItem('access_token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  const companyId = localStorage.getItem('selected_company_id')
  if (companyId) {
    config.headers['X-Company-Id'] = companyId
  }
  return config
})

api.interceptors.response.use(
  (res) => res,
  (err: AxiosError<{ error: ApiError }>) => {
    if (err.response?.status === 401) {
      localStorage.removeItem('access_token')
      localStorage.removeItem('refresh_token')
      if (typeof window !== 'undefined' && window.location.pathname !== '/login') {
        window.location.href = '/login'
      }
    }
    const apiErr = err.response?.data?.error
    throw new ApiErrorClass(
      err.response?.status ?? 500,
      apiErr?.code ?? 'UNKNOWN_ERROR',
      apiErr?.message ?? err.message ?? 'An error occurred',
      apiErr?.details ?? null,
      apiErr?.request_id ?? null,
    )
  },
)

export { api, ApiErrorClass }
export default api
