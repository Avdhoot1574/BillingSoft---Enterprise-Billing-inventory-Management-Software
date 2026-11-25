import { useEffect, useState } from 'react'
import { useAuth } from '@/context/AuthContext'
import api from '@/api/index'
import { Save, Loader2, Edit2, Building, Mail, Phone, MapPin, CreditCard, Calendar, Hash } from 'lucide-react'

export default function CompanySettings() {
  const { companyDetail, isOwner, permissions, refreshCompanies } = useAuth()
  const [editing, setEditing] = useState(false)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')
  const [form, setForm] = useState<any>({
    name: '', legal_name: '', gstin: '', pan: '', email: '', phone: '',
    address_line1: '', address_line2: '', city: '', district: '', state_code: '',
    postal_code: '', financial_year_start_month: 4,
  })

  useEffect(() => {
    if (companyDetail) {
      setForm({
        name: companyDetail.name, legal_name: companyDetail.legal_name ?? '', gstin: companyDetail.gstin ?? '',
        pan: companyDetail.pan ?? '', email: companyDetail.email ?? '', phone: companyDetail.phone ?? '',
        address_line1: companyDetail.address_line1 ?? '', address_line2: companyDetail.address_line2 ?? '',
        city: companyDetail.city ?? '', district: companyDetail.district ?? '', state_code: companyDetail.state_code ?? '',
        postal_code: companyDetail.postal_code ?? '', financial_year_start_month: companyDetail.financial_year_start_month,
      })
    }
  }, [companyDetail])

  const save = async () => {
    setError('')
    setSaving(true)
    try {
      await api.patch('/companies/current', {
        name: form.name, legal_name: form.legal_name || null, gstin: form.gstin || null,
        pan: form.pan || null, email: form.email || null, phone: form.phone || null,
        address_line1: form.address_line1 || null, address_line2: form.address_line2 || null,
        city: form.city || null, district: form.district || null, state_code: form.state_code || null,
        postal_code: form.postal_code || null, financial_year_start_month: Number(form.financial_year_start_month) || 4,
      })
      setSuccess('Company updated successfully')
      setSaving(false)
      setEditing(false)
      await refreshCompanies()
    } catch (e: any) {
      setError(e.message || 'Update failed')
      setSaving(false)
    }
  }

  return (
    <div className="p-6">
      <div className="flex flex-col md:flex-row md:items-center justify-between mb-6 gap-3">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Company Settings</h1>
          <p className="text-gray-500">Manage your company profile and billing details.</p>
        </div>
        <div className="flex gap-2">
          {!editing && (
            <button onClick={() => setEditing(true)} className="btn-outline flex items-center gap-2">
              <Edit2 className="w-4 h-4" /> Edit details
            </button>
          )}
        </div>
      </div>

      {error && <div className="mb-4 rounded-md bg-red-50 p-3 text-sm text-red-700 border border-red-100">{error}</div>}
      {success && <div className="mb-4 rounded-md bg-green-50 p-3 text-sm text-green-700 border border-green-100">{success}</div>}

      <div className="card">
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          <div className="col-span-1 md:col-span-2">
            <h3 className="text-sm font-semibold text-gray-700 uppercase tracking-wider mb-4">Company profile</h3>
            {editing ? (
              <form onSubmit={(e) => { e.preventDefault(); save() }} className="space-y-3">
                <div>
                  <label className="label">Company name *</label>
                  <input className="input" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} required />
                </div>
                <div>
                  <label className="label">Legal name</label>
                  <input className="input" value={form.legal_name} onChange={(e) => setForm({ ...form, legal_name: e.target.value })} />
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="label">GSTIN</label>
                    <input className="input" maxLength={15} value={form.gstin} onChange={(e) => setForm({ ...form, gstin: e.target.value.toUpperCase() })} />
                  </div>
                  <div>
                    <label className="label">PAN</label>
                    <input className="input" maxLength={10} value={form.pan} onChange={(e) => setForm({ ...form, pan: e.target.value.toUpperCase() })} />
                  </div>
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="label">Email</label>
                    <input className="input" type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} />
                  </div>
                  <div>
                    <label className="label">Phone</label>
                    <input className="input" value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })} />
                  </div>
                </div>
                <div>
                  <label className="label">Address line 1</label>
                  <input className="input" value={form.address_line1} onChange={(e) => setForm({ ...form, address_line1: e.target.value })} />
                </div>
                <div>
                  <label className="label">Address line 2</label>
                  <input className="input" value={form.address_line2} onChange={(e) => setForm({ ...form, address_line2: e.target.value })} />
                </div>
                <div className="grid grid-cols-3 gap-3">
                  <div>
                    <label className="label">City</label>
                    <input className="input" value={form.city} onChange={(e) => setForm({ ...form, city: e.target.value })} />
                  </div>
                  <div>
                    <label className="label">District</label>
                    <input className="input" value={form.district} onChange={(e) => setForm({ ...form, district: e.target.value })} />
                  </div>
                  <div>
                    <label className="label">State code</label>
                    <input className="input" maxLength={2} value={form.state_code} onChange={(e) => setForm({ ...form, state_code: e.target.value.toUpperCase() })} />
                  </div>
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="label">Postal code</label>
                    <input className="input" value={form.postal_code} onChange={(e) => setForm({ ...form, postal_code: e.target.value })} />
                  </div>
                  <div>
                    <label className="label">Financial year start month</label>
                    <input className="input" type="number" min="1" max="12" value={form.financial_year_start_month} onChange={(e) => setForm({ ...form, financial_year_start_month: e.target.value })} />
                  </div>
                </div>
                <div className="flex justify-end gap-2 pt-3">
                  <button type="button" onClick={() => setEditing(false)} className="btn-secondary">Cancel</button>
                  <button type="submit" className="btn-primary" disabled={saving}>{saving ? <Loader2 className="w-4 h-4" /> : <Save className="w-4 h-4" />} Save</button>
                </div>
              </form>
            ) : (
              <div className="space-y-3">
                <div className="flex items-center gap-2"><Building className="w-5 h-5 text-gray-400" /><span className="font-medium">{companyDetail?.name || form.name}</span></div>
                {companyDetail?.legal_name && <div className="flex items-center gap-2"><Hash className="w-5 h-5 text-gray-400" /><span className="text-gray-600 text-sm">{companyDetail.legal_name}</span></div>}
                {companyDetail?.gstin && <div className="flex items-center gap-2"><CreditCard className="w-5 h-5 text-gray-400" /><span className="text-gray-600 text-sm">{companyDetail.gstin}</span></div>}
                {companyDetail?.pan && <div className="flex items-center gap-2"><Hash className="w-5 h-5 text-gray-400" /><span className="text-gray-600 text-sm">{companyDetail.pan}</span></div>}
                {companyDetail?.email && <div className="flex items-center gap-2"><Mail className="w-5 h-5 text-gray-400" /><span className="text-gray-600 text-sm">{companyDetail.email}</span></div>}
                {companyDetail?.phone && <div className="flex items-center gap-2"><Phone className="w-5 h-5 text-gray-400" /><span className="text-gray-600 text-sm">{companyDetail.phone}</span></div>}
                <div className="flex items-center gap-2"><MapPin className="w-5 h-5 text-gray-400" /><span className="text-gray-600 text-sm max-w-xs truncate">{[companyDetail?.address_line1, companyDetail?.city, companyDetail?.state_code, companyDetail?.postal_code].filter(Boolean).join(', ') || '—'}</span></div>
                <div className="flex items-center gap-2"><Calendar className="w-5 h-5 text-gray-400" /><span className="text-gray-600 text-sm">Financial year starts: month {companyDetail?.financial_year_start_month ?? form.financial_year_start_month}</span></div>
              </div>
            )}
          </div>

          <div>
            <h3 className="text-sm font-semibold text-gray-700 uppercase tracking-wider mb-4">Your access</h3>
            <div className="space-y-3">
              <div className="flex items-center gap-2 p-2 rounded bg-gray-50 border border-gray-100">
                <Building className="w-4 h-4 text-gray-400" />
                <span className="text-sm text-gray-700">You are {isOwner ? 'the owner (admin)' : 'a member'} of this company</span>
              </div>
              <div className="flex items-center gap-2 p-2 rounded bg-gray-50 border border-gray-100">
                <Hash className="w-4 h-4 text-gray-400" />
                <span className="text-sm text-gray-700">Company ID: {companyDetail?.id}</span>
              </div>
              <div className="flex items-center gap-2 p-2 rounded bg-gray-50 border border-gray-100">
                <Mail className="w-4 h-4 text-gray-400" />
                <span className="text-sm text-gray-700">Currency: {companyDetail?.currency_code || 'INR'}</span>
              </div>
              <div className="flex items-center gap-2 p-2 rounded bg-gray-50 border border-gray-100">
                <Calendar className="w-4 h-4 text-gray-400" />
                <span className="text-sm text-gray-700">Country: {companyDetail?.country_code || 'IN'}</span>
              </div>
              <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mt-6 mb-2">Permissions ({permissions.length})</h3>
              <div className="flex flex-wrap gap-2">
                {permissions.map((p) => (
                  <span key={p} className="px-2 py-1 rounded text-xs bg-brand-50 text-brand-700 border border-brand-100">{p}</span>
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}



