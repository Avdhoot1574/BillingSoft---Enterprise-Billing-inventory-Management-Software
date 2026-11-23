import { createContext, useContext, useState, ReactNode } from 'react'

type SidebarContextType = {
  collapsed: boolean // desktop: slim vs full sidebar
  mobileOpen: boolean // mobile: sidebar overlay open vs closed
  toggleCollapse: () => void
  toggleMobile: () => void
  setCollapsed: (v: boolean) => void
  setMobileOpen: (v: boolean) => void
}

const SidebarContext = createContext<SidebarContextType | undefined>(undefined)

export function useSidebar() {
  const ctx = useContext(SidebarContext)
  if (!ctx) throw new Error('useSidebar must be used within SidebarProvider')
  return ctx
}

export function SidebarProvider({ children }: { children: ReactNode }) {
  const [collapsed, setCollapsed] = useState(false)
  const [mobileOpen, setMobileOpen] = useState(false)
  const toggleCollapse = () => setCollapsed((c) => !c)
  const toggleMobile = () => setMobileOpen((o) => !o)
  return (
    <SidebarContext.Provider value={{ collapsed, mobileOpen, toggleCollapse, toggleMobile, setCollapsed, setMobileOpen }}>
      {children}
    </SidebarContext.Provider>
  )
}
