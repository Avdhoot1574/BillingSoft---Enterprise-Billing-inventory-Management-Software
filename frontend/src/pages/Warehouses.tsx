import { useEffect, useState } from 'react'
import { useAuth } from '@/context/AuthContext'
import api from '@/api/index'
import Modal from '@/components/common/Modal'
import { Plus, Search, Edit2, Save, Loader2 } from 'lucide-react'

export default function Warehouses() {
  const { permissions } = useAuth()
  const [items, setItems] = useState<any[]>([])
  const [search, setSearch] = useState('')
  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [open, setOpen] = useState(false)
  const [editing, setEditing] = useState(false)
  const [current, setCurrent] = useState<any>(null)
  const [form, setForm] = useState({ name: '', code: '', address: '', is_default: false, is_active: true })
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')

  const canCreate = permissions.includes('inventory.adjust')
  const canUpdate = permissions.includes('inventory.adjust')

  useEffect(() => {
    load()
  }, [search])

  const load = async () => {
    setLoading(true)
    try {
      const res = await api.get('/warehouses', { params: { search: search || undefined, limit: 100 } })
      setItems(res.data as any[])
    } catch (e: any) {
      setError(e.message || 'Failed to load warehouses')
    } finally {
      setLoading(false)
    }
  }

  const openCreate = () => {
    setEditing(false)
    setCurrent(null)
    setForm({ name: '', code: '', address: '', is_default: false, is_active: true })
    setError('')
    setSuccess('')
    setOpen(true)
  }

  const openEdit = (item: any) => {
    setEditing(true)
    setCurrent(item)
    setForm({ name: item.name, code: item.code ?? '', address: item.address ?? '', is_default: !!item.is_default, is_active: !!item.is_active })
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
        code: form.code || null,
        address: form.address || null,
        is_default: form.is_default,
        is_active: form.is_active,
      }
      if (editing && current) {
        await api.patch(`/warehouses/${current.id}`, payload)
      } else {
        await api.post('/warehouses', payload)
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
          <h1 className="text-2xl font-bold text-gray-900">Warehouses</h1>
          <p className="text-gray-500">Storage locations for inventory.</p>
        </div>
        {canCreate && (
          <button onClick={openCreate} className="btn-primary flex items-center gap-2">
            <Plus className="w-4 h-4" /> Add Warehouse
          </button>
        )}
      </div>

      <div className="card">
        <div className="overflow-x-auto">
          <table className="min-w-full">
            <thead>
              <tr>
                <th>Name</th>
                <th className="text-center">Code</th>
                <th>Address</th>
                <th className="text-center">Default</th>
                <th className="text-center">Active</th>
                <th className="text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr><td colSpan={6} className="p-4 text-center"><Loader2 className="w-5 h-5 animate-spin" /> Loading...</td></tr>
              ) : items.length === 0 ? (
                <tr><td colSpan={6} className="p-4 text-center text-gray-400">No warehouses found.</td></tr>
              ) : (
                items.map((w) => (
                  <tr key={w.id} className="border-b border-gray-100 hover:bg-gray-50">
                    <td className="font-medium">{w.name}</td>
                    <td className="text-center text-gray-600">{w.code ?? '—'}</td>
                    <td className="text-gray-600">{w.address ?? '—'}</td>
                    <td className="text-center">{w.is_default ? 'Yes' : 'No'}</td>
                    <td className="text-center">{w.is_active ? 'Yes' : 'No'}</td>
                    <td className="text-right">
                      {canUpdate && (
                        <button onClick={() => openEdit(w)} className="text-brand-600 hover:underline text-sm mr-3">Edit</button>
                      )}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      <Modal open={open} onClose={() => setOpen(false)} title={editing ? 'Edit Warehouse' : 'Create Warehouse'}>
        {error && <div className="mb-3 rounded-md bg-red-50 p-2 text-sm text-red-700">{error}</div>}
        {success && <div className="mb-3 rounded-md bg-green-50 p-2 text-sm text-green-700">{success}</div>}
        <form onSubmit={(e) => { e.preventDefault(); save() }} className="space-y-3">
              <div>
                <label className="label">Warehouse name</label>
                <input className="input" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} required />
              </div>
              <div>
                <label className="label">Code (optional)</label>
                <input className="input" value={form.code} onChange={(e) => setForm({ ...form, code: e.target.value })} />
              </div>
              <div>
                <label className="label">Address (optional)</label>
                <input className="input" value={form.address} onChange={(e) => setForm({ ...form, address: e.target.value })} />
              </div>
              <div className="flex items-center gap-2">
                <input type="checkbox" checked={form.is_default} onChange={(e) => setForm({ ...form, is_default: e.target.checked })} />
                <label className="text-sm text-gray-700">Default warehouse</label>
              </div>
              <div className="flex items-center gap-2">
                <input type="checkbox" checked={form.is_active} onChange={(e) => setForm({ ...form, is_active: e.target.checked })} />
                <label className="text-sm text-gray-700">Active</label>
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



