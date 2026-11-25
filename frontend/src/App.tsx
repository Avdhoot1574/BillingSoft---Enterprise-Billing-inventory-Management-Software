import { useState } from 'react'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { useAuth } from '@/context/AuthContext'
import { AuthProvider } from '@/context/AuthContext'
import { SidebarProvider, useSidebar } from '@/context/SidebarContext'
import Sidebar from '@/components/layout/Sidebar'
import TopBar from '@/components/layout/TopBar'
import CreateCompanyDialog from '@/components/layout/CreateCompanyDialog'
import Login from '@/pages/Login'
import Register from '@/pages/Register'
import Dashboard from '@/pages/Dashboard'
import Invoices from '@/pages/Invoices'
import CreateInvoice from '@/pages/CreateInvoice'
import InvoiceView from '@/pages/InvoiceView'
import Parties from '@/pages/Parties'
import Items from '@/pages/Items'
import Units from '@/pages/Units'
import Categories from '@/pages/Categories'
import TaxRates from '@/pages/TaxRates'
import Warehouses from '@/pages/Warehouses'
import UnitConversions from '@/pages/UnitConversions'
import CompanySettings from '@/pages/CompanySettings'
import Members from '@/pages/Members'

function ProtectedRoute({ children }: { children: JSX.Element }) {
  const { isAuthenticated, loading } = useAuth()
  if (loading) {
    return (
      <div className="flex h-screen items-center justify-center">
        <div className="flex flex-col items-center gap-2">
          <div className="w-8 h-8 border-4 border-brand-200 rounded-full border-t-brand-600 animate-spin" />
          <p className="text-sm text-gray-500">Loading...</p>
        </div>
      </div>
    )
  }
  if (!isAuthenticated) return <Navigate to="/login" replace />
  return <div className="flex flex-col h-screen">{children}</div>
}

function AppShell() {
  const { collapsed } = useSidebar()
  const { selectedCompany } = useAuth()
  const [creatingCompany, setCreatingCompany] = useState(false)
  if (!selectedCompany) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-50">
        <p className="text-slate-600">Set up your first company to get started.</p>
        <CreateCompanyDialog required onClose={() => setCreatingCompany(false)} />
      </div>
    )
  }
  return (
    <div className="relative">
      <TopBar onCreateCompany={() => setCreatingCompany(true)} />
      <div className="flex flex-1 overflow-hidden">
        <Sidebar />
        <main key={selectedCompany.id} className={`flex-1 overflow-y-auto pt-16 pb-8 transition-all duration-300 ${
          collapsed ? 'md:pl-16' : 'md:pl-64'
        }`}>
          <Routes>
            <Route path="/" element={<Navigate to="/dashboard" replace />} />
            <Route path="dashboard" element={<Dashboard />} />
            <Route path="invoices" element={<Invoices />} />
            <Route path="invoices/create" element={<CreateInvoice />} />
            <Route path="invoices/:id" element={<InvoiceView />} />
            <Route path="invoices/:id/edit" element={<CreateInvoice />} />
            <Route path="parties" element={<Parties />} />
            <Route path="items" element={<Items />} />
            <Route path="units" element={<Units />} />
            <Route path="categories" element={<Categories />} />
            <Route path="tax-rates" element={<TaxRates />} />
            <Route path="warehouses" element={<Warehouses />} />
            <Route path="unit-conversions" element={<UnitConversions />} />
            <Route path="settings/company" element={<CompanySettings />} />
            <Route path="members" element={<Members />} />
          </Routes>
        </main>
      </div>
      {creatingCompany && <CreateCompanyDialog onClose={() => setCreatingCompany(false)} />}
    </div>
  )
}

export default function Root() {
  return (
    <AuthProvider>
      <SidebarProvider>
        <BrowserRouter>
          <Routes>
            <Route path="/login" element={<Login />} />
            <Route path="/register" element={<Register />} />
            <Route path="*" element={<ProtectedRoute><AppShell /></ProtectedRoute>} />
          </Routes>
        </BrowserRouter>
      </SidebarProvider>
    </AuthProvider>
  )
}
