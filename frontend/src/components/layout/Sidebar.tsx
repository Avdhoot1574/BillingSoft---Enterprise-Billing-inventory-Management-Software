import { Link, useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from '@/context/AuthContext'
import { useSidebar } from '@/context/SidebarContext'
import {
  LayoutDashboard,
  FileText,
  Users,
  Package,
  Square,
  Percent,
  Building,
  Settings,
  ShieldCheck,
  Plus,
  LogOut,
  ChevronRight,
  RefreshCcw,
  ChevronLeft,
  X,
} from 'lucide-react'

type NavItem = {
  label: string
  href: string
  icon: React.ElementType
  permission?: string
  adminOnly?: boolean
}

const NAV_ITEMS: NavItem[] = [
  { label: 'Dashboard', href: '/dashboard', icon: LayoutDashboard },
  { label: 'Invoices', href: '/invoices', icon: FileText, permission: 'sales.invoice.read' },
  { label: 'Create Invoice', href: '/invoices/create', icon: Plus, permission: 'sales.invoice.create' },
  { label: 'Parties', href: '/parties', icon: Users, permission: 'parties.read' },
  { label: 'Items', href: '/items', icon: Package, permission: 'items.read' },
  { label: 'Units', href: '/units', icon: Square, permission: 'items.read' },
  { label: 'Categories', href: '/categories', icon: LayoutDashboard, permission: 'items.read' },
  { label: 'Tax Rates', href: '/tax-rates', icon: Percent, permission: 'items.read' },
  { label: 'Warehouses', href: '/warehouses', icon: Building, permission: 'inventory.read' },
  { label: 'Unit Conversion', href: '/unit-conversions', icon: RefreshCcw, permission: 'inventory.adjust' },
  { label: 'Company Settings', href: '/settings/company', icon: Settings, permission: 'settings.company.read' },
  { label: 'Members', href: '/members', icon: ShieldCheck, adminOnly: true },
]

export default function Sidebar() {
  const { permissions, isOwner, logout, selectedCompany } = useAuth()
  const { collapsed, mobileOpen, toggleCollapse, toggleMobile } = useSidebar()
  const location = useLocation()
  const navigate = useNavigate()

  const visibleItems = NAV_ITEMS.filter((item) => {
    if (item.adminOnly && !isOwner) return false
    if (item.permission && !permissions.includes(item.permission)) return false
    return true
  })

  return (
    <>
      {/* Mobile backdrop */}
      {mobileOpen && (
        <div
          className="fixed inset-0 z-40 bg-slate-900/40 backdrop-blur-sm md:hidden"
          onClick={toggleMobile}
        />
      )}

      <aside
        className={`flex flex-col h-full fixed inset-y-0 left-0 z-50 bg-white border-r border-slate-200 transition-all duration-500 ease-in-out ${
          collapsed ? 'w-16' : 'w-64'
        } ${mobileOpen ? 'translate-x-0' : '-translate-x-full md:translate-x-0'}`}
      >
        {/* Top brand + controls */}
        <div className="flex h-16 items-center justify-between px-3 border-b border-slate-200 bg-white flex-shrink-0">
          {!collapsed && (
            <Link to="/dashboard" className="flex items-center gap-2 group">
              <div className="w-8 h-8 rounded-xl bg-brand-50 flex items-center justify-center group-hover:bg-brand-100 transition-colors">
                <Building className="w-5 h-5 text-brand-600" />
              </div>
              <span className="font-bold text-slate-900 tracking-tight">BillingSoft</span>
            </Link>
          )}
          <div className="flex items-center gap-1">
            {collapsed ? (
              <button
                onClick={toggleCollapse}
                className="w-8 h-8 rounded-xl hover:bg-slate-100 text-slate-600 hover:text-slate-900 transition-all flex items-center justify-center"
                title="Expand sidebar"
              >
                <ChevronRight className="w-4 h-4" />
              </button>
            ) : (
              <>
                <button
                  onClick={toggleMobile}
                  className="md:hidden w-8 h-8 rounded-xl hover:bg-slate-100 text-slate-600 hover:text-slate-900 transition-all flex items-center justify-center"
                  title="Close menu"
                >
                  <X className="w-4 h-4" />
                </button>
                <button
                  onClick={toggleCollapse}
                  className="w-8 h-8 rounded-xl hover:bg-slate-100 text-slate-600 hover:text-slate-900 transition-all flex items-center justify-center"
                  title="Collapse sidebar"
                >
                  <ChevronLeft className="w-4 h-4" />
                </button>
              </>
            )}
          </div>
        </div>

        {/* Scrollable middle section */}
        <div className="flex-1 overflow-y-auto sidebar-scrollbar px-1 py-2">
          {selectedCompany && !collapsed && (
            <div className="px-4 py-4 border-b border-slate-100 bg-slate-50/50 mb-2">
              <p className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider mb-1">Company</p>
              <p className="text-sm font-medium text-slate-900 truncate group-hover:underline">{selectedCompany.name}</p>
            </div>
          )}
          <nav className="space-y-0.5">
            {visibleItems.map((item) => {
              const isActive = location.pathname === item.href || location.pathname.startsWith(item.href + '/')
              return (
                <Link
                  key={item.href}
                  to={item.href}
                  onClick={toggleMobile}
                  className={`nav-link ${isActive ? 'nav-link-active' : 'nav-link-inactive'}`}
                >
                  <div className={`w-8 h-8 rounded-lg flex items-center justify-center transition-colors duration-200 ${
                    isActive ? 'bg-brand-100' : 'hover:bg-slate-50'
                  }`}>
                    <item.icon className={`w-5 h-5 ${isActive ? 'text-brand-600' : 'text-slate-500'}`} />
                  </div>
                  {!collapsed && item.label}
                  {!collapsed && isActive && <ChevronRight className="ml-auto w-3 h-3 text-slate-400" />}
                </Link>
              )
            })}
          </nav>
        </div>

        {/* Bottom sign out (fixed at bottom when not collapsed) */}
        <div className="px-2 py-2 border-t border-slate-200 bg-white/80 backdrop-blur-sm flex-shrink-0">
          <button
            onClick={logout}
            className="nav-link text-red-600 hover:bg-red-50 hover:text-red-700"
            title="Sign out"
          >
            <div className="w-8 h-8 rounded-lg flex items-center justify-center bg-red-50">
              <LogOut className="w-5 h-5 text-red-600" />
            </div>
            {!collapsed && <span>Sign out</span>}
          </button>
        </div>
      </aside>
    </>
  )
}
