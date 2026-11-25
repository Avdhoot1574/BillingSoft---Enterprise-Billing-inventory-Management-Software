import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '@/context/AuthContext'
import api, { Invoice } from '@/api/index'
import { formatDate, formatMoney } from '@/lib/format'
import { FileText, Users, Package, TrendingUp, ArrowRight } from 'lucide-react'

type DashboardSummary = {
  invoice_count: number | null
  party_count: number | null
  item_count: number | null
  posted_invoice_value: number | null
  recent_invoices: Invoice[] | null
}

type StatCard = {
  title: string
  value: string | number
  subtitle: string
  icon: React.ElementType
  color: string
}

export default function Dashboard() {
  const { permissions, selectedCompany } = useAuth()
  const navigate = useNavigate()
  const [summary, setSummary] = useState<DashboardSummary | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [updatedAt, setUpdatedAt] = useState<Date | null>(null)
  const [retryKey, setRetryKey] = useState(0)

  useEffect(() => {
    let active = true
    let controller: AbortController | null = null
    setLoading(true)
    setSummary(null)
    setError('')
    const refresh = async () => {
      if (!selectedCompany) return
      controller?.abort()
      const request = new AbortController()
      controller = request
      try {
        const res = await api.get<DashboardSummary>('/dashboard/summary', { signal: request.signal })
        if (!active || request.signal.aborted) return
        setSummary(res.data)
        setError('')
        setUpdatedAt(new Date())
      } catch (err: any) {
        if (!active || request.signal.aborted) return
        setSummary(null)
        setError(err.message || 'Dashboard data is unavailable')
      } finally {
        if (active && !request.signal.aborted) setLoading(false)
      }
    }
    const refreshWhenVisible = () => {
      if (document.visibilityState === 'visible') void refresh()
    }
    void refresh()
    const interval = window.setInterval(refreshWhenVisible, 15000)
    document.addEventListener('visibilitychange', refreshWhenVisible)
    window.addEventListener('focus', refreshWhenVisible)
    return () => {
      active = false
      controller?.abort()
      window.clearInterval(interval)
      document.removeEventListener('visibilitychange', refreshWhenVisible)
      window.removeEventListener('focus', refreshWhenVisible)
    }
  }, [selectedCompany?.id, retryKey])

  const canCreateInvoice = permissions.includes('sales.invoice.create')

  const cards: StatCard[] = [
    { title: 'Total Invoices', value: summary?.invoice_count ?? '—', subtitle: 'All sales documents', icon: FileText, color: 'bg-brand-500' },
    { title: 'Parties', value: summary?.party_count ?? '—', subtitle: 'Active customers & suppliers', icon: Users, color: 'bg-indigo-500' },
    { title: 'Items', value: summary?.item_count ?? '—', subtitle: 'Active catalog items', icon: Package, color: 'bg-emerald-500' },
    { title: 'Posted Invoice Value', value: summary?.posted_invoice_value == null ? '—' : formatMoney(summary.posted_invoice_value), subtitle: 'Excludes drafts & cancellations', icon: TrendingUp, color: 'bg-violet-500' },
  ]

  return (
    <div className="p-6 animate-fade-in">
      <div className="page-title">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 mb-1">Dashboard</h1>
          <p className="text-slate-500 text-sm">{selectedCompany?.name} — business overview</p>
        </div>
        <div className="flex gap-2">
          {canCreateInvoice && (
            <button
              onClick={() => navigate('/invoices/create')}
              className="btn-primary flex items-center gap-2 group"
            >
              Create Invoice <ArrowRight className="w-4 h-4 group-hover:translate-x-1 transition-transform" />
            </button>
          )}
        </div>
      </div>

      {error && <div role="alert" className="mb-5 rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-700">
        Dashboard data is unavailable: {error} <button type="button" onClick={() => setRetryKey((key) => key + 1)} className="ml-2 font-semibold underline">Retry</button>
      </div>}
      {updatedAt && !error && <p className="mb-4 text-right text-xs text-slate-400">Updated {updatedAt.toLocaleTimeString()}</p>}

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
        {cards.map((card, idx) => (
          <div
            key={card.title}
            className="stat-card animate-fade-in"
            style={{ animationDelay: `${idx * 0.1}s` }}
          >
            <div className={`stat-card-icon ${card.color}`}>
              <card.icon className="w-5 h-5" />
            </div>
            <div>
              <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider">{card.title}</p>
              <p className="text-xl font-bold text-slate-900">{card.value}</p>
              <p className="text-xs text-slate-400">{card.subtitle}</p>
            </div>
          </div>
        ))}
      </div>

      <div className="card">
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-lg font-semibold text-slate-900">Recent Invoices</h2>
          <a
            href="/invoices"
            className="inline-flex items-center gap-1.5 px-3 py-2 rounded-xl text-sm font-semibold text-brand-600 hover:bg-brand-50 transition-colors"
          >
            View All <ArrowRight className="w-3 h-3" />
          </a>
        </div>
        {loading ? (
          <div className="p-8 text-center text-slate-400 animate-pulse">Loading...</div>
        ) : summary?.recent_invoices == null ? (
          <div className="p-8 text-center text-slate-400">{error ? 'Recent invoices are unavailable.' : 'You do not have access to invoices.'}</div>
        ) : summary.recent_invoices.length === 0 ? (
          <div className="p-8 text-center text-slate-400">No invoices yet. Create your first invoice.</div>
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th className="w-1/3">Invoice #</th>
                  <th className="w-1/6">Date</th>
                  <th className="w-1/3">Customer</th>
                  <th className="w-1/6 text-right">Status</th>
                  <th className="w-1/6 text-right">Amount</th>
                </tr>
              </thead>
              <tbody>
                {summary.recent_invoices.map((inv) => (
                  <tr key={inv.id} className="hover:bg-slate-50 transition-colors">
                    <td className="font-medium">{inv.invoice_number ?? 'Draft'}</td>
                    <td className="text-slate-600 text-sm">{formatDate(inv.invoice_date)}</td>
                    <td>{inv.customer_name_snapshot}</td>
                    <td className="text-right">
                      <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium ${
                        inv.status === 'posted' ? 'bg-green-100 text-green-700' : inv.status === 'cancelled'
                          ? 'bg-red-100 text-red-700'
                          : 'bg-slate-100 text-slate-700'
                      }`}>
                        {inv.status.charAt(0).toUpperCase() + inv.status.slice(1)}
                      </span>
                    </td>
                    <td className="text-right font-medium">{formatMoney(inv.grand_total)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}
