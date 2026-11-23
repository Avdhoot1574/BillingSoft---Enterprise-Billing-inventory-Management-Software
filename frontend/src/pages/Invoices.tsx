import { useEffect, useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { useAuth } from '@/context/AuthContext'
import api from '@/api/index'
import { formatMoney, formatDate } from '@/lib/format'
import { FileText, Search, Plus, Loader2, Clock, Filter } from 'lucide-react'

type Status = 'draft' | 'posted' | 'cancelled' | ''

export default function Invoices() {
  const { permissions } = useAuth()
  const navigate = useNavigate()
  const [items, setItems] = useState<any[]>([])
  const [status, setStatus] = useState<Status>('')
  const [search, setSearch] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const canCreate = permissions.includes('sales.invoice.create')
  const canRead = permissions.includes('sales.invoice.read')

  useEffect(() => {
    load()
  }, [status, search])

  const load = async () => {
    if (!canRead) return
    setLoading(true)
    try {
      const res = await api.get('/invoices', { params: { status: status || undefined, limit: 100 } })
      setItems(res.data as any[])
    } catch (e: any) {
      setError(e.message || 'Failed to load invoices')
    } finally {
      setLoading(false)
    }
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
          <h1 className="text-2xl font-bold text-gray-900">Sales Invoices</h1>
          <p className="text-gray-500">Create, view and manage sales invoices.</p>
        </div>
        <div className="flex gap-2">
          <select value={status} onChange={(e) => setStatus(e.target.value as Status)} className="input text-xs border border-gray-300 rounded px-2 py-1.5">
            <option value="">All statuses</option>
            <option value="draft">Draft</option>
            <option value="posted">Posted</option>
            <option value="cancelled">Cancelled</option>
          </select>
          {canCreate && (
            <Link to="/invoices/create"><button className="btn-primary flex items-center gap-2"><Plus className="w-4 h-4" /> Create Invoice</button></Link>
          )}
        </div>
      </div>

      {error && <div className="mb-4 rounded-md bg-red-50 p-3 text-sm text-red-700">{error}</div>}

      <div className="card">
        <div className="overflow-x-auto">
          <table className="min-w-full">
            <thead>
              <tr>
                <th>Invoice #</th>
                <th className="text-center">Date</th>
                <th>Customer</th>
                <th className="text-center">Status</th>
                <th className="text-right">Grand total</th>
                <th className="text-right">Paid</th>
                <th className="text-right">Balance</th>
                <th className="text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr><td colSpan={8} className="p-4 text-center"><Loader2 className="w-5 h-5 animate-spin" /> Loading...</td></tr>
              ) : items.length === 0 ? (
                <tr><td colSpan={8} className="p-4 text-center text-gray-400">No invoices found.</td></tr>
              ) : (
                items.filter((inv) => {
                  if (search) {
                    const q = search.toLowerCase()
                    return (inv.invoice_number ?? '').toLowerCase().includes(q) || inv.customer_name_snapshot.toLowerCase().includes(q)
                  }
                  return true
                }).map((inv) => (
                  <tr key={inv.id} className="border-b border-gray-100 hover:bg-gray-50">
                    <td className="font-medium">{inv.invoice_number ?? 'Draft'}</td>
                    <td className="text-center text-gray-600 text-sm">{formatDate(inv.invoice_date)}</td>
                    <td>{inv.customer_name_snapshot}</td>
                    <td className="text-center">
                      <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium ${STATUS_COLOR[inv.status] ?? 'bg-gray-100 text-gray-700'}`}>
                        {inv.status.charAt(0).toUpperCase() + inv.status.slice(1)}
                      </span>
                    </td>
                    <td className="text-right font-medium">{formatMoney(inv.grand_total)}</td>
                    <td className="text-right text-sm">{formatMoney(inv.paid_total)}</td>
                    <td className="text-right text-sm font-medium text-gray-600">{formatMoney((inv.grand_total ?? 0) - (inv.paid_total ?? 0))}</td>
                    <td className="text-right">
                      <Link to={`/invoices/${inv.id}`} className="text-brand-600 hover:underline text-sm">View</Link>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}



