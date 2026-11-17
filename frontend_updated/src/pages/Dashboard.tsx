import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '@/context/AuthContext'
import api from '@/api/index'
import { formatMoney } from '@/lib/format'
import { FileText, Users, Package, TrendingUp, Building, ArrowRight } from 'lucide-react'

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
  const [stats, setStats] = useState<{ invoices: number; parties: number; items: number; total: number }>({
    invoices: 0,
    parties: 0,
    items: 0,
    total: 0,
  })
  const [recent, setRecent] = useState<any[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let cancelled = false
    Promise.all([
      api.get('/invoices?limit=5').catch(() => ({ data: [] } as any)),
      api.get('/parties?limit=1').catch(() => ({ data: [] } as any)),
      api.get('/items?limit=1').catch(() => ({ data: [] } as any)),
    ])
      .then(([invRes, partyRes, itemRes]) => {
        if (cancelled) return
        const invoices = invRes.data as any[]
        const parties = partyRes.data as any[]
        const items = itemRes.data as any[]
        setRecent(invoices)
        setStats({
          invoices: invoices.length,
          parties: parties.length,
          items: items.length,
          total: invoices.reduce((s, inv) => s + (inv.grand_total ?? 0), 0),
        })
        setLoading(false)
      })
      .catch(() => setLoading(false))
    return () => {
      cancelled = true
    }
  }, [])

  const canCreateInvoice = permissions.includes('sales.invoice.create')

  const cards: StatCard[] = [
    { title: 'Total Invoices', value: stats.invoices, subtitle: 'Sales documents', icon: FileText, color: 'bg-brand-500' },
    { title: 'Parties', value: stats.parties, subtitle: 'Customers & suppliers', icon: Users, color: 'bg-indigo-500' },
    { title: 'Items', value: stats.items, subtitle: 'Catalog items', icon: Package, color: 'bg-emerald-500' },
    { title: 'Invoice Value', value: formatMoney(stats.total), subtitle: 'Grand total', icon: TrendingUp, color: 'bg-violet-500' },
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
        ) : recent.length === 0 ? (
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
                {recent.map((inv, idx) => (
                  <tr key={inv.id} className="hover:bg-slate-50 transition-colors">
                    <td className="font-medium">{inv.invoice_number ?? 'Draft'}</td>
                    <td className="text-slate-600 text-sm">{inv.invoice_date}</td>
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
