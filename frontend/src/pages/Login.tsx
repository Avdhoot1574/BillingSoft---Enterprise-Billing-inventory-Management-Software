import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '@/context/AuthContext'
import { ShieldCheck, Mail, Lock, Eye, EyeOff, ArrowRight, Zap, Boxes, Cloud, Check, LayoutDashboard, FileText, Users, BarChart3, Settings } from 'lucide-react'
import './Login.css'

export default function Login() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const { login } = useAuth()
  const navigate = useNavigate()

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      await login(email, password)
      navigate('/dashboard')
    } catch (err: any) {
      setError(err.message || 'Login failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <main className="login-page">
      <div className="login-stage">
        <div className="login-orb login-orb-one" aria-hidden="true" />
        <div className="login-orb login-orb-two" aria-hidden="true" />
        <div className="login-brand">
          <span className="login-brand-mark"><ShieldCheck aria-hidden="true" /></span>
          <span>BillingSoft</span>
        </div>

        <section className="login-intro" aria-labelledby="login-headline">
          <h1 id="login-headline">Smarter Billing for<br /><span>Modern Businesses
            <svg className="login-underline" viewBox="0 0 280 18" aria-hidden="true"><path d="M5 10 Q120 -1 275 8 M55 16 Q150 3 270 11" /></svg>
          </span></h1>
          <p className="login-description">A complete business management solution for invoicing, inventory, and growth &mdash; all in one place.</p>
          <ul className="login-features">
            <li><Zap aria-hidden="true" />Fast Invoicing</li>
            <li><Boxes aria-hidden="true" />Inventory Tracking</li>
            <li><ShieldCheck aria-hidden="true" />GST-Ready</li>
            <li><Cloud aria-hidden="true" />Secure Cloud Access</li>
          </ul>
          <DashboardIllustration />
        </section>

        <section className="login-card" aria-labelledby="login-title">
          <header className="login-card-heading">
            <h2 id="login-title">Welcome back</h2>
            <p>Sign in to your BillingSoft account</p>
          </header>
          <form onSubmit={handleSubmit} className="login-form">
            <div className="login-field">
              <label htmlFor="login-email">Email address</label>
              <div className="login-input-wrap">
                <Mail aria-hidden="true" />
                <input id="login-email" name="email" type="email" autoComplete="username"
                  placeholder="you@company.com" value={email}
                  onChange={(e) => setEmail(e.target.value)} required />
              </div>
            </div>
            <div className="login-field">
              <label htmlFor="login-password">Password</label>
              <div className="login-input-wrap">
                <Lock aria-hidden="true" />
                <input id="login-password" name="password" type={showPassword ? 'text' : 'password'} autoComplete="current-password" className="password-input"
                  placeholder="&#8226;&#8226;&#8226;&#8226;&#8226;&#8226;&#8226;&#8226;" value={password}
                  onChange={(e) => setPassword(e.target.value)} required />
                <button type="button" className="password-toggle" onClick={() => setShowPassword((shown) => !shown)}
                  aria-label={showPassword ? 'Hide password' : 'Show password'} aria-pressed={showPassword}>
                  {showPassword ? <EyeOff aria-hidden="true" /> : <Eye aria-hidden="true" />}
                </button>
              </div>
            </div>
            {error && <div className="login-error" role="alert">{error}</div>}
            <button type="submit" className="login-submit" disabled={loading} aria-busy={loading}>
              {loading ? <><Loader className="animate-spin" /> Signing in...</> : <>Sign in <ArrowRight aria-hidden="true" /></>}
            </button>
          </form>
          <div className="login-divider" aria-hidden="true"><span /></div>
          <p className="login-register">Don&apos;t have an account? <Link to="/register">Create an account</Link></p>
        </section>
      </div>
    </main>
  )
}

function Loader({ className }: { className?: string }) {
  return <div className={`inline-block w-4 h-4 border-2 border-current border-t-transparent rounded-full ${className}`} />
}

function DashboardIllustration() {
  return (
    <div className="login-illustration" aria-hidden="true">
      <div className="login-laptop">
        <div className="login-laptop-screen">
          <div className="login-mini-sidebar">
            <div className="login-mini-brand"><ShieldCheck />BillingSoft</div>
            <span className="is-active"><LayoutDashboard />Dashboard</span>
            <span><FileText />Invoices</span><span><Boxes />Inventory</span>
            <span><Users />Customers</span><span><BarChart3 />Reports</span><span><Settings />Settings</span>
          </div>
          <div className="login-mini-content">
            <div className="login-mini-heading">Dashboard<span>JD</span></div>
            <div className="login-mini-stats">
              <div><small>Total Sales</small><strong>&#8377; 4,82,300</strong></div>
              <div><small>Invoices</small><strong>128 <span>&#8599;</span></strong></div>
              <div><small>Stock Items</small><strong>1,246</strong></div>
            </div>
            <div className="login-mini-chart"><strong>Sales Overview</strong>
              <svg viewBox="0 0 360 120" preserveAspectRatio="none">
                <defs><linearGradient id="login-chart-fill" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#12c7b1" stopOpacity=".45" /><stop offset="100%" stopColor="#12c7b1" stopOpacity=".02" /></linearGradient></defs>
                <path d="M0 25H360 M0 60H360 M0 95H360" stroke="#e7f1f2" strokeDasharray="4 5" fill="none" />
                <path d="M0 96 C30 65 43 108 74 73 S114 48 145 65 S188 31 210 30 S245 54 267 24 S312 32 360 4 L360 120H0Z" fill="url(#login-chart-fill)" />
                <path d="M0 96 C30 65 43 108 74 73 S114 48 145 65 S188 31 210 30 S245 54 267 24 S312 32 360 4" fill="none" stroke="#00bda7" strokeWidth="3" />
                <circle cx="210" cy="30" r="5" fill="white" stroke="#00bda7" strokeWidth="2" />
              </svg>
            </div>
          </div>
        </div>
        <div className="login-laptop-base"><span /></div>
      </div>
      <div className="login-invoice-paper">
        <span className="login-invoice-check"><Check /></span>
        <strong>Invoice</strong><div className="login-paper-subtitle" />
        {[0, 1, 2, 3, 4].map((row) => <div className="login-paper-row" key={row}><i /><i /></div>)}
        <div className="login-paper-total" />
      </div>
      <div className="login-illustration-rays"><i /><i /><i /></div>
    </div>
  )
}
