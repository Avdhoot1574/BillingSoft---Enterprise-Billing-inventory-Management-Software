import { useEffect, useState } from 'react'
import { useAuth } from '@/context/AuthContext'
import api from '@/api/index'
import { formatMoney } from '@/lib/format'
import Modal from '@/components/common/Modal'
import { Plus, Search, Edit2, Save, Loader2 } from 'lucide-react'

export default function TaxRates() {
  const { permissions } = useAuth()
  const [items, setItems] = useState<any[]>([])
  const [search, setSearch] = useState('')
  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [open, setOpen] = useState(false)
  const [editing, setEditing] = useState(false)
  const [current, setCurrent] = useState<any>(null)
  const [form, setForm] = useState({ name: '', tax_type: 'gst', rate_percent: 0, cgst_percent: 0, sgst_percent: 0, igst_percent: 0, cess_percent: 0, is_active: true })
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')

  const canCreate = permissions.includes('items.create')
  const canUpdate = permissions.includes('items.update')

  useEffect(() => {
    load()
  }, [search])

  const load = async () => {
    setLoading(true)
    try {
      const res = await api.get('/tax-rates', { params: { search: search || undefined, limit: 100 } })
      setItems(res.data as any[])
    } catch (e: any) {
      setError(e.message || 'Failed to load tax rates')
    } finally {
      setLoading(false)
    }
  }

  const openCreate = () => {
    setEditing(false)
    setCurrent(null)
    setForm({ name: '', tax_type: 'gst', rate_percent: 0, cgst_percent: 0, sgst_percent: 0, igst_percent: 0, cess_percent: 0, is_active: true })
    setError('')
    setSuccess('')
    setOpen(true)
  }

  const openEdit = (item: any) => {
    setEditing(true)
    setCurrent(item)
    setForm({ ...item, is_active: item.is_active ?? true })
    setError('')
    setSuccess('')
    setOpen(true)
  }

  const save = async () => {
    setError('')
    setSaving(true)
    try {
      const payload = {
        name: form.name,
        tax_type: form.tax_type,
        rate_percent: Number(form.rate_percent) || 0,
        cgst_percent: Number(form.cgst_percent) || 0,
        sgst_percent: Number(form.sgst_percent) || 0,
        igst_percent: Number(form.igst_percent) || 0,
        cess_percent: Number(form.cess_percent) || 0,
        is_active: form.is_active,
      }
      if (editing && current) {
        await api.patch(`/tax-rates/${current.id}`, payload)
      } else {
        await api.post('/tax-rates', payload)
      }
      setSuccess('Saved successfully')
      setSaving(false)
      setOpen(false)
      load()
    } catch (e: any) {
      setError(e.message || 'Save failed')
      setSaving(false)
    }
  }

  return (
    <div className="p-6">
      <div className="flex flex-col md:flex-row md:items-center justify-between mb-6 gap-3">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Tax Rates</h1>
          <p className="text-gray-500">GST, cess and other tax rates applied to invoices.</p>
        </div>
        {canCreate && (
          <button onClick={openCreate} className="btn-primary flex items-center gap-2">
            <Plus className="w-4 h-4" /> Add Tax Rate
          </button>
        )}
      </div>

      <div className="card">
        <div className="overflow-x-auto">
          <table className="min-w-full">
            <thead>
              <tr>
                <th>Name</th>
                <th className="text-center">Type</th>
                <th className="text-right">Rate %</th>
                <th className="text-center">CGST</th>
                <th className="text-center">SGST</th>
                <th className="text-center">IGST</th>
                <th className="text-center">Cess</th>
                <th className="text-center">Active</th>
                <th className="text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr><td colSpan={9} className="p-4 text-center"><Loader2 className="w-5 h-5 animate-spin" /> Loading...</td></tr>
              ) : items.length === 0 ? (
                <tr><td colSpan={9} className="p-4 text-center text-gray-400">No tax rates found.</td></tr>
              ) : (
                items.map((t) => (
                  <tr key={t.id} className="border-b border-gray-100 hover:bg-gray-50">
                    <td className="font-medium">{t.name}</td>
                    <td className="text-center text-gray-600 capitalize">{t.tax_type}</td>
                    <td className="text-right font-medium">{formatMoney(t.rate_percent).replace('₹', '')}%</td>
                    <td className="text-center">{formatNumber(t.cgst_percent)}%</td>
                    <td className="text-center">{formatNumber(t.sgst_percent)}%</td>
                    <td className="text-center">{formatNumber(t.igst_percent)}%</td>
                    <td className="text-center">{formatNumber(t.cess_percent)}%</td>
                    <td className="text-center">{t.is_active ? 'Yes' : 'No'}</td>
                    <td className="text-right">
                      {permissions.includes('items.update') && (
                        <button onClick={() => openEdit(t)} className="text-brand-600 hover:underline text-sm mr-3">Edit</button>
                      )}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      <Modal open={open} onClose={() => setOpen(false)} title={editing ? 'Edit Tax Rate' : 'Create Tax Rate'}>
        {error && <div className="mb-3 rounded-md bg-red-50 p-2 text-sm text-red-700">{error}</div>}
        {success && <div className="mb-3 rounded-md bg-green-50 p-2 text-sm text-green-700">{success}</div>}
        <form onSubmit={(e) => { e.preventDefault(); save() }} className="space-y-3">
              <div>
                <label className="label">Tax rate name</label>
                <input className="input" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} required />
              </div>
              <div>
                <label className="label">Tax type</label>
                <select className="input" value={form.tax_type} onChange={(e) => setForm({ ...form, tax_type: e.target.value })}>
                  <option value="gst">GST</option>
                  <option value="cess">Cess</option>
                  <option value="other">Other</option>
                  <option value="exempt">Exempt</option>
                  <option value="nil_rated">Nil Rated</option>
                </select>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="label">Rate %</label>
                  <input className="input" type="number" step="0.01" value={form.rate_percent} onChange={(e) => setForm({ ...form, rate_percent: Number(e.target.value) || 0 })} />
                </div>
                <div>
                  <label className="label">CGST %</label>
                  <input className="input" type="number" step="0.01" value={form.cgst_percent} onChange={(e) => setForm({ ...form, cgst_percent: Number(e.target.value) || 0 })} />
                </div>
                <div>
                  <label className="label">SGST %</label>
                  <input className="input" type="number" step="0.01" value={form.sgst_percent} onChange={(e) => setForm({ ...form, sgst_percent: Number(e.target.value) || 0 })} />
                </div>
                <div>
                  <label className="label">IGST %</label>
                  <input className="input" type="number" step="0.01" value={form.igst_percent} onChange={(e) => setForm({ ...form, igst_percent: Number(e.target.value) || 0 })} />
                </div>
                <div>
                  <label className="label">Cess %</label>
                  <input className="input" type="number" step="0.01" value={form.cess_percent} onChange={(e) => setForm({ ...form, cess_percent: Number(e.target.value) || 0 })} />
                </div>
                <div className="flex items-end">
                  <label className="label">Active</label>
                  <input type="checkbox" checked={form.is_active} onChange={(e) => setForm({ ...form, is_active: e.target.checked })} className="ml-2" />
                </div>
              </div>
              <div className="flex justify-end gap-2 pt-2">
                <button type="button" onClick={() => setOpen(false)} className="btn-secondary">Cancel</button>
                <button type="submit" className="btn-primary" disabled={saving}>{saving ? <Loader2 className="w-4 h-4" /> : <Save className="w-4 h-4" />} {saving ? 'Saving...' : 'Save'}</button>
              </div>
            </form>
          </Modal>
    </div>
  )
}

function formatNumber(value: number | null | undefined, decimals = 2): string {
  const n = value ?? 0
  return new Intl.NumberFormat('en-IN', { minimumFractionDigits: decimals, maximumFractionDigits: decimals }).format(n)
}



