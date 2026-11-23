import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '@/context/AuthContext'
import api from '@/api/index'
import { formatNumber } from '@/lib/format'
import Modal from '@/components/common/Modal'
import { Plus, Search, Edit2, Trash2, Save, Loader2 } from 'lucide-react'

export default function Units() {
  const { permissions } = useAuth()
  const navigate = useNavigate()
  const [items, setItems] = useState<any[]>([])
  const [search, setSearch] = useState('')
  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [open, setOpen] = useState(false)
  const [editing, setEditing] = useState(false)
  const [current, setCurrent] = useState<any>(null)
  const [form, setForm] = useState({ name: '', abbreviation: '', decimal_places: 2 })
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
      const res = await api.get('/units', { params: { search: search || undefined, limit: 100 } })
      setItems(res.data as any[])
    } catch (e: any) {
      setError(e.message || 'Failed to load units')
    } finally {
      setLoading(false)
    }
  }

  const openCreate = () => {
    setEditing(false)
    setCurrent(null)
    setForm({ name: '', abbreviation: '', decimal_places: 2 })
    setError('')
    setSuccess('')
    setOpen(true)
  }

  const openEdit = (item: any) => {
    setEditing(true)
    setCurrent(item)
    setForm({ name: item.name, abbreviation: item.abbreviation, decimal_places: item.decimal_places ?? 2 })
    setError('')
    setSuccess('')
    setOpen(true)
  }

  const save = async () => {
    setError('')
    setSaving(true)
    try {
      if (editing && current) {
        await api.patch(`/units/${current.id}`, { name: form.name, abbreviation: form.abbreviation, decimal_places: form.decimal_places })
      } else {
        await api.post('/units', { name: form.name, abbreviation: form.abbreviation, decimal_places: form.decimal_places })
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

  const remove = async (id: string) => {
    if (!window.confirm('Archive this unit?')) return
    // Units have no archive endpoint; skip delete
  }

  return (
    <div className="p-6">
      <div className="flex flex-col md:flex-row md:items-center justify-between mb-6 gap-3">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Units of Measure</h1>
          <p className="text-gray-500">Manage units used for items and invoices.</p>
        </div>
        {canCreate && (
          <button onClick={openCreate} className="btn-primary flex items-center gap-2">
            <Plus className="w-4 h-4" /> Add Unit
          </button>
        )}
      </div>

      <div className="card">
        <div className="overflow-x-auto">
          <table className="min-w-full">
            <thead>
              <tr>
                <th>Name</th>
                <th className="text-center">Abbreviation</th>
                <th className="text-center">Decimals</th>
                <th className="text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr><td colSpan={4} className="p-4 text-center"><Loader2 className="w-5 h-5 animate-spin" /> Loading...</td></tr>
              ) : items.length === 0 ? (
                <tr><td colSpan={4} className="p-4 text-center text-gray-400">No units found.</td></tr>
              ) : (
                items.map((u) => (
                  <tr key={u.id} className="border-b border-gray-100 hover:bg-gray-50">
                    <td className="font-medium">{u.name}</td>
                    <td className="text-center text-gray-600">{u.abbreviation}</td>
                    <td className="text-center text-gray-600">{formatNumber(u.decimal_places, 0)}</td>
                    <td className="text-right">
                      {canUpdate && (
                        <button onClick={() => openEdit(u)} className="text-brand-600 hover:underline text-sm mr-3">Edit</button>
                      )}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      <Modal open={open} onClose={() => setOpen(false)} title={editing ? 'Edit Unit' : 'Create Unit'}>
        {error && <div className="mb-3 rounded-md bg-red-50 p-2 text-sm text-red-700">{error}</div>}
        {success && <div className="mb-3 rounded-md bg-green-50 p-2 text-sm text-green-700">{success}</div>}
        <form onSubmit={(e) => { e.preventDefault(); save() }} className="space-y-3">
              <div>
                <label className="label">Unit name</label>
                <input className="input" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} required />
              </div>
              <div>
                <label className="label">Abbreviation</label>
                <input className="input" value={form.abbreviation} onChange={(e) => setForm({ ...form, abbreviation: e.target.value })} required />
              </div>
              <div>
                <label className="label">Decimal places</label>
                <input type="number" min="0" max="6" className="input" value={form.decimal_places} onChange={(e) => setForm({ ...form, decimal_places: Number(e.target.value) || 2 })} required />
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



