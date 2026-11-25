import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '@/context/AuthContext'
import { useSidebar } from '@/context/SidebarContext'
import { Menu, User as UserIcon, LogOut, Building, Plus } from 'lucide-react'

export default function TopBar({ onCreateCompany }: { onCreateCompany: () => void }) {
  const { user, selectedCompany, companies, selectCompany, logout } = useAuth()
  const { toggleMobile } = useSidebar()
  const navigate = useNavigate()
  const [userMenuOpen, setUserMenuOpen] = useState(false)

  return (
    <header className="fixed top-0 left-0 right-0 z-30 h-16 bg-white/80 backdrop-blur-md border-b border-slate-200 flex items-center justify-between px-6">
      <div className="flex items-center gap-4">
        <button
          className="md:hidden w-9 h-9 rounded-xl flex items-center justify-center text-slate-600 hover:bg-slate-100 transition-all"
          onClick={toggleMobile}
        >
          <Menu className="w-5 h-5" />
        </button>
        <Link to="/dashboard" className="hidden md:flex items-center gap-2 group">
          <div className="w-7 h-7 rounded-xl bg-brand-50 flex items-center justify-center group-hover:bg-brand-100 transition-colors">
            <Building className="w-4 h-4 text-brand-600" />
          </div>
          <span className="font-bold text-slate-900 tracking-tight">BillingSoft</span>
        </Link>
      </div>

      <div className="flex items-center gap-4">
        <div className="flex items-center gap-2">
            <label htmlFor="company-switcher" className="sr-only">Company</label>
            <select
              id="company-switcher"
              value={selectedCompany?.id ?? ''}
              onChange={(e) => {
                const c = companies.find((x) => x.id === e.target.value)
                if (c) {
                  void selectCompany(c)
                  navigate('/dashboard')
                }
              }}
              className="max-w-32 sm:max-w-48 text-xs border border-slate-300 rounded-xl px-2.5 py-1.5 bg-white focus:ring-2 focus:ring-brand-500 outline-none transition-all"
            >
              {companies.map((c) => (
                <option key={c.id} value={c.id}>{c.name}</option>
              ))}
            </select>
            <button type="button" onClick={onCreateCompany} title="Create company" aria-label="Create company" className="flex items-center gap-1 rounded-xl border border-brand-200 px-2.5 py-1.5 text-xs font-semibold text-brand-700 hover:bg-brand-50">
              <Plus className="w-4 h-4" /><span className="hidden sm:inline">New company</span>
            </button>
          </div>
        <div className="relative">
          <button
            className="flex items-center gap-2 rounded-full px-3 py-1.5 text-sm font-medium bg-slate-100 hover:bg-slate-200 transition-all"
            onClick={() => setUserMenuOpen(!userMenuOpen)}
          >
            <UserIcon className="w-4 h-4" />
            <span className="hidden md:inline">{user?.full_name}</span>
          </button>
          {userMenuOpen && (
            <div className="absolute right-0 mt-2 w-48 rounded-2xl border border-slate-200 bg-white shadow-xl py-2 z-50 animate-fade-in">
              <p className="px-4 py-1.5 text-[10px] font-semibold text-slate-500 uppercase">{user?.email}</p>
              <hr className="my-1 border-slate-100" />
              <Link
                to="/settings/company"
                className="flex w-full items-center gap-3 px-4 py-2 text-sm text-slate-700 hover:bg-slate-50 transition-colors rounded-xl"
              >
                <UserIcon className="w-4 h-4 text-slate-500" />
                Profile
              </Link>
              <button
                onClick={logout}
                className="flex w-full items-center gap-3 px-4 py-2 text-sm text-red-600 hover:bg-red-50 transition-colors rounded-xl"
              >
                <LogOut className="w-4 h-4 text-red-600" />
                Sign out
              </button>
            </div>
          )}
        </div>
      </div>
    </header>
  )
}

