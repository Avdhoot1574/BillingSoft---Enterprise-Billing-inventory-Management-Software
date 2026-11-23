import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { useAuth } from '@/context/AuthContext'
import api from '@/api/index'
import { formatMoney } from '@/lib/format'
import { Plus, Trash2, Save, Loader2 } from 'lucide-react'

type Line = {
  id: string
  item_id: string | null
  item_name: string
  sku: string
  hsn_sac: string
  unit_name: string
  quantity: string
  unit_price: string
  discount_percent: string
  tax_rate_percent: string
  warehouse_id: string | null
}

const EMPTY_LINE: Line = {
  id: crypto.randomUUID(),
  item_id: null,
  item_name: '',
  sku: '',
  hsn_sac: '',
  unit_name: 'Nos',
  quantity: '1',
  unit_price: '0',
  discount_percent: '0',
  tax_rate_percent: '0',
  warehouse_id: null,
}

export default function CreateInvoice() {
  const { permissions, selectedCompany } = useAuth()
  const navigate = useNavigate()
  const { id: invoiceId } = useParams<{ id?: string }>()
  const [isEditMode, setIsEditMode] = useState(false)
  const [parties, setParties] = useState<any[]>([])
  const [items, setItems] = useState<any[]>([])
  const [units, setUnits] = useState<any[]>([])
  const [taxRates, setTaxRates] = useState<any[]>([])
  const [warehouses, setWarehouses] = useState<any[]>([])
  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')

  const [form, setForm] = useState<InvoiceForm>({
    party_id: '',
    invoice_date: new Date().toISOString().slice(0, 10),
    due_date: '',
    place_of_supply_state_code: '',
    supply_type: 'intra_state',
    customer_name: '',
    customer_gstin: '',
    billing_address: {},
    shipping_address: {},
    other_charges: '0',
    notes: '',
    terms: '',
    paid_amount: '0',
    is_full_paid: false,
    lines: [EMPTY_LINE],
  })

  useEffect(() => {
    loadLookups()
    if (invoiceId) {
      loadInvoice(invoiceId)
    }
  }, [])

  const loadLookups = async () => {
    try {
      const [p, i, u, w, t] = await Promise.all([
        api.get('/parties?limit=200'),
        api.get('/items?limit=200'),
        api.get('/units?limit=200'),
        api.get('/warehouses?limit=200'),
        api.get('/tax-rates?limit=200'),
      ])
      setParties(p.data as any[])
      setItems(i.data as any[])
      setUnits(u.data as any[])
      setWarehouses(w.data as any[])
      setTaxRates(t.data as any[])
    } catch { setError("Some customer or item lookups could not be loaded. Please retry.") }
  }

  const loadInvoice = async (invoiceId: string) => {
    setLoading(true)
    try {
      const res = await api.get(`/invoices/${invoiceId}`)
      const inv = res.data as any
      setIsEditMode(true)
      setForm({
        party_id: inv.party_id ?? '',
        invoice_date: inv.invoice_date ?? '',
        due_date: inv.due_date ?? '',
        place_of_supply_state_code: inv.place_of_supply_state_code ?? '',
        supply_type: inv.supply_type ?? 'intra_state',
        customer_name: inv.customer_name_snapshot ?? '',
        customer_gstin: inv.customer_gstin_snapshot ?? '',
        billing_address: inv.billing_address_snapshot ?? {},
        shipping_address: inv.shipping_address_snapshot ?? {},
        other_charges: String(inv.other_charges ?? 0),
        notes: inv.notes ?? '',
        terms: inv.terms ?? '',
        paid_amount: String(inv.paid_total ?? 0),
        is_full_paid: inv.payment_status === 'paid',
        lines: (inv.lines ?? []).map((line: any) => ({
          id: line.id ?? crypto.randomUUID(),
          item_id: line.item_id ?? null,
          item_name: line.item_name_snapshot ?? line.item_name,
          sku: line.sku_snapshot ?? '',
          hsn_sac: line.hsn_sac_snapshot ?? '',
          unit_name: line.unit_name_snapshot ?? 'Nos',
          quantity: String(line.quantity ?? 1),
          unit_price: String(line.unit_price ?? 0),
          discount_percent: String(line.discount_percent ?? 0),
          tax_rate_percent: String(line.tax_rate_percent ?? 0),
          warehouse_id: line.warehouse_id ?? null,
        })),
      })
    } catch (e: any) {
      setError(e.message || 'Failed to load invoice for editing')
    } finally {
      setLoading(false)
    }
  }

  const addLine = () => {
    setForm({ ...form, lines: [...form.lines, { ...EMPTY_LINE, id: crypto.randomUUID() }] })
  }

  const removeLine = (id: string) => {
    if (form.lines.length === 1) return
    setForm({ ...form, lines: form.lines.filter((l) => l.id !== id) })
  }

  const updateLine = (index: number, field: string, value: string | null) => {
    const lines = [...form.lines]
    ;(lines[index] as any)[field] = value
    setForm({ ...form, lines })
  }

  const selectItem = (index: number, item: any) => {
    const lines = [...form.lines]
    lines[index] = {
      ...lines[index],
      item_id: item.id,
      item_name: item.name,
      sku: item.sku ?? '',
      hsn_sac: item.hsn_sac ?? '',
      tax_rate_percent: String(item.tax_rate?.rate_percent ?? taxRates.find((t) => t.id === item.tax_rate_id)?.rate_percent ?? 0),
      unit_price: String(item.sale_price ?? 0),
      unit_name: item.unit?.abbreviation ?? units.find((u) => u.id === item.unit_id)?.abbreviation ?? 'Nos',
    }
    setForm({ ...form, lines })
  }

  const selectParty = (partyId: string) => {
    const party = parties.find((p) => p.id === partyId)
    setForm((prev) => ({ ...prev, party_id: partyId }))
    if (!party) return

    // Auto-fill customer name and GSTIN from party
    setForm((prev) => ({
      ...prev,
      customer_name: party.name,
      customer_gstin: party.gstin ?? '',
      place_of_supply_state_code: '',
    }))

    // Auto-fill billing address from party's default billing address
    const billingAddr = party.addresses?.find((a: any) => a.address_type === 'billing' && a.is_default)
      ?? party.addresses?.find((a: any) => a.address_type === 'billing')
      ?? {}

    // Auto-fill shipping address from party's default shipping address
    const shippingAddr = party.addresses?.find((a: any) => a.address_type === 'shipping' && a.is_default)
      ?? party.addresses?.find((a: any) => a.address_type === 'shipping')
      ?? billingAddr
      ?? {}

    const setAddress = (addr: any) => ({
      line1: addr.line1 ?? '',
      line2: addr.line2 ?? '',
      city: addr.city ?? '',
      district: addr.district ?? '',
      state_code: addr.state_code ?? '',
      state_name: addr.state_name ?? '',
      postal_code: addr.postal_code ?? '',
      country_code: addr.country_code ?? 'IN',
      is_default: addr.is_default ?? false,
    })

    setForm((prev) => ({
      ...prev,
      billing_address: setAddress(billingAddr),
      shipping_address: setAddress(shippingAddr),
      place_of_supply_state_code: billingAddr.state_code ?? prev.place_of_supply_state_code,
    }))
  }

  const roundMoney = (value: number) => Math.round((value + Number.EPSILON) * 100) / 100

  const lineTotal = (l: Line) => {
    const qty = Number(l.quantity) || 0
    const price = Number(l.unit_price) || 0
    const disc = Number(l.discount_percent) || 0
    const gross = roundMoney(qty * price)
    return roundMoney(gross - roundMoney(gross * disc / 100))
  }

  const taxAmount = (l: Line) => {
    const base = lineTotal(l)
    const rate = Number(l.tax_rate_percent) || 0
    return roundMoney(base * (rate / 100))
  }

  const subtotal = form.lines.reduce((s, l) => s + roundMoney(Number(l.quantity) * Number(l.unit_price)), 0)
  const discountTotal = form.lines.reduce((s, l) => s + roundMoney(roundMoney(Number(l.quantity) * Number(l.unit_price)) * Number(l.discount_percent) / 100), 0)
  const taxTotal = form.lines.reduce((s, l) => s + taxAmount(l), 0)
  const otherCharges = Number(form.other_charges) || 0
  const grandTotal = roundMoney(subtotal - discountTotal + taxTotal + otherCharges)
  const paidAmount = form.is_full_paid ? grandTotal : Number(form.paid_amount) || 0
  const balance = grandTotal - paidAmount
  const paymentStatus = paidAmount >= grandTotal ? 'paid' : paidAmount > 0 ? 'partially_paid' : 'unpaid'

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setSaving(true)
    try {
      // Pre-submit validation
      if (!form.customer_name) {
        setError('Customer name is required')
        setSaving(false)
        return
      }
      for (const l of form.lines) {
        if (!l.item_name?.trim()) {
          setError(`Line ${form.lines.indexOf(l) + 1}: Item name is required`)
          setSaving(false)
          return
        }
        if (!l.unit_name?.trim()) {
          setError(`Line ${form.lines.indexOf(l) + 1}: Unit is required`)
          setSaving(false)
          return
        }
        if ((Number(l.quantity) || 0) <= 0) {
          setError(`Line ${form.lines.indexOf(l) + 1}: Quantity must be greater than 0`)
          setSaving(false)
          return
        }
        const disc = Number(l.discount_percent) || 0
        const tax = Number(l.tax_rate_percent) || 0
        if (disc < 0 || disc > 100) {
          setError(`Line ${form.lines.indexOf(l) + 1}: Discount % must be between 0 and 100`)
          setSaving(false)
          return
        }
        if (tax < 0 || tax > 100) {
          setError(`Line ${form.lines.indexOf(l) + 1}: Tax % must be between 0 and 100`)
          setSaving(false)
          return
        }
      }

      const payload = {
        party_id: form.party_id || null,
        invoice_date: form.invoice_date,
        due_date: form.due_date || null,
        place_of_supply_state_code: form.place_of_supply_state_code || null,
        supply_type: form.supply_type,
        customer_name: form.customer_name,
        customer_gstin: form.customer_gstin || null,
        billing_address: form.billing_address,
        shipping_address: form.shipping_address,
        other_charges: otherCharges,
        notes: form.notes || null,
        terms: form.terms || null,
        paid_amount: paidAmount,
        lines: form.lines.map((l) => ({
          item_id: l.item_id || null,
          item_name: l.item_name,
          sku: l.sku || null,
          hsn_sac: l.hsn_sac || null,
          unit_name: l.unit_name,
          quantity: Number(l.quantity) || 0,
          unit_price: Number(l.unit_price) || 0,
          discount_percent: Number(l.discount_percent) || 0,
          tax_rate_percent: Number(l.tax_rate_percent) || 0,
          warehouse_id: l.warehouse_id || null,
        })),
      }
      const res = await api.post('/invoices', payload)
      const inv = res.data as any
      const invoiceId = inv.id ?? inv.invoice?.id
      setSuccess('Invoice created successfully')
      setSaving(false)
      setTimeout(() => navigate(`/invoices/${invoiceId}`), 800)
    } catch (err: any) {
      // Show detailed validation errors from 422 response
      const details = err.details ?? err.response?.data?.error?.details
      if (Array.isArray(details)) {
        const msgs = details.map((d: any) => {
          const loc = d.loc?.join('.') || 'field'
          return `${loc}: ${d.msg}`
        })
        setError('Validation failed: ' + msgs.join('; '))
      } else {
        setError(err.message || 'Failed to create invoice')
      }
      setSaving(false)
    }
  }

  const handleSubmitEdit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setSaving(true)
    try {
      if (!invoiceId) return
      if (!form.customer_name) {
        setError('Customer name is required')
        setSaving(false)
        return
      }
      for (const l of form.lines) {
        if (!l.item_name?.trim()) {
          setError(`Line ${form.lines.indexOf(l) + 1}: Item name is required`)
          setSaving(false)
          return
        }
        if (!l.unit_name?.trim()) {
          setError(`Line ${form.lines.indexOf(l) + 1}: Unit is required`)
          setSaving(false)
          return
        }
        if ((Number(l.quantity) || 0) <= 0) {
          setError(`Line ${form.lines.indexOf(l) + 1}: Quantity must be greater than 0`)
          setSaving(false)
          return
        }
        const disc = Number(l.discount_percent) || 0
        const tax = Number(l.tax_rate_percent) || 0
        if (disc < 0 || disc > 100) {
          setError(`Line ${form.lines.indexOf(l) + 1}: Discount % must be between 0 and 100`)
          setSaving(false)
          return
        }
        if (tax < 0 || tax > 100) {
          setError(`Line ${form.lines.indexOf(l) + 1}: Tax % must be between 0 and 100`)
          setSaving(false)
          return
        }
      }

      const payload = {
        party_id: form.party_id || null,
        invoice_date: form.invoice_date,
        due_date: form.due_date || null,
        place_of_supply_state_code: form.place_of_supply_state_code || null,
        supply_type: form.supply_type,
        customer_name: form.customer_name,
        customer_gstin: form.customer_gstin || null,
        billing_address: form.billing_address,
        shipping_address: form.shipping_address,
        other_charges: otherCharges,
        notes: form.notes || null,
        terms: form.terms || null,
        paid_amount: paidAmount,
        lines: form.lines.map((l) => ({
          item_id: l.item_id || null,
          item_name: l.item_name,
          sku: l.sku || null,
          hsn_sac: l.hsn_sac || null,
          unit_name: l.unit_name,
          quantity: Number(l.quantity) || 0,
          unit_price: Number(l.unit_price) || 0,
          discount_percent: Number(l.discount_percent) || 0,
          tax_rate_percent: Number(l.tax_rate_percent) || 0,
          warehouse_id: l.warehouse_id || null,
        })),
      }
      const res = await api.patch(`/invoices/${invoiceId}`, payload)
      const inv = res.data as any
      setSuccess('Invoice updated successfully')
      setSaving(false)
      setTimeout(() => navigate(`/invoices/${inv.id ?? inv.invoice?.id}`), 800)
    } catch (err: any) {
      const details = err.details ?? err.response?.data?.error?.details
      if (Array.isArray(details)) {
        const msgs = details.map((d: any) => {
          const loc = d.loc?.join('.') || 'field'
          return `${loc}: ${d.msg}`
        })
        setError('Validation failed: ' + msgs.join('; '))
      } else {
        setError(err.message || 'Failed to update invoice')
      }
      setSaving(false)
    }
  }

  const canPost = permissions.includes('sales.invoice.post')

  return (
    <div className="p-6">
      <div className="flex flex-col md:flex-row md:items-center justify-between mb-6 gap-3">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">{isEditMode ? 'Edit Sales Invoice' : 'Create Sales Invoice'}</h1>
          <p className="text-gray-500">{isEditMode ? 'Modify invoice details below.' : 'Select a party to auto-fill customer details, then add line items.'}</p>
        </div>
        <div className="flex gap-2">
          <button onClick={() => navigate('/invoices')} className="btn-secondary">Back to list</button>
          <button onClick={isEditMode ? handleSubmitEdit : handleSubmit} className="btn-primary" disabled={saving || loading}>
            {saving ? <Loader2 className="w-4 h-4 mr-2" /> : <Save className="w-4 h-4 mr-2" />} Save Invoice
          </button>
        </div>
      </div>

      {error && <div className="mb-4 rounded-md bg-red-50 p-3 text-sm text-red-700 border border-red-100">{error}</div>}
      {success && <div className="mb-4 rounded-md bg-green-50 p-3 text-sm text-green-700 border border-green-100">{success}</div>}

      <div className="card">
        <form onSubmit={(e) => (isEditMode ? handleSubmitEdit(e) : handleSubmit(e))} className="space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            <div>
              <label className="label">Customer / Party</label>
              <select className="input" value={form.party_id} onChange={(e) => selectParty(e.target.value)}>
                <option value="">Select party (optional)</option>
                {parties.map((p) => (
                  <option key={p.id} value={p.id}>{p.name} ({p.kind})</option>
                ))}
              </select>
            </div>
            <div>
              <label className="label">Invoice date *</label>
              <input className="input" type="date" value={form.invoice_date} onChange={(e) => setForm({ ...form, invoice_date: e.target.value })} required />
            </div>
            <div>
              <label className="label">Due date</label>
              <input className="input" type="date" value={form.due_date} onChange={(e) => setForm({ ...form, due_date: e.target.value })} />
            </div>
            <div>
              <label className="label">Supply type</label>
              <select className="input" value={form.supply_type} onChange={(e) => setForm({ ...form, supply_type: e.target.value as 'intra_state' | 'inter_state' | 'export' | 'other' })}>
                <option value="intra_state">Intra-state</option>
                <option value="inter_state">Inter-state</option>
                <option value="export">Export</option>
                <option value="other">Other</option>
              </select>
            </div>
            <div>
              <label className="label">Place of supply state code</label>
              <input className="input" maxLength={2} value={form.place_of_supply_state_code} onChange={(e) => setForm({ ...form, place_of_supply_state_code: e.target.value.toUpperCase() })} />
              <p className="text-xs text-gray-500">2-digit state code (e.g. 27 for Maharashtra)</p>
            </div>
            <div className="md:col-span-2">
              <label className="label">Customer name *</label>
              <input className="input" value={form.customer_name} onChange={(e) => setForm({ ...form, customer_name: e.target.value })} required />
            </div>
            <div>
              <label className="label">Customer GSTIN</label>
              <input className="input" maxLength={15} value={form.customer_gstin} onChange={(e) => setForm({ ...form, customer_gstin: e.target.value.toUpperCase() })} />
            </div>
          </div>

          <div className="border-t pt-4">
            <h3 className="text-sm font-semibold text-gray-700 uppercase tracking-wider mb-3">Billing address</h3>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              <input className="input" placeholder="Line 1" value={String(form.billing_address.line1 ?? '')} onChange={(e) => setForm({ ...form, billing_address: { ...form.billing_address, line1: e.target.value } }) } />
              <input className="input" placeholder="Line 2" value={String(form.billing_address.line2 ?? '')} onChange={(e) => setForm({ ...form, billing_address: { ...form.billing_address, line2: e.target.value } }) } />
              <input className="input" placeholder="City" value={String(form.billing_address.city ?? '')} onChange={(e) => setForm({ ...form, billing_address: { ...form.billing_address, city: e.target.value } }) } />
              <input className="input" placeholder="State / Postal" value={String(form.billing_address.state_code ?? '')} onChange={(e) => setForm({ ...form, billing_address: { ...form.billing_address, state_code: e.target.value } }) } />
            </div>
          </div>

          <div className="border-t pt-4">
            <h3 className="text-sm font-semibold text-gray-700 uppercase tracking-wider mb-3">Shipping address</h3>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              <input className="input" placeholder="Line 1" value={String(form.shipping_address.line1 ?? '')} onChange={(e) => setForm({ ...form, shipping_address: { ...form.shipping_address, line1: e.target.value } }) } />
              <input className="input" placeholder="Line 2" value={String(form.shipping_address.line2 ?? '')} onChange={(e) => setForm({ ...form, shipping_address: { ...form.shipping_address, line2: e.target.value } }) } />
              <input className="input" placeholder="City" value={String(form.shipping_address.city ?? '')} onChange={(e) => setForm({ ...form, shipping_address: { ...form.shipping_address, city: e.target.value } }) } />
              <input className="input" placeholder="State / Postal" value={String(form.shipping_address.state_code ?? '')} onChange={(e) => setForm({ ...form, shipping_address: { ...form.shipping_address, state_code: e.target.value } }) } />
            </div>
          </div>

          <div className="border-t pt-4">
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-sm font-semibold text-gray-700 uppercase tracking-wider">Line items</h3>
              <button type="button" onClick={addLine} className="text-sm text-brand-600 hover:underline flex items-center gap-1">
                <Plus className="w-3 h-3" /> Add line
              </button>
            </div>
            <div className="overflow-x-auto border border-gray-200 rounded-lg">
              <table className="min-w-full">
                <thead>
                  <tr className="bg-gray-50">
                    <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500">Item</th>
                    <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500">SKU / HSN</th>
                    <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500">Unit</th>
                    <th className="px-4 py-3 text-right text-xs font-semibold text-gray-500">Qty</th>
                    <th className="px-4 py-3 text-right text-xs font-semibold text-gray-500">Unit price</th>
                    <th className="px-4 py-3 text-right text-xs font-semibold text-gray-500">Disc %</th>
                    <th className="px-4 py-3 text-right text-xs font-semibold text-gray-500">Tax %</th>
                    <th className="px-4 py-3 text-right text-xs font-semibold text-gray-500">Warehouse</th>
                    <th className="px-4 py-3 text-right text-xs font-semibold text-gray-500">Line total</th>
                    <th className="px-4 py-3 text-right text-xs font-semibold text-gray-500"></th>
                  </tr>
                </thead>
                <tbody>
                  {form.lines.map((line, index) => (
                    <tr key={line.id} className="border-b border-gray-100">
                      <td className="px-4 py-3">
                        <select
                          className="input input-sm w-full"
                          value={line.item_id ?? ''}
                          onChange={(e) => {
                            const sel = items.find((it) => it.id === e.target.value)
                            if (sel) selectItem(index, sel)
                            else updateLine(index, 'item_id', e.target.value || null)
                          }}
                        >
                          <option value="">Enter item name</option>
                          {items.map((it) => (
                            <option key={it.id} value={it.id}>{it.name}</option>
                          ))}
                        </select>
                        <div className="mt-1">
                          <input className="input input-sm w-full" placeholder="Item name" value={line.item_name} onChange={(e) => updateLine(index, 'item_name', e.target.value)} />
                        </div>
                      </td>
                      <td className="px-4 py-3">
                        <input className="input input-sm w-full" placeholder="SKU" value={line.sku} onChange={(e) => updateLine(index, 'sku', e.target.value)} />
                        <input className="input input-sm w-full mt-1" placeholder="HSN/SAC" value={line.hsn_sac} onChange={(e) => updateLine(index, 'hsn_sac', e.target.value)} />
                      </td>
                      <td className="px-4 py-3">
                        <select className="input input-sm w-full" value={line.unit_name} onChange={(e) => {
                          updateLine(index, 'unit_name', e.target.value)
                        }}>
                          <option value="Nos">Nos</option>
                          {units.map((u) => (
                            <option key={u.id} value={u.abbreviation}>{u.name} ({u.abbreviation})</option>
                          ))}
                        </select>
                      </td>
                      <td className="px-4 py-3 text-right">
                        <input className="input input-sm text-right w-full" value={line.quantity} onChange={(e) => updateLine(index, 'quantity', e.target.value)} />
                      </td>
                      <td className="px-4 py-3 text-right">
                        <input className="input input-sm text-right w-full" value={line.unit_price} onChange={(e) => updateLine(index, 'unit_price', e.target.value)} />
                      </td>
                      <td className="px-4 py-3 text-right">
                        <input className="input input-sm text-right w-full" value={line.discount_percent} onChange={(e) => updateLine(index, 'discount_percent', e.target.value)} />
                      </td>
                      <td className="px-4 py-3 text-right">
                        <input className="input input-sm text-right w-full" value={line.tax_rate_percent} onChange={(e) => updateLine(index, 'tax_rate_percent', e.target.value)} />
                      </td>
                      <td className="px-4 py-3 text-right">
                        <select className="input input-sm w-full" value={line.warehouse_id ?? ''} onChange={(e) => updateLine(index, 'warehouse_id', e.target.value || null)}>
                          <option value="">None</option>
                          {warehouses.map((w) => (
                            <option key={w.id} value={w.id}>{w.name}</option>
                          ))}
                        </select>
                      </td>
                      <td className="px-4 py-3 text-right font-mono text-sm">{formatMoney(lineTotal(line))}</td>
                      <td className="px-4 py-3 text-right">
                        {form.lines.length > 1 && (
                          <button type="button" onClick={() => removeLine(line.id)} className="text-red-500 hover:text-red-700"><Trash2 className="w-4 h-4" /></button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="flex justify-end pt-3">
              <p className="text-sm font-medium text-gray-700">Lines: {form.lines.length}</p>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="label">Other charges</label>
              <input className="input" type="number" step="0.01" value={form.other_charges} onChange={(e) => setForm({ ...form, other_charges: e.target.value })} />
            </div>
            <div>
              <label className="label">Notes</label>
              <input className="input" value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} />
            </div>
            <div className="md:col-span-2">
              <label className="label">Terms</label>
              <input className="input" value={form.terms} onChange={(e) => setForm({ ...form, terms: e.target.value })} />
            </div>
          </div>

            <div className="bg-gray-50 rounded-lg p-4 border border-gray-200">
              <div className="grid grid-cols-1 md:grid-cols-4 gap-4 text-sm">
                <div>
                  <p className="text-gray-500 text-xs">Subtotal</p>
                  <p className="font-medium">{formatMoney(subtotal)}</p>
                </div>
                <div>
                  <p className="text-gray-500 text-xs">Discount</p>
                  <p className="font-medium text-gray-600">-{formatMoney(discountTotal)}</p>
                </div>
                <div>
                  <p className="text-gray-500 text-xs">Tax</p>
                  <p className="font-medium">{formatMoney(taxTotal)}</p>
                </div>
                <div>
                  <p className="text-gray-500 text-xs">Grand total</p>
                  <p className="font-bold text-brand-700">{formatMoney(grandTotal)}</p>
                </div>
              </div>
            </div>

            {/* Payment tracking section */}
            <div className="border-t pt-4">
              <h3 className="text-sm font-semibold text-gray-700 uppercase tracking-wider mb-3">Payment</h3>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className="label">Paid amount</label>
                  <input className="input" type="number" step="0.01" value={form.is_full_paid ? String(grandTotal) : form.paid_amount} onChange={(e) => setForm({ ...form, paid_amount: e.target.value, is_full_paid: false })} />
                </div>
                <div className="flex items-center gap-2">
                  <input type="checkbox" checked={form.is_full_paid} onChange={(e) => {
                    if (e.target.checked) {
                      setForm({ ...form, paid_amount: String(grandTotal), is_full_paid: true })
                    } else {
                      setForm({ ...form, paid_amount: '0', is_full_paid: false })
                    }
                  }} />
                  <label className="text-sm text-slate-600 cursor-pointer">Full paid</label>
                </div>
              </div>
              <div className="flex items-baseline gap-2 mt-3">
                <span className="text-sm font-semibold text-slate-700">Balance:</span>
                <span className={`text-lg font-bold ${balance >= grandTotal ? 'text-green-600' : balance > 0 ? 'text-amber-600' : 'text-red-600'}`}>
                  {formatMoney(balance)}
                </span>
                <span className="text-xs text-slate-500 uppercase">{paymentStatus}</span>
              </div>
            </div>

          <div className="flex justify-end gap-2 pt-4">
            <button type="button" onClick={() => navigate('/invoices')} className="btn-secondary">Cancel</button>
            <button type="submit" className="btn-primary" disabled={saving || !form.customer_name}>
              {saving ? <Loader2 className="w-4 h-4 mr-2" /> : <Save className="w-4 h-4 mr-2" />} {isEditMode ? 'Update Invoice' : 'Save Invoice'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

type InvoiceForm = {
  party_id: string
  invoice_date: string
  due_date: string
  place_of_supply_state_code: string
  supply_type: string
  customer_name: string
  customer_gstin: string
  billing_address: any
  shipping_address: any
  other_charges: string
  notes: string
  terms: string
  paid_amount: string
  is_full_paid: boolean
  lines: Line[]
}
