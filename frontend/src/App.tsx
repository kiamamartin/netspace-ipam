import { NavLink, Route, Routes } from 'react-router-dom'
import Dashboard from './pages/Dashboard'
import Calculator from './pages/Calculator'
import Planner from './pages/Planner'
import Plans from './pages/Plans'
import Networks from './pages/Networks'
import IpAddresses from './pages/IpAddresses'
import Departments from './pages/Departments'

const NAV = [
  { to: '/', label: 'Dashboard', end: true },
  { to: '/calculator', label: 'Calculator' },
  { to: '/planner', label: 'VLSM Planner' },
  { to: '/plans', label: 'Allocation Plans' },
  { to: '/networks', label: 'Networks' },
  { to: '/ip-addresses', label: 'IP Addresses' },
  { to: '/departments', label: 'Departments' },
]

export default function App() {
  return (
    <div className="app-shell no-print">
      <aside className="sidebar no-print">
        <div className="brand">
          <span className="brand-mark">◧</span> NetSpace <small>IPAM</small>
        </div>
        <nav>
          {NAV.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) => (isActive ? 'nav-link active' : 'nav-link')}
            >
              {item.label}
            </NavLink>
          ))}
        </nav>
        <div className="sidebar-foot">IPv4 · IPv6 · VLSM</div>
      </aside>
      <div className="app-main">
        <header className="topbar no-print">
          <span className="topbar-title">Network address management</span>
          <button className="btn ghost" onClick={() => window.print()} title="Print current view">
            Print
          </button>
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
    </div>
  )
}
