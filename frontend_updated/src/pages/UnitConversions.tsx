import { useEffect, useState } from 'react'
import { useAuth } from '@/context/AuthContext'
import api from '@/api/index'
import Modal from '@/components/common/Modal'
import { Plus, Save, Loader2, Trash2 } from 'lucide-react'

export default function UnitConversions() {
  const { permissions } = useAuth()
  const [items, setItems] = useState<any[]>([])
  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [open, setOpen] = useState(false)
  const [form, setForm] = useState({ from_unit_id: '', to_unit_id: '', factor: '' })
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')
  const [units, setUnits] = useState<any[]>([])

  const canCreate = permissions.includes('inventory.adjust')

  useEffect(() => {
    load()
    loadUnits()
  }, [])

  const load = async () => {
    setLoading(true)
    try {
      const res = await api.get('/unit-conversions')
      setItems(res.data as any[])
    } catch (e: any) {
      setError(e.message || 'Failed to load unit conversions')
    } finally {
      setLoading(false)
    }
  }

  const loadUnits = async () => {
    try {
      const res = await api.get('/units?limit=200')
      setUnits(res.data as any[])
    } catch {}
  }

  const openCreate = () => {
    setForm({ from_unit_id: '', to_unit_id: '', factor: '' })
    setError('')
    setSuccess('')
    setOpen(true)
  }

  const save = async () => {
    setError('')
    setSaving(true)
    try {
      await api.post('/unit-conversions', {
        from_unit_id: form.from_unit_id,
        to_unit_id: form.to_unit_id,
        factor: Number(form.factor) || 0,
      })
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
    if (!window.confirm('Delete this unit conversion?')) return
    try {
      await api.delete(`/unit-conversions/${id}`)
      load()
    } catch (e: any) {
      setError(e.message || 'Delete failed')
    }
  }

  return (
    <div className="p-6">
      <div className="flex flex-col md:flex-row md:items-center justify-between mb-6 gap-3">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Unit Conversions</h1>
          <p className="text-gray-500">Convert quantities between units (e.g. box to piece).</p>
        </div>
        {canCreate && (
          <button onClick={openCreate} className="btn-primary flex items-center gap-2">
            <Plus className="w-4 h-4" /> Add Conversion
          </button>
        )}
      </div>

      <div className="card">
        <div className="overflow-x-auto">
          <table className="min-w-full">
            <thead>
              <tr>
                <th>From Unit</th>
                <th>To Unit</th>
                <th className="text-right">Factor</th>
                <th className="text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr><td colSpan={4} className="p-4 text-center"><Loader2 className="w-5 h-5 animate-spin" /> Loading...</td></tr>
              ) : items.length === 0 ? (
                <tr><td colSpan={4} className="p-4 text-center text-gray-400">No unit conversions found.</td></tr>
              ) : (
                items.map((c) => (
                  <tr key={c.id} className="border-b border-gray-100 hover:bg-gray-50">
                    <td className="font-medium">{c.from_unit?.name ?? c.from_unit_id}</td>
                    <td className="text-gray-600">{c.to_unit?.name ?? c.to_unit_id}</td>
                    <td className="text-right font-medium">{Number(c.factor).toFixed(4)}</td>
                    <td className="text-right">
                      <button onClick={() => remove(c.id)} className="text-red-600 hover:underline text-sm">Delete</button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      <Modal open={open} onClose={() => setOpen(false)} title="Create Unit Conversion">
        {error && <div className="mb-3 rounded-md bg-red-50 p-2 text-sm text-red-700">{error}</div>}
        {success && <div className="mb-3 rounded-md bg-green-50 p-2 text-sm text-green-700">{success}</div>}
        <form onSubmit={(e) => { e.preventDefault(); save() }} className="space-y-3">
              <div>
                <label className="label">From unit</label>
                <select className="input" value={form.from_unit_id} onChange={(e) => setForm({ ...form, from_unit_id: e.target.value })} required>
                  <option value="">Select unit</option>
                  {units.map((u) => (
                    <option key={u.id} value={u.id}>{u.name} ({u.abbreviation})</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="label">To unit</label>
                <select className="input" value={form.to_unit_id} onChange={(e) => setForm({ ...form, to_unit_id: e.target.value })} required>
                  <option value="">Select unit</option>
                  {units.map((u) => (
                    <option key={u.id} value={u.id}>{u.name} ({u.abbreviation})</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="label">Conversion factor</label>
                <input className="input" type="number" step="0.00000001" value={form.factor} onChange={(e) => setForm({ ...form, factor: e.target.value })} required />
                <p className="text-xs text-gray-500">1 from-unit = X to-units</p>
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



