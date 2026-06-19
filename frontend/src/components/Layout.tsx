import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { Cpu, LogOut, Home, Database, Rocket, Activity } from 'lucide-react'

interface LayoutProps {
  children: React.ReactNode
  activePage?: string
}

const navItems = [
  { id: 'dashboard', label: 'Dashboard', icon: Home, path: '/dashboard' },
  { id: 'projects', label: 'Projects', icon: Database, path: '/dashboard' },
  { id: 'deployments', label: 'Deployments', icon: Rocket, path: '/deployments' },
  { id: 'monitoring', label: 'Monitoring', icon: Activity, path: '/monitoring' },
]

export default function Layout({ children, activePage = 'dashboard' }: LayoutProps) {
  const navigate = useNavigate()

  const handleLogout = () => {
    localStorage.removeItem('access_token')
    navigate('/login')
  }

  return (
    <div className="flex h-screen overflow-hidden" style={{ background: 'var(--color-bg-primary)' }}>
      {/* Sidebar */}
      <aside className="w-56 flex-shrink-0 flex flex-col border-r" style={{
        background: 'var(--color-bg-secondary)',
        borderColor: 'var(--color-border)',
      }}>
        {/* Logo */}
        <div className="flex items-center gap-3 px-5 py-5 border-b" style={{ borderColor: 'var(--color-border)' }}>
          <div className="flex items-center justify-center w-8 h-8 rounded-lg" style={{
            background: 'linear-gradient(135deg, #6366f1, #8b5cf6)',
          }}>
            <Cpu size={16} className="text-white" />
          </div>
          <div>
            <div className="text-sm font-bold" style={{ color: 'var(--color-text-primary)' }}>ML Platform</div>
            <div className="text-xs" style={{ color: 'var(--color-text-muted)' }}>Admin Console</div>
          </div>
        </div>

        {/* Navigation */}
        <nav className="flex-1 p-3 space-y-0.5">
          {navItems.map((item) => {
            const Icon = item.icon
            const isActive = activePage === item.id
            return (
              <Link
                key={item.id}
                to={item.path}
                className="flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all duration-150"
                style={{
                  background: isActive ? 'rgba(99,102,241,0.15)' : 'transparent',
                  color: isActive ? 'var(--color-accent-hover)' : 'var(--color-text-secondary)',
                  borderLeft: isActive ? '2px solid var(--color-accent)' : '2px solid transparent',
                }}
                onMouseEnter={(e) => {
                  if (!isActive) {
                    (e.currentTarget as HTMLElement).style.background = 'rgba(255,255,255,0.04)'
                    ;(e.currentTarget as HTMLElement).style.color = 'var(--color-text-primary)'
                  }
                }}
                onMouseLeave={(e) => {
                  if (!isActive) {
                    (e.currentTarget as HTMLElement).style.background = 'transparent'
                    ;(e.currentTarget as HTMLElement).style.color = 'var(--color-text-secondary)'
                  }
                }}
              >
                <Icon size={16} />
                {item.label}
              </Link>
            )
          })}
        </nav>

        {/* Logout */}
        <div className="p-3 border-t" style={{ borderColor: 'var(--color-border)' }}>
          <button
            id="logout-btn"
            onClick={handleLogout}
            className="flex items-center gap-3 w-full px-3 py-2.5 rounded-lg text-sm font-medium transition-all duration-150"
            style={{ color: 'var(--color-text-muted)' }}
            onMouseEnter={(e) => {
              (e.currentTarget as HTMLElement).style.background = 'rgba(239,68,68,0.1)'
              ;(e.currentTarget as HTMLElement).style.color = 'var(--color-error)'
            }}
            onMouseLeave={(e) => {
              (e.currentTarget as HTMLElement).style.background = 'transparent'
              ;(e.currentTarget as HTMLElement).style.color = 'var(--color-text-muted)'
            }}
          >
            <LogOut size={16} />
            Sign out
          </button>
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 overflow-y-auto">
        {children}
      </main>
    </div>
  )
}
