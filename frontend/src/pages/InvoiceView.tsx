import { useEffect, useState } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import { useAuth } from '@/context/AuthContext'
import api from '@/api/index'
import { formatMoney, formatDate } from '@/lib/format'
import { FileText, Loader2, ArrowLeft, Mail, Users, Save, RefreshCcw } from 'lucide-react'

function formatAddress(addr: any): string {
  if (!addr || typeof addr !== 'object') return ''
  const parts: string[] = []
  if (addr.line1) parts.push(addr.line1)
  if (addr.line2) parts.push(addr.line2)
  const cityLine = [addr.city, addr.district, addr.state_code, addr.postal_code]
    .filter(Boolean)
    .join(', ')
  if (cityLine) parts.push(cityLine)
  if (addr.country_code) parts.push(addr.country_code.toUpperCase())
  return parts.join('\n')
}

export default function InvoiceView() {
  const { id } = useParams<{ id: string }>()
  const { permissions, isOwner, selectedCompany } = useAuth()
  const navigate = useNavigate()
  const [invoice, setInvoice] = useState<any>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [printing, setPrinting] = useState(false)
  const [paymentEditing, setPaymentEditing] = useState(false)
  const [paidAmount, setPaidAmount] = useState('')
  const [savingPayment, setSavingPayment] = useState(false)

  const canPost = permissions.includes('sales.invoice.post')
  const canEdit = permissions.includes('sales.invoice.create')
  const canDelete = isOwner && permissions.includes('sales.invoice.cancel')

  useEffect(() => {
    if (!id) return
    load()
  }, [id])

  const load = async () => {
    setLoading(true)
    try {
      const res = await api.get(`/invoices/${id}`)
      setInvoice(res.data as any)
    } catch (e: any) {
      setError(e.message || 'Failed to load invoice')
    } finally {
      setLoading(false)
    }
  }

  const downloadPdf = async () => {
    if (!id) return
    setPrinting(true)
    try {
      const res = await api.get(`/invoices/${id}/print`, { responseType: 'blob' })
      const blob = res.data as Blob
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `invoice-${id}.pdf`
      document.body.appendChild(a)
      a.click()
      window.URL.revokeObjectURL(url)
      document.body.removeChild(a)
    } catch (e: any) {
      setError(e.message || 'Failed to download invoice PDF')
    } finally {
      setPrinting(false)
    }
  }

  const postInvoice = async () => {
    if (!window.confirm('Post this invoice? Posted invoices cannot be edited.')) return
    try {
      await api.post(`/invoices/${id}/post`, {})
      load()
    } catch (e: any) {
      setError(e.message || 'Failed to post invoice')
    }
  }

  const deleteInvoice = async () => {
    if (!window.confirm('Permanently delete this invoice? This cannot be undone.')) return
    try {
      await api.delete(`/invoices/${id}`)
      navigate('/invoices')
    } catch (e: any) {
      setError(e.message || 'Failed to delete invoice')
    }
  }

  const savePayment = async (e: React.FormEvent) => {
    e.preventDefault()
    const amount = Number(paidAmount)
    if (!Number.isFinite(amount) || amount < 0 || amount > Number(invoice.grand_total)) {
      setError('Paid amount must be between zero and the invoice total')
      return
    }
    setSavingPayment(true)
    setError('')
    try {
      await api.patch(`/invoices/${id}/payment`, { paid_amount: paidAmount })
      setPaymentEditing(false)
      await load()
    } catch (e: any) {
      setError(e.message || 'Failed to update payment')
    } finally {
      setSavingPayment(false)
    }
  }

  if (loading) {
    return (
      <div className="p-6 flex flex-col items-center justify-center h-screen">
        <Loader2 className="w-8 h-8 animate-spin text-brand-600 mb-2" />
        <p className="text-gray-500">Loading invoice...</p>
      </div>
    )
  }
  if (!invoice) {
    return (
      <div className="p-6 card">
        <h2 className="text-lg font-bold text-gray-900">Invoice not found</h2>
        <p className="text-gray-500">{error}</p>
        <button onClick={() => navigate('/invoices')} className="btn-primary mt-4">Back to invoices</button>
      </div>
    )
  }

  const STATUS_COLOR: Record<string, string> = {
    draft: 'bg-gray-100 text-gray-700',
    posted: 'bg-green-100 text-green-700',
    cancelled: 'bg-red-100 text-red-700',
  }

  return (
    <div className="p-6">
      <div className="flex flex-col md:flex-row md:items-center justify-between mb-6 gap-3">
        <div>
          <Link to="/invoices" className="text-sm text-gray-500 hover:text-brand-600 mb-1 flex items-center gap-1">
            <ArrowLeft className="w-4 h-4" /> Back to invoices
          </Link>
          <h1 className="text-2xl font-bold text-gray-900">Invoice {invoice.invoice_number ?? 'Draft'}</h1>
          <p className="text-gray-500">{formatDate(invoice.invoice_date)} · {invoice.customer_name_snapshot}</p>
        </div>
        <div className="flex gap-2">
          <span className={`inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium border ${STATUS_COLOR[invoice.status] ?? 'bg-gray-100 text-gray-700'}`}>
            {invoice.payment_status.charAt(0).toUpperCase() + invoice.payment_status.slice(1)}
          </span>
          <span className={`inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium border ${STATUS_COLOR[invoice.status] ?? 'bg-gray-100 text-gray-700'}`}>
            {invoice.status.charAt(0).toUpperCase() + invoice.status.slice(1)}
          </span>
          <button onClick={downloadPdf} className="btn-primary flex items-center gap-2" disabled={printing}>
            {printing ? <Loader2 className="w-4 h-4 animate-spin" /> : <FileText className="w-4 h-4" />} Download PDF
          </button>
          {invoice.status === 'draft' && canPost && (
            <button onClick={postInvoice} className="btn-outline">Post invoice</button>
          )}
          {invoice.status === 'draft' && canEdit && (
            <button onClick={() => navigate(`/invoices/${id}/edit`)} className="btn-secondary">Edit</button>
          )}
          {invoice.status === 'posted' && canEdit && (
            <button onClick={() => { setPaidAmount(String(invoice.paid_total)); setPaymentEditing(true) }} className="btn-secondary">Edit payment</button>
          )}
          {canDelete && (
            <button onClick={deleteInvoice} className="btn-danger">Delete invoice</button>
          )}
        </div>
      </div>

      {error && <div className="mb-4 rounded-md bg-red-50 p-3 text-sm text-red-700 border border-red-100">{error}</div>}
      {paymentEditing && (
        <form onSubmit={savePayment} className="card mb-6 max-w-md space-y-3">
          <label htmlFor="invoice-paid-amount" className="label">Total amount received</label>
          <input id="invoice-paid-amount" className="input" type="number" min="0" max={invoice.grand_total} step="0.01"
            value={paidAmount} onChange={(e) => setPaidAmount(e.target.value)} required />
          <p className="text-sm text-gray-500">Enter the total received so far. The remaining balance and status update automatically.</p>
          <div className="flex gap-2">
            <button type="submit" disabled={savingPayment} className="btn-primary">{savingPayment ? 'Saving...' : 'Save payment'}</button>
            <button type="button" onClick={() => setPaymentEditing(false)} className="btn-secondary">Close</button>
          </div>
        </form>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2">
          <div className="card">
            <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4 mb-6 border-b border-gray-200 pb-4">
              <div>
                <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wider">From</h2>
                <p className="font-medium">{selectedCompanyName()}</p>
              </div>
              <div className="text-right">
                <p className="text-lg font-bold text-gray-900">{invoice.invoice_number ?? '—'}</p>
                <p className="text-sm text-gray-500">{formatDate(invoice.invoice_date)}</p>
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div>
                <h3 className="text-sm font-semibold text-gray-700 uppercase tracking-wider mb-3">Bill to</h3>
                <p className="text-gray-700">{invoice.customer_name_snapshot}</p>
                {invoice.customer_gstin_snapshot && <p className="text-sm text-gray-500">GSTIN: {invoice.customer_gstin_snapshot}</p>}
                {invoice.billing_address_snapshot && Object.keys(invoice.billing_address_snapshot).length > 0 && (
                  <p className="text-sm text-gray-500 whitespace-pre-line">{formatAddress(invoice.billing_address_snapshot)}</p>
                )}
              </div>
              <div>
                <h3 className="text-sm font-semibold text-gray-700 uppercase tracking-wider mb-3">Ship to</h3>
                <p className="text-gray-700">{invoice.customer_name_snapshot}</p>
                {invoice.shipping_address_snapshot && Object.keys(invoice.shipping_address_snapshot).length > 0 && (
                  <p className="text-sm text-gray-500 whitespace-pre-line">{formatAddress(invoice.shipping_address_snapshot)}</p>
                )}
              </div>
            </div>
          </div>

          <div className="card mt-6">
            <table className="w-full text-sm">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 border-b">Item</th>
                  <th className="px-4 py-3 text-right text-xs font-semibold text-gray-500 border-b">Qty</th>
                  <th className="px-4 py-3 text-right text-xs font-semibold text-gray-500 border-b">Unit price</th>
                  <th className="px-4 py-3 text-right text-xs font-semibold text-gray-500 border-b">Tax %</th>
                  <th className="px-4 py-3 text-right text-xs font-semibold text-gray-500 border-b">Amount</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {(invoice.lines ?? []).map((line: any, i: number) => (
                  <tr key={i} className="hover:bg-gray-50">
                    <td className="px-4 py-3">
                      <p className="font-medium">{line.item_name_snapshot || line.item_name}</p>
                      {line.sku_snapshot && <p className="text-xs text-gray-500">SKU: {line.sku_snapshot}</p>}
                      {line.unit_name_snapshot && <p className="text-xs text-gray-500">{line.unit_name_snapshot}</p>}
                    </td>
                    <td className="px-4 py-3 text-right">{Number(line.quantity).toFixed(2)}</td>
                    <td className="px-4 py-3 text-right">{formatMoney(line.unit_price)}</td>
                    <td className="px-4 py-3 text-right">{Number(line.tax_rate_percent).toFixed(2)}%</td>
                    <td className="px-4 py-3 text-right font-medium">{formatMoney(line.line_total ?? line.quantity * line.unit_price)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="card mt-6">
            <table className="w-full text-sm">
              <tbody className="divide-y divide-gray-100">
                <tr>
                  <td className="px-4 py-3 text-right text-gray-500">Subtotal</td>
                  <td className="px-4 py-3 text-right font-medium">{formatMoney(invoice.subtotal)}</td>
                </tr>
                <tr>
                  <td className="px-4 py-3 text-right text-gray-500">Discount</td>
                  <td className="px-4 py-3 text-right text-gray-600">-{formatMoney(invoice.discount_total)}</td>
                </tr>
                <tr>
                  <td className="px-4 py-3 text-right text-gray-500">CGST</td>
                  <td className="px-4 py-3 text-right">{formatMoney(invoice.cgst_total)}</td>
                </tr>
                <tr>
                  <td className="px-4 py-3 text-right text-gray-500">SGST</td>
                  <td className="px-4 py-3 text-right">{formatMoney(invoice.sgst_total)}</td>
                </tr>
                <tr>
                  <td className="px-4 py-3 text-right text-gray-500">IGST</td>
                  <td className="px-4 py-3 text-right">{formatMoney(invoice.igst_total)}</td>
                </tr>
                <tr>
                  <td className="px-4 py-3 text-right text-gray-500">Cess</td>
                  <td className="px-4 py-3 text-right">{formatMoney(invoice.cess_total)}</td>
                </tr>
                <tr>
                  <td className="px-4 py-3 text-right text-gray-500">Other charges</td>
                  <td className="px-4 py-3 text-right">{formatMoney(invoice.other_charges)}</td>
                </tr>
                <tr className="font-bold border-t border-gray-200 pt-4">
                  <td className="px-4 py-3 text-right text-gray-900">Grand total</td>
                  <td className="px-4 py-3 text-right text-brand-700 font-bold">{formatMoney(invoice.grand_total)}</td>
                </tr>
                <tr>
                  <td className="px-4 py-3 text-right text-gray-500">Paid</td>
                  <td className="px-4 py-3 text-right">{formatMoney(invoice.paid_total)}</td>
                </tr>
                <tr>
                  <td className="px-4 py-3 text-right text-gray-500">Balance due</td>
                  <td className="px-4 py-3 text-right font-medium">{formatMoney((invoice.grand_total ?? 0) - (invoice.paid_total ?? 0))}</td>
                </tr>
              </tbody>
            </table>
            {invoice.notes && (
              <div className="mt-4 p-3 bg-gray-50 rounded border border-gray-200">
                <p className="text-xs font-semibold text-gray-700">Notes</p>
                <p className="text-sm text-gray-700 mt-1">{invoice.notes}</p>
              </div>
            )}
            {invoice.terms && (
              <div className="mt-3 p-3 bg-gray-50 rounded border border-gray-200">
                <p className="text-xs font-semibold text-gray-700">Terms</p>
                <p className="text-sm text-gray-700 mt-1">{invoice.terms}</p>
              </div>
            )}
          </div>
        </div>

        <div className="lg:col-span-1">
          <div className="card">
            <h3 className="text-sm font-semibold text-gray-700 mb-4">Summary</h3>
            <div className="space-y-3 text-sm">
              <div className="flex justify-between"><span className="text-gray-500">Status</span><span className="font-medium">{invoice.status}</span></div>
              <div className="flex justify-between"><span className="text-gray-500">Payment status</span><span className="font-medium">{invoice.payment_status}</span></div>
              <div className="flex justify-between"><span className="text-gray-500">Grand total</span><span className="font-medium">{formatMoney(invoice.grand_total)}</span></div>
              <div className="flex justify-between"><span className="text-gray-500">Balance due</span><span className="font-medium text-gray-600">{formatMoney((invoice.grand_total ?? 0) - (invoice.paid_total ?? 0))}</span></div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )

  function selectedCompanyName(): string {
    return selectedCompany?.name ?? 'My Company'
  }
}



