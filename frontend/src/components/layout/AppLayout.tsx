import { Building2, FileSearch, Settings2, ShieldCheck } from 'lucide-react'
import { NavLink, Outlet, useLocation } from 'react-router-dom'

import { useLanguage } from '../../lib/language'
import { cn } from '../../lib/utils'

function getCopy(uiLanguage: 'en' | 'fr') {
  if (uiLanguage === 'fr') {
    return {
      nav: {
        documents: 'Documents',
        reviews: 'Revues',
        clients: 'Clients',
        settings: 'Parametres',
      },
      page: {
        documents: 'Documents',
        reviews: 'Revues',
        clients: 'Clients',
        settings: 'Parametres',
        document: 'Document',
      },
      primaryNav: 'Navigation principale',
      mobileNav: 'Navigation mobile',
      workspace: 'Espace de travail',
    }
  }

  return {
    nav: {
      documents: 'Documents',
      reviews: 'Reviews',
      clients: 'Clients',
      settings: 'Settings',
    },
    page: {
      documents: 'Documents',
      reviews: 'Reviews',
      clients: 'Clients',
      settings: 'Settings',
      document: 'Document',
    },
    primaryNav: 'Primary navigation',
    mobileNav: 'Mobile navigation',
    workspace: 'Workspace',
  }
}

function getPageTitle(pathname: string, uiLanguage: 'en' | 'fr') {
  const copy = getCopy(uiLanguage)
  if (pathname.startsWith('/reviews')) return copy.page.reviews
  if (pathname.startsWith('/clients')) return copy.page.clients
  if (pathname.startsWith('/settings')) return copy.page.settings
  if (pathname.startsWith('/documents/')) return copy.page.document
  return copy.page.documents
}

export function AppLayout() {
  const location = useLocation()
  const { uiLanguage } = useLanguage()
  const copy = getCopy(uiLanguage)
  const navItems = [
    { to: '/', label: copy.nav.documents, icon: FileSearch, end: true },
    { to: '/reviews', label: copy.nav.reviews, icon: ShieldCheck, end: false },
    { to: '/clients', label: copy.nav.clients, icon: Building2, end: false },
    { to: '/settings', label: copy.nav.settings, icon: Settings2, end: false },
  ] as const

  return (
    <div className="app-shell">
      <div className="mx-auto flex min-h-screen max-w-[1600px]">
        <aside className="hidden w-[240px] shrink-0 border-r border-sidebar-border/90 bg-sidebar/90 px-5 py-6 lg:block">
          <div className="space-y-8">
            <div className="space-y-1">
              <p className="text-xl font-semibold tracking-tight">Veltar</p>
              <p className="font-mono text-[11px] uppercase tracking-[0.2em] text-muted-foreground">
                export control
              </p>
            </div>

            <nav className="space-y-1.5" aria-label={copy.primaryNav}>
              {navItems.map((item) => (
                <NavLink
                  key={item.to}
                  to={item.to}
                  end={item.end}
                  className={({ isActive }) =>
                    cn(
                      'flex items-center gap-3 rounded-[18px] px-3 py-2.5 text-sm font-medium transition-colors',
                      isActive ? 'bg-primary text-primary-foreground' : 'text-muted-foreground hover:bg-secondary/75 hover:text-foreground',
                    )
                  }
                >
                  <item.icon className="h-4 w-4" />
                  {item.label}
                </NavLink>
              ))}
            </nav>
          </div>
        </aside>

        <div className="min-w-0 flex-1">
          <header className="sticky top-0 z-30 border-b border-border/70 bg-background/92 backdrop-blur-xl">
            <div className="px-4 py-4 sm:px-6 lg:px-8">
              <div className="flex flex-col gap-3">
                <div className="lg:hidden">
                  <p className="text-lg font-semibold tracking-tight">Veltar</p>
                </div>

                <div className="flex items-end justify-between gap-4">
                  <div>
                    <p className="font-mono text-[11px] uppercase tracking-[0.2em] text-muted-foreground">
                      {copy.workspace}
                    </p>
                    <h1 className="mt-1 text-2xl font-semibold tracking-tight text-foreground">
                      {getPageTitle(location.pathname, uiLanguage)}
                    </h1>
                  </div>
                </div>

                <nav className="flex gap-2 overflow-x-auto pb-1 lg:hidden" aria-label={copy.mobileNav}>
                  {navItems.map((item) => (
                    <NavLink
                      key={item.to}
                      to={item.to}
                      end={item.end}
                      className={({ isActive }) =>
                        cn(
                          'shrink-0 rounded-full border px-3 py-2 font-mono text-[11px] uppercase tracking-[0.16em] transition-colors',
                          isActive
                            ? 'border-primary bg-primary text-primary-foreground'
                            : 'border-border bg-surface text-muted-foreground',
                        )
                      }
                    >
                      {item.label}
                    </NavLink>
                  ))}
                </nav>
              </div>
            </div>
          </header>

          <main className="px-4 py-6 sm:px-6 lg:px-8">
            <Outlet />
          </main>
        </div>
      </div>
    </div>
  )
}
