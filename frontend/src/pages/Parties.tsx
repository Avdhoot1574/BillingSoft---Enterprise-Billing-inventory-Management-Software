import { useEffect, useState } from 'react'
import { useAuth } from '@/context/AuthContext'
import api, { Party } from '@/api/index'
import { formatMoney, formatDate } from '@/lib/format'
import Modal from '@/components/common/Modal'
import { Plus, Search, Save, Loader2 } from 'lucide-react'

type PartyKind = 'customer' | 'supplier' | 'both'

const KIND_LABEL: Record<PartyKind, string> = { customer: 'Customer', supplier: 'Supplier', both: 'Both' }
const KIND_COLOR: Record<PartyKind, string> = { customer: 'bg-blue-100 text-blue-700', supplier: 'bg-amber-100 text-amber-700', both: 'bg-purple-100 text-purple-700' }

export default function Parties() {
  const { permissions } = useAuth()
  const [items, setItems] = useState<Party[]>([])
  const [search, setSearch] = useState('')
  const [kind, setKind] = useState<PartyKind | ''>('')
  const [archivedOnly, setArchivedOnly] = useState(false)
  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [open, setOpen] = useState(false)
  const [editing, setEditing] = useState(false)
  const [current, setCurrent] = useState<Party | null>(null)
  const [form, setForm] = useState<PartyForm>({
    code: '', name: '', legal_name: '', kind: 'customer', gstin: '', pan: '',
    tax_registration_type: 'unregistered', email: '', phone: '', alternate_phone: '',
    opening_balance: '0', opening_balance_side: 'none', credit_limit: '', payment_terms_days: 0,
    notes: '', addresses: [],
  })
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')

  const canCreate = permissions.includes('parties.create')
  const canUpdate = permissions.includes('parties.update')
  const canArchive = permissions.includes('parties.archive')

  useEffect(() => {
    load()
  }, [search, kind, archivedOnly])

  const load = async () => {
    setLoading(true)
    try {
      const res = await api.get('/parties', { params: { search: search || undefined, kind: kind || undefined, archived_only: archivedOnly, limit: 100 } })
      setItems(res.data as Party[])
    } catch (e: any) {
      setError(e.message || 'Failed to load parties')
    } finally {
      setLoading(false)
    }
  }

  const openCreate = () => {
    setEditing(false)
    setCurrent(null)
    setForm({ code: '', name: '', legal_name: '', kind: 'customer', gstin: '', pan: '', tax_registration_type: 'unregistered', email: '', phone: '', alternate_phone: '', opening_balance: '0', opening_balance_side: 'none', credit_limit: '', payment_terms_days: 0, notes: '', addresses: [] })
    setError('')
    setSuccess('')
    setOpen(true)
  }

  const openEdit = (item: Party) => {
    setEditing(true)
    setCurrent(item)
    setForm({
      code: item.code ?? '', name: item.name, legal_name: item.legal_name ?? '', kind: item.kind,
      gstin: item.gstin ?? '', pan: item.pan ?? '', tax_registration_type: item.tax_registration_type,
      email: item.email ?? '', phone: item.phone ?? '', alternate_phone: item.alternate_phone ?? '',
      opening_balance: String(item.opening_balance), opening_balance_side: (item.opening_balance_side ?? 'none') as 'receivable' | 'payable' | 'none',
      credit_limit: item.credit_limit ? String(item.credit_limit) : '', payment_terms_days: item.payment_terms_days,
      notes: item.notes ?? '', addresses: item.addresses.map((a) => ({
        address_type: a.address_type,
        line1: a.line1 ?? '',
        line2: a.line2 ?? '',
        city: a.city ?? '',
        district: a.district ?? '',
        state_code: a.state_code ?? '',
        state_name: a.state_name ?? '',
        postal_code: a.postal_code ?? '',
        country_code: a.country_code ?? 'IN',
        is_default: a.is_default,
        id: a.id ?? '',
      })),
    })
    setError('')
    setSuccess('')
    setOpen(true)
  }

  const save = async () => {
    setError('')
    setSaving(true)
    try {
      const payload: any = {
        name: form.name,
        legal_name: form.legal_name || null,
        kind: form.kind,
        gstin: form.gstin || null,
        pan: form.pan || null,
        tax_registration_type: form.tax_registration_type,
        email: form.email || null,
        phone: form.phone || null,
        alternate_phone: form.alternate_phone || null,
        opening_balance: Number(form.opening_balance) || 0,
        opening_balance_side: form.opening_balance_side,
        credit_limit: form.credit_limit ? Number(form.credit_limit) : null,
        payment_terms_days: form.payment_terms_days,
        notes: form.notes || null,
        addresses: form.addresses.filter((a) => a.line1).map((a) => ({
          address_type: a.address_type,
          line1: a.line1,
          line2: a.line2 || null,
          city: a.city || null,
          district: a.district || null,
          state_code: a.state_code || null,
          state_name: a.state_name || null,
          postal_code: a.postal_code || null,
          country_code: a.country_code || 'IN',
          is_default: a.is_default,
        })),
      }
      if (editing && current) {
        await api.patch(`/parties/${current.id}`, payload)
      } else {
        if (form.code) payload.code = form.code
        await api.post('/parties', payload)
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

  const archive = async (id: string) => {
    if (!window.confirm('Archive this party? Archived parties are hidden from lists.')) return
    try {
      await api.post(`/parties/${id}/archive`)
      load()
    } catch (e: any) {
      setError(e.message || 'Archive failed')
    }
  }

  const restore = async (id: string) => {
    try {
      setError('')
      await api.post(`/parties/${id}/restore`)
      await load()
    } catch (e: any) {
      setError(e.message || 'Restore failed')
    }
  }

  const addAddress = () => {
    setForm({ ...form, addresses: [...form.addresses, { address_type: 'billing', line1: '', line2: '', city: '', district: '', state_code: '', state_name: '', postal_code: '', country_code: 'IN', is_default: false }] })
  }

  return (
    <div className="p-6">
      <div className="flex flex-col md:flex-row md:items-center justify-between mb-6 gap-3">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Parties</h1>
          <p className="text-gray-500">Customers and suppliers.</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <select value={kind} onChange={(e) => setKind(e.target.value as PartyKind)} className="input text-xs border border-gray-300 rounded px-2 py-1.5">
            <option value="">All kinds</option>
            <option value="customer">Customer</option>
            <option value="supplier">Supplier</option>
            <option value="both">Both</option>
          </select>
          <div className="flex rounded-lg border border-gray-300 overflow-hidden text-sm">
            <button type="button" onClick={() => setArchivedOnly(false)} className={`px-3 py-1.5 ${!archivedOnly ? 'bg-brand-50 text-brand-700 font-semibold' : 'text-gray-600'}`}>Active</button>
            <button type="button" onClick={() => setArchivedOnly(true)} className={`px-3 py-1.5 ${archivedOnly ? 'bg-brand-50 text-brand-700 font-semibold' : 'text-gray-600'}`}>Archived</button>
          </div>
          {canCreate && (
            <button onClick={openCreate} className="btn-primary flex items-center gap-2">
              <Plus className="w-4 h-4" /> Add Party
            </button>
          )}
        </div>
      </div>

      {error && !open && <div className="mb-3 rounded-md bg-red-50 p-3 text-sm text-red-700" role="alert">{error}</div>}

      <div className="relative">
        <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
          <Search className="w-4 h-4 text-gray-400" />
        </div>
        <input
          className="input pl-9"
          placeholder="Search party name, phone, GSTIN..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
      </div>

      <div className="card mt-4">
        <div className="overflow-x-auto">
          <table className="min-w-full">
            <thead>
              <tr>
                <th>Name</th>
                <th className="text-center">Kind</th>
                <th>GSTIN / PAN</th>
                <th className="text-right">Phone</th>
                <th className="text-right">Balance</th>
                <th className="text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr><td colSpan={6} className="p-4 text-center"><Loader2 className="w-5 h-5 animate-spin" /> Loading...</td></tr>
              ) : items.length === 0 ? (
                <tr><td colSpan={6} className="p-4 text-center text-gray-400">No {archivedOnly ? 'archived ' : ''}parties found.</td></tr>
              ) : (
                items.map((p) => (
                  <tr key={p.id} className="border-b border-gray-100 hover:bg-gray-50">
                    <td className="font-medium">{p.name}</td>
                    <td className="text-center"><span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium ${KIND_COLOR[p.kind]}`}>{KIND_LABEL[p.kind]}</span></td>
                    <td className="text-gray-600 text-sm">{p.gstin ?? p.pan ?? '—'}</td>
                    <td className="text-right text-gray-600 text-sm">{p.phone ?? '—'}</td>
                    <td className="text-right font-medium">{formatMoney(p.opening_balance)}</td>
                    <td className="text-right">
                      {canUpdate && !p.is_archived && (
                        <button onClick={() => openEdit(p)} className="text-brand-600 hover:underline text-sm mr-3">Edit</button>
                      )}
                      {canArchive && !p.is_archived && (
                        <button onClick={() => archive(p.id)} className="text-red-600 hover:underline text-sm">Archive</button>
                      )}
                      {canArchive && p.is_archived && (
                        <button onClick={() => restore(p.id)} className="text-brand-600 hover:underline text-sm">Restore</button>
                      )}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      <Modal open={open} onClose={() => setOpen(false)} title={editing ? 'Edit Party' : 'Create Party'}>
        {error && <div className="mb-3 rounded-md bg-red-50 p-2 text-sm text-red-700">{error}</div>}
        {success && <div className="mb-3 rounded-md bg-green-50 p-2 text-sm text-green-700">{success}</div>}
        <form onSubmit={(e) => { e.preventDefault(); save() }} className="space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className="label">Party code (optional)</label>
                  <input className="input" value={form.code} onChange={(e) => setForm({ ...form, code: e.target.value })} />
                </div>
                <div>
                  <label className="label">Party name *</label>
                  <input className="input" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} required />
                </div>
                <div>
                  <label className="label">Legal name</label>
                  <input className="input" value={form.legal_name} onChange={(e) => setForm({ ...form, legal_name: e.target.value })} />
                </div>
                <div>
                  <label className="label">Kind *</label>
                  <select className="input" value={form.kind} onChange={(e) => setForm({ ...form, kind: e.target.value as PartyKind })}>
                    <option value="customer">Customer</option>
                    <option value="supplier">Supplier</option>
                    <option value="both">Both</option>
                  </select>
                </div>
                <div>
                  <label className="label">GSTIN</label>
                  <input className="input" value={form.gstin} onChange={(e) => setForm({ ...form, gstin: e.target.value.toUpperCase() })} />
                </div>
                <div>
                  <label className="label">PAN</label>
                  <input className="input" value={form.pan} onChange={(e) => setForm({ ...form, pan: e.target.value.toUpperCase() })} />
                </div>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div>
                  <label className="label">Email</label>
                  <input className="input" type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} />
                </div>
                <div>
                  <label className="label">Phone</label>
                  <input className="input" value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })} />
                </div>
                <div>
                  <label className="label">Alternate phone</label>
                  <input className="input" value={form.alternate_phone} onChange={(e) => setForm({ ...form, alternate_phone: e.target.value })} />
                </div>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div>
                  <label className="label">Opening balance</label>
                  <input className="input" type="number" step="0.0001" value={form.opening_balance} onChange={(e) => setForm({ ...form, opening_balance: e.target.value })} />
                </div>
                <div>
                  <label className="label">Balance side</label>
                  <select className="input" value={form.opening_balance_side} onChange={(e) => setForm({ ...form, opening_balance_side: e.target.value as 'receivable' | 'payable' | 'none' })}>
                    <option value="none">None</option>
                    <option value="receivable">Receivable</option>
                    <option value="payable">Payable</option>
                  </select>
                </div>
                <div>
                  <label className="label">Credit limit</label>
                  <input className="input" type="number" step="0.01" value={form.credit_limit} onChange={(e) => setForm({ ...form, credit_limit: e.target.value })} />
                </div>
              </div>
              <div>
                <label className="label">Payment terms (days)</label>
                <input className="input" type="number" value={form.payment_terms_days} onChange={(e) => setForm({ ...form, payment_terms_days: Number(e.target.value) || 0 })} />
              </div>
              <div>
                <label className="label">Notes</label>
                <textarea className="input" rows={2} value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} />
              </div>

              <div className="border-t pt-4">
                <h4 className="text-sm font-semibold text-gray-700 mb-3">Addresses</h4>
                {form.addresses.map((addr, i) => (
                  <div key={i} className="border border-gray-200 rounded-lg p-3 mb-3">
                    <div className="flex justify-between mb-2">
                      <span className="text-xs font-semibold text-gray-500 uppercase">Address {i + 1}</span>
                      <select className="input text-xs border border-gray-300 rounded px-2 py-1" value={addr.address_type} onChange={(e) => {
                        const addrs = [...form.addresses]; addrs[i].address_type = e.target.value as any; setForm({ ...form, addresses: addrs })
                      }}>
                        <option value="billing">Billing</option>
                        <option value="shipping">Shipping</option>
                        <option value="other">Other</option>
                      </select>
                    </div>
                    <input className="input mb-2" value={addr.line1} onChange={(e) => { const a=[...form.addresses]; a[i].line1=e.target.value; setForm({...form, addresses:a}) }} placeholder="Line 1" />
                    <input className="input mb-2" value={addr.line2} onChange={(e) => { const a=[...form.addresses]; a[i].line2=e.target.value; setForm({...form, addresses:a}) }} placeholder="Line 2" />
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
                      <input className="input" value={addr.city} onChange={(e) => { const a=[...form.addresses]; a[i].city=e.target.value; setForm({...form, addresses:a}) }} placeholder="City" />
                      <input className="input" value={addr.district} onChange={(e) => { const a=[...form.addresses]; a[i].district=e.target.value; setForm({...form, addresses:a}) }} placeholder="District" />
                      <input className="input" value={addr.state_code} onChange={(e) => { const a=[...form.addresses]; a[i].state_code=e.target.value; setForm({...form, addresses:a}) }} placeholder="State code" />
                      <input className="input" value={addr.postal_code} onChange={(e) => { const a=[...form.addresses]; a[i].postal_code=e.target.value; setForm({...form, addresses:a}) }} placeholder="Postal" />
                    </div>
                    <div className="flex items-center gap-2 mt-2">
                      <input type="checkbox" checked={addr.is_default} onChange={(e) => { const a=[...form.addresses]; a[i].is_default=e.target.checked; setForm({...form, addresses:a}) }} />
                      <label className="text-xs text-gray-600">Default</label>
                    </div>
                  </div>
                ))}
                <button type="button" onClick={addAddress} className="text-sm text-brand-600 hover:underline flex items-center gap-1">
                  <Plus className="w-3 h-3" /> Add address
                </button>
              </div>

              <div className="flex justify-end gap-2 pt-4">
                <button type="button" onClick={() => setOpen(false)} className="btn-secondary">Cancel</button>
                <button type="submit" className="btn-primary" disabled={saving}>{saving ? <Loader2 className="w-4 h-4" /> : <Save className="w-4 h-4" />} {saving ? 'Saving...' : 'Save'}</button>
              </div>
            </form>
          </Modal>
    </div>
  )
}

type PartyForm = {
  code: string
  name: string
  legal_name: string
  kind: PartyKind
  gstin: string
  pan: string
  tax_registration_type: string
  email: string
  phone: string
  alternate_phone: string
  opening_balance: string
  opening_balance_side: 'receivable' | 'payable' | 'none'
  credit_limit: string
  payment_terms_days: number
  notes: string
  addresses: Array<{
    address_type: 'billing' | 'shipping' | 'other'
    line1: string
    line2: string
    city: string
    district: string
    state_code: string
    state_name: string
    postal_code: string
    country_code: string
    is_default: boolean
    id?: string
  }>
}



