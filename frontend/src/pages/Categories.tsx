import { useEffect, useState } from 'react'
import { useAuth } from '@/context/AuthContext'
import api from '@/api/index'
import Modal from '@/components/common/Modal'
import { Plus, Search, Edit2, Save, Loader2 } from 'lucide-react'

export default function Categories() {
  const { permissions } = useAuth()
  const [items, setItems] = useState<any[]>([])
  const [search, setSearch] = useState('')
  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [open, setOpen] = useState(false)
  const [editing, setEditing] = useState(false)
  const [current, setCurrent] = useState<any>(null)
  const [form, setForm] = useState({ name: '', parent_id: '' as string | null })
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
      const res = await api.get('/categories', { params: { search: search || undefined, limit: 100 } })
      setItems(res.data as any[])
    } catch (e: any) {
      setError(e.message || 'Failed to load categories')
    } finally {
      setLoading(false)
    }
  }

  const openCreate = () => {
    setEditing(false)
    setCurrent(null)
    setForm({ name: '', parent_id: null })
    setError('')
    setSuccess('')
    setOpen(true)
  }

  const openEdit = (item: any) => {
    setEditing(true)
    setCurrent(item)
    setForm({ name: item.name, parent_id: item.parent_id ?? null })
    setError('')
    setSuccess('')
    setOpen(true)
  }

  const save = async () => {
    setError('')
    setSaving(true)
    try {
      const payload: any = { name: form.name }
      if (form.parent_id) payload.parent_id = form.parent_id
      if (editing && current) {
        await api.patch(`/categories/${current.id}`, payload)
      } else {
        await api.post('/categories', payload)
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
          <h1 className="text-2xl font-bold text-gray-900">Item Categories</h1>
          <p className="text-gray-500">Organize items into categories.</p>
        </div>
        {canCreate && (
          <button onClick={openCreate} className="btn-primary flex items-center gap-2">
            <Plus className="w-4 h-4" /> Add Category
          </button>
        )}
      </div>

      <div className="card">
        <div className="overflow-x-auto">
          <table className="min-w-full">
            <thead>
              <tr>
                <th>Name</th>
                <th className="text-center">Parent</th>
                <th className="text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr><td colSpan={3} className="p-4 text-center"><Loader2 className="w-5 h-5 animate-spin" /> Loading...</td></tr>
              ) : items.length === 0 ? (
                <tr><td colSpan={3} className="p-4 text-center text-gray-400">No categories found.</td></tr>
              ) : (
                items.map((c) => (
                  <tr key={c.id} className="border-b border-gray-100 hover:bg-gray-50">
                    <td className="font-medium">{c.name}</td>
                    <td className="text-center text-gray-600">{c.parent_id ? 'Sub-category' : '—'}</td>
                    <td className="text-right">
                      {canUpdate && (
                        <button onClick={() => openEdit(c)} className="text-brand-600 hover:underline text-sm mr-3">Edit</button>
                      )}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      <Modal open={open} onClose={() => setOpen(false)} title={editing ? 'Edit Category' : 'Create Category'}>
        {error && <div className="mb-3 rounded-md bg-red-50 p-2 text-sm text-red-700">{error}</div>}
        {success && <div className="mb-3 rounded-md bg-green-50 p-2 text-sm text-green-700">{success}</div>}
        <form onSubmit={(e) => { e.preventDefault(); save() }} className="space-y-3">
              <div>
                <label className="label">Category name</label>
                <input className="input" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} required />
              </div>
              <div>
                <label className="label">Parent category (optional)</label>
                <select className="input" value={form.parent_id ?? ''} onChange={(e) => setForm({ ...form, parent_id: e.target.value || null })}>
                  <option value="">None</option>
                  {items.map((c) => (
                    <option key={c.id} value={c.id}>{c.name}</option>
                  ))}
                </select>
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



