import { useEffect, useState } from 'react'
import { NavLink, Route, Routes, useLocation } from 'react-router-dom'
import Dashboard from './pages/Dashboard'
import Calculator from './pages/Calculator'
import Planner from './pages/Planner'
import Plans from './pages/Plans'
import Networks from './pages/Networks'
import IpAddresses from './pages/IpAddresses'
import Departments from './pages/Departments'
import Login from './pages/Login'
import { clearSession, getUser, onAuthChange, type AuthUser } from './auth'
import { ConfirmHost, Icon, ThemeToggle, Tip, ToastHost, type IconName } from './ui'

interface NavItem {
  to: string
  label: string
  icon: IconName
  end?: boolean
}

const NAV_SECTIONS: { title: string; items: NavItem[]; ifAdmin?: boolean; ifOperator?: boolean }[] = [
  {
    title: 'Overview',
    items: [
      { to: '/', label: 'Dashboard', icon: 'dashboard', end: true },
    ],
  },
  {
    title: 'Planning',
    items: [
      { to: '/calculator', label: 'Calculator', icon: 'calculator' },
      { to: '/planner', label: 'VLSM Planner', icon: 'planner' },
      { to: '/plans', label: 'Allocation Plans', icon: 'plans' },
    ],
  },
  {
    title: 'Inventory',
    items: [
      { to: '/networks', label: 'Networks', icon: 'network' },
      { to: '/ip-addresses', label: 'IP Addresses', icon: 'ip' },
      { to: '/departments', label: 'Departments', icon: 'users' },
    ],
  },
]

const TITLES: Record<string, string> = {
  '/': 'Dashboard',
  '/calculator': 'Subnet calculator',
  '/planner': 'VLSM planner',
  '/plans': 'Allocation plans',
  '/networks': 'Networks',
  '/ip-addresses': 'IP addresses',
  '/departments': 'Departments',
}

function pageTitle(pathname: string): string {
  if (TITLES[pathname]) return TITLES[pathname]
  const base = '/' + pathname.split('/')[1]
  return TITLES[base] ?? 'NetSpace IPAM'
}

export default function App() {
  const { pathname } = useLocation()
  const [user, setUser] = useState<AuthUser | null>(getUser())

  // keep the shell in sync with direct clearSession() calls (401 auto-logout)
  useEffect(() => onAuthChange(setUser), [])

  if (!user) {
    return <Login onSignedIn={setUser} />
  }

  return (
    <div className="app-shell">
      <aside className="sidebar no-print">
        <div className="brand">
          <span className="brand-mark">
            <Icon name="network" size={16} />
          </span>
          NetSpace <small>IPAM</small>
        </div>
        <nav>
          {NAV_SECTIONS.filter((section) => {
            if (section.ifAdmin && user?.role !== 'admin') return false
            if (section.ifOperator && user?.role !== 'operator' && user?.role !== 'admin') return false
            return true
          }).map((section) => (
            <div key={section.title}>
              <div className="side-section">{section.title}</div>
              {section.items.map((item) => (
                <NavLink
                  key={item.to}
                  to={item.to}
                  end={item.end}
                  className={({ isActive }) => (isActive ? 'nav-link active' : 'nav-link')}
                >
                  <Icon name={item.icon} size={16} />
                  {item.label}
                </NavLink>
              ))}
            </div>
          ))}
        </nav>
        <div className="sidebar-foot">IPv4 · IPv6 · VLSM</div>
      </aside>
      <div className="app-main">
        <header className="topbar no-print">
          <span className="topbar-title">{pageTitle(pathname)}</span>
          <div className="action-row">
            <span className="role-badge" title={`Signed in as ${user.username}`}>
              <span className="role-username">{user.username}</span>
              <span className={`badge role-${user.role}`}>{user.role}</span>
            </span>
            <ThemeToggle />
            <Tip content="Print the current view">
              <button className="btn subtle small" onClick={() => window.print()}>
                <Icon name="print" size={13} /> Print
              </button>
            </Tip>
            <Tip content="Sign out">
              <button
                className="btn subtle small"
                onClick={() => clearSession()}
                aria-label="Sign out"
              >
                <Icon name="power" size={13} /> Sign out
              </button>
            </Tip>
          </div>
        </header>
        <main className="content">
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/calculator" element={<Calculator />} />
            <Route path="/planner" element={<Planner />} />
            <Route path="/plans" element={<Plans />} />
            <Route path="/plans/:planId" element={<Plans />} />
            <Route path="/networks" element={<Networks />} />
            <Route path="/networks/:networkId" element={<Networks />} />
            <Route path="/ip-addresses" element={<IpAddresses />} />
            <Route path="/departments" element={<Departments />} />
            <Route path="*" element={<Dashboard />} />
          </Routes>
        </main>
      </div>
      <ToastHost />
      <ConfirmHost />
    </div>
  )
}
