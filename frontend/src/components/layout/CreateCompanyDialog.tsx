import { useState } from 'react'
import { Building2, Loader2, X } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '@/context/AuthContext'

export default function CreateCompanyDialog({ onClose, required = false }: { onClose: () => void; required?: boolean }) {
  const { createCompany, logout } = useAuth()
  const navigate = useNavigate()
  const [form, setForm] = useState({ name: '', legal_name: '', gstin: '', pan: '', email: '', phone: '', address_line1: '', city: '', state_code: '', postal_code: '', financial_year_start_month: 4 })
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  const submit = async (event: React.FormEvent) => {
    event.preventDefault()
    setError('')
    setSaving(true)
    try {
      await createCompany({
        name: form.name.trim(), legal_name: form.legal_name.trim() || null,
        gstin: form.gstin.trim() || null, pan: form.pan.trim() || null,
        email: form.email.trim() || null, phone: form.phone.trim() || null,
        address_line1: form.address_line1.trim() || null, city: form.city.trim() || null,
        state_code: form.state_code.trim() || null, postal_code: form.postal_code.trim() || null,
        financial_year_start_month: Number(form.financial_year_start_month),
      })
      onClose()
      navigate('/dashboard')
    } catch (err: any) {
      setError(err.message || 'Could not create company')
    } finally {
      setSaving(false)
    }
  }

  const field = (key: keyof typeof form, label: string, options: { type?: string; maxLength?: number; placeholder?: string } = {}) => (
    <label className="block text-sm font-medium text-slate-700">
      {label}
      <input className="input mt-1" type={options.type ?? 'text'} maxLength={options.maxLength} placeholder={options.placeholder}
        value={form[key]} onChange={(event) => setForm({ ...form, [key]: key === 'gstin' || key === 'pan' ? event.target.value.toUpperCase() : event.target.value })}
        required={key === 'name'} min={key === 'financial_year_start_month' ? 1 : undefined} max={key === 'financial_year_start_month' ? 12 : undefined} />
    </label>
  )

  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center bg-slate-900/50 p-4" role="presentation">
      <div className="w-full max-w-xl max-h-[90vh] overflow-y-auto rounded-2xl bg-white p-6 shadow-2xl" role="dialog" aria-modal="true" aria-labelledby="create-company-title">
        <div className="flex items-start justify-between gap-4 mb-5">
          <div className="flex items-center gap-3">
            <span className="rounded-xl bg-brand-50 p-2 text-brand-600"><Building2 className="w-5 h-5" /></span>
            <div>
              <h2 id="create-company-title" className="text-xl font-bold text-slate-900">Create a company</h2>
              <p className="text-sm text-slate-500">Each company has its own invoices, items, members and settings.</p>
            </div>
          </div>
          {!required && <button type="button" onClick={onClose} aria-label="Close" className="text-slate-500 hover:text-slate-900"><X className="w-5 h-5" /></button>}
        </div>
        <form onSubmit={submit} className="space-y-4">
          {field('name', 'Company name *', { maxLength: 200 })}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {field('legal_name', 'Legal name', { maxLength: 200 })}
            {field('email', 'Company email', { type: 'email' })}
            {field('gstin', 'GSTIN', { maxLength: 15 })}
            {field('pan', 'PAN', { maxLength: 10 })}
            {field('phone', 'Phone')}
            {field('state_code', 'State code', { maxLength: 2, placeholder: 'e.g. 27' })}
            {field('city', 'City')}
            {field('postal_code', 'Postal code')}
          </div>
          {field('address_line1', 'Address')}
          {field('financial_year_start_month', 'Financial year start month', { type: 'number' })}
          {error && <p role="alert" className="rounded-lg bg-red-50 p-3 text-sm text-red-700">{error}</p>}
          <div className="flex justify-between items-center gap-3 pt-2">
            {required ? <button type="button" onClick={logout} className="text-sm text-slate-600 hover:underline">Sign out</button> : <button type="button" onClick={onClose} className="btn-secondary">Cancel</button>}
            <button type="submit" disabled={saving} className="btn-primary flex items-center gap-2">
              {saving && <Loader2 className="w-4 h-4 animate-spin" />} Create company
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
