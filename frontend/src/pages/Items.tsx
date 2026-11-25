import { useEffect, useState } from 'react'
import { useAuth } from '@/context/AuthContext'
import api from '@/api/index'
import { formatMoney } from '@/lib/format'
import Modal from '@/components/common/Modal'
import { Plus, Search, Save, Loader2, Package } from 'lucide-react'

export default function Items() {
  const { permissions } = useAuth()
  const [items, setItems] = useState<any[]>([])
  const [units, setUnits] = useState<any[]>([])
  const [categories, setCategories] = useState<any[]>([])
  const [taxRates, setTaxRates] = useState<any[]>([])
  const [search, setSearch] = useState('')
  const [archivedOnly, setArchivedOnly] = useState(false)
  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [open, setOpen] = useState(false)
  const [editing, setEditing] = useState(false)
  const [current, setCurrent] = useState<any>(null)
  const [form, setForm] = useState<ItemForm>({
    name: '', unit_id: '', category_id: '', tax_rate_id: '', sku: '', description: '', kind: 'goods',
    hsn_sac: '', barcode: '', sale_price: '0', purchase_price: '0', opening_quantity: '0',
    reorder_level: '0', sale_price_includes_tax: false, purchase_price_includes_tax: false, track_inventory: true,
  })
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')

  const canCreate = permissions.includes('items.create')
  const canUpdate = permissions.includes('items.update')
  const canArchive = permissions.includes('items.archive')

  useEffect(() => {
    load()
    loadLookups()
  }, [search, archivedOnly])

  const load = async () => {
    setLoading(true)
    try {
      const res = await api.get('/items', { params: { search: search || undefined, archived_only: archivedOnly, limit: 100 } })
      setItems(res.data as any[])
    } catch (e: any) {
      setError(e.message || 'Failed to load items')
    } finally {
      setLoading(false)
    }
  }

  const loadLookups = async () => {
    try {
      const [u, c, t] = await Promise.all([
        api.get('/units?limit=200'),
        api.get('/categories?limit=200'),
        api.get('/tax-rates?limit=200'),
      ])
      setUnits(u.data as any[])
      setCategories(c.data as any[])
      setTaxRates(t.data as any[])
    } catch {}
  }

  const openCreate = () => {
    setEditing(false)
    setCurrent(null)
    setForm({ name: '', unit_id: '', category_id: '', tax_rate_id: '', sku: '', description: '', kind: 'goods', hsn_sac: '', barcode: '', sale_price: '0', purchase_price: '0', opening_quantity: '0', reorder_level: '0', sale_price_includes_tax: false, purchase_price_includes_tax: false, track_inventory: true })
    setError('')
    setSuccess('')
    setOpen(true)
  }

  const openEdit = (item: any) => {
    setEditing(true)
    setCurrent(item)
    setForm({
      name: item.name, unit_id: item.unit_id, category_id: item.category_id ?? '', tax_rate_id: item.tax_rate_id ?? '',
      sku: item.sku ?? '', description: item.description ?? '', kind: item.kind, hsn_sac: item.hsn_sac ?? '', barcode: item.barcode ?? '',
      sale_price: String(item.sale_price ?? 0), purchase_price: String(item.purchase_price ?? 0), opening_quantity: String(item.opening_quantity ?? 0),
      reorder_level: String(item.reorder_level ?? 0), sale_price_includes_tax: !!item.sale_price_includes_tax,
      purchase_price_includes_tax: !!item.purchase_price_includes_tax, track_inventory: !!item.track_inventory,
    })
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
        unit_id: form.unit_id,
        category_id: form.category_id || null,
        tax_rate_id: form.tax_rate_id || null,
        sku: form.sku || null,
        description: form.description || null,
        kind: form.kind,
        hsn_sac: form.hsn_sac || null,
        barcode: form.barcode || null,
        sale_price: Number(form.sale_price) || 0,
        purchase_price: Number(form.purchase_price) || 0,
        opening_quantity: Number(form.opening_quantity) || 0,
        reorder_level: Number(form.reorder_level) || 0,
        sale_price_includes_tax: form.sale_price_includes_tax,
        purchase_price_includes_tax: form.purchase_price_includes_tax,
        track_inventory: form.track_inventory,
      }
      if (editing && current) {
        await api.patch(`/items/${current.id}`, payload)
      } else {
        await api.post('/items', payload)
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
    if (!window.confirm('Archive this item?')) return
    try {
      await api.post(`/items/${id}/archive`)
      load()
    } catch (e: any) {
      setError(e.message || 'Archive failed')
    }
  }

  const restore = async (id: string) => {
    try {
      setError('')
      await api.post(`/items/${id}/restore`)
      await load()
    } catch (e: any) {
      setError(e.message || 'Restore failed')
    }
  }

  return (
    <div className="p-6">
      <div className="flex flex-col md:flex-row md:items-center justify-between mb-6 gap-3">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Items</h1>
          <p className="text-gray-500">Products and services you sell or purchase.</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <div className="flex rounded-lg border border-gray-300 overflow-hidden text-sm">
            <button type="button" onClick={() => setArchivedOnly(false)} className={`px-3 py-1.5 ${!archivedOnly ? 'bg-brand-50 text-brand-700 font-semibold' : 'text-gray-600'}`}>Active</button>
            <button type="button" onClick={() => setArchivedOnly(true)} className={`px-3 py-1.5 ${archivedOnly ? 'bg-brand-50 text-brand-700 font-semibold' : 'text-gray-600'}`}>Archived</button>
          </div>
          {canCreate && (
          <button onClick={openCreate} className="btn-primary flex items-center gap-2">
            <Package className="w-4 h-4" /> Add Item
          </button>
          )}
        </div>
      </div>

      {error && !open && <div className="mb-3 rounded-md bg-red-50 p-3 text-sm text-red-700" role="alert">{error}</div>}

      <div className="relative mb-4">
        <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
          <Search className="w-4 h-4 text-gray-400" />
        </div>
        <input
          className="input pl-9"
          placeholder="Search item name, SKU, barcode..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
      </div>

      <div className="card">
        <div className="overflow-x-auto">
          <table className="min-w-full">
            <thead>
              <tr>
                <th>Name</th>
                <th className="text-center">SKU</th>
                <th className="text-center">Unit</th>
                <th className="text-right">Sale price</th>
                <th className="text-right">Purchase price</th>
                <th className="text-center">Stock</th>
                <th className="text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr><td colSpan={7} className="p-4 text-center"><Loader2 className="w-5 h-5 animate-spin" /> Loading...</td></tr>
              ) : items.length === 0 ? (
                <tr><td colSpan={7} className="p-4 text-center text-gray-400">No {archivedOnly ? 'archived ' : ''}items found.</td></tr>
              ) : (
                items.map((it) => (
                  <tr key={it.id} className="border-b border-gray-100 hover:bg-gray-50">
                    <td className="font-medium">{it.name}</td>
                    <td className="text-center text-gray-600 text-sm">{it.sku ?? '—'}</td>
                    <td className="text-center text-gray-600 text-sm">{it.unit?.abbreviation ?? '—'}</td>
                    <td className="text-right font-medium text-sm">{formatMoney(it.sale_price)}</td>
                    <td className="text-right text-sm">{formatMoney(it.purchase_price)}</td>
                    <td className="text-center text-sm">{Number(it.opening_quantity).toFixed(2)}</td>
                    <td className="text-right">
                      {canUpdate && !it.is_archived && (
                        <button onClick={() => openEdit(it)} className="text-brand-600 hover:underline text-sm mr-3">Edit</button>
                      )}
                      {canArchive && !it.is_archived && (
                        <button onClick={() => archive(it.id)} className="text-red-600 hover:underline text-sm">Archive</button>
                      )}
                      {canArchive && it.is_archived && (
                        <button onClick={() => restore(it.id)} className="text-brand-600 hover:underline text-sm">Restore</button>
                      )}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      <Modal open={open} onClose={() => setOpen(false)} title={editing ? 'Edit Item' : 'Create Item'} className="max-w-2xl overflow-y-auto max-h-[85vh]">
        {error && <div className="mb-3 rounded-md bg-red-50 p-2 text-sm text-red-700">{error}</div>}
        {success && <div className="mb-3 rounded-md bg-green-50 p-2 text-sm text-green-700">{success}</div>}
        <form onSubmit={(e) => { e.preventDefault(); save() }} className="space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div>
                  <label className="label">Item name *</label>
                  <input className="input" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} required />
                </div>
                <div>
                  <label className="label">Unit *</label>
                  <select className="input" value={form.unit_id} onChange={(e) => setForm({ ...form, unit_id: e.target.value })} required>
                    <option value="">Select unit</option>
                    {units.map((u) => (
                      <option key={u.id} value={u.id}>{u.name} ({u.abbreviation})</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="label">Category</label>
                  <select className="input" value={form.category_id} onChange={(e) => setForm({ ...form, category_id: e.target.value })}>
                    <option value="">None</option>
                    {categories.map((c) => (
                      <option key={c.id} value={c.id}>{c.name}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="label">Tax rate</label>
                  <select className="input" value={form.tax_rate_id} onChange={(e) => setForm({ ...form, tax_rate_id: e.target.value })}>
                    <option value="">None</option>
                    {taxRates.map((t) => (
                      <option key={t.id} value={t.id}>{t.name}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="label">SKU</label>
                  <input className="input" value={form.sku} onChange={(e) => setForm({ ...form, sku: e.target.value })} />
                </div>
                <div>
                  <label className="label">HSN / SAC</label>
                  <input className="input" value={form.hsn_sac} onChange={(e) => setForm({ ...form, hsn_sac: e.target.value })} />
                </div>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className="label">Sale price</label>
                  <input className="input" type="number" step="0.01" value={form.sale_price} onChange={(e) => setForm({ ...form, sale_price: e.target.value })} />
                </div>
                <div>
                  <label className="label">Purchase price</label>
                  <input className="input" type="number" step="0.01" value={form.purchase_price} onChange={(e) => setForm({ ...form, purchase_price: e.target.value })} />
                </div>
                <div>
                  <label className="label">Opening quantity</label>
                  <input className="input" type="number" step="0.001" value={form.opening_quantity} onChange={(e) => setForm({ ...form, opening_quantity: e.target.value })} />
                </div>
                <div>
                  <label className="label">Reorder level</label>
                  <input className="input" type="number" step="0.01" value={form.reorder_level} onChange={(e) => setForm({ ...form, reorder_level: e.target.value })} />
                </div>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div>
                  <label className="label">Kind</label>
                  <select className="input" value={form.kind} onChange={(e) => setForm({ ...form, kind: e.target.value as 'goods' | 'service' })}>
                    <option value="goods">Goods</option>
                    <option value="service">Service</option>
                  </select>
                </div>
                <div className="flex items-end">
                  <label className="label">Sale price includes tax</label>
                  <input type="checkbox" checked={form.sale_price_includes_tax} onChange={(e) => setForm({ ...form, sale_price_includes_tax: e.target.checked })} className="ml-2" />
                </div>
                <div className="flex items-end">
                  <label className="label">Track inventory</label>
                  <input type="checkbox" checked={form.track_inventory} onChange={(e) => setForm({ ...form, track_inventory: e.target.checked })} className="ml-2" />
                </div>
              </div>
              <div>
                <label className="label">Description</label>
                <textarea className="input" rows={2} value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} />
              </div>
              <div>
                <label className="label">Barcode</label>
                <input className="input" value={form.barcode} onChange={(e) => setForm({ ...form, barcode: e.target.value })} />
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

type ItemForm = {
  name: string
  unit_id: string
  category_id: string
  tax_rate_id: string
  sku: string
  description: string
  kind: 'goods' | 'service'
  hsn_sac: string
  barcode: string
  sale_price: string
  purchase_price: string
  opening_quantity: string
  reorder_level: string
  sale_price_includes_tax: boolean
  purchase_price_includes_tax: boolean
  track_inventory: boolean
}



