import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '@/context/AuthContext'
import { ShieldCheck, User, Mail, Phone, Lock, Eye, EyeOff, ArrowRight, Zap, Boxes, Cloud, FileText, CheckCircle2 } from 'lucide-react'
import './Login.css'
import './Register.css'

export default function Register() {
  const [form, setForm] = useState({ full_name: '', email: '', phone: '', password: '' })
  const [showPassword, setShowPassword] = useState(false)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const { register } = useAuth()
  const navigate = useNavigate()

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      await register({ full_name: form.full_name, email: form.email, password: form.password, phone: form.phone || undefined })
      navigate('/login')
    } catch (err: any) {
      setError(err.message || 'Registration failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <main className="login-page register-page">
      <div className="login-stage register-stage">
        <div className="login-orb login-orb-one" aria-hidden="true" />
        <div className="login-orb login-orb-two" aria-hidden="true" />
        <div className="login-brand">
          <span className="login-brand-mark"><ShieldCheck aria-hidden="true" /></span>
          <span>BillingSoft</span>
        </div>

        <section className="login-intro" aria-labelledby="register-headline">
          <h1 id="register-headline">Your business starts<br /><span>here
            <svg className="login-underline" viewBox="0 0 280 18" aria-hidden="true"><path d="M5 10 Q120 -1 275 8 M55 16 Q150 3 270 11" /></svg>
          </span></h1>
          <p className="login-description">Create your account and bring your billing, inventory, and business details together in one place.</p>
          <ul className="login-features">
            <li><Zap aria-hidden="true" />Fast Invoicing</li>
            <li><Boxes aria-hidden="true" />Inventory Tracking</li>
            <li><ShieldCheck aria-hidden="true" />GST-Ready</li>
            <li><Cloud aria-hidden="true" />Secure Cloud Access</li>
          </ul>
          <div className="register-preview" aria-hidden="true">
            <div className="register-preview-icon"><FileText /></div>
            <div><strong>One place for your business</strong><span>Create a company after you sign in and start managing its work.</span></div>
            <CheckCircle2 className="register-preview-check" />
          </div>
        </section>

        <section className="login-card register-card" aria-labelledby="register-title">
          <header className="login-card-heading">
            <h2 id="register-title">Create account</h2>
            <p>Get started with BillingSoft</p>
          </header>
          <form onSubmit={handleSubmit} className="login-form">
            <div className="login-field">
              <label htmlFor="register-name">Full name</label>
              <div className="login-input-wrap">
                <User aria-hidden="true" />
                <input id="register-name" name="full_name" type="text" autoComplete="name" placeholder="John Doe"
                  value={form.full_name} onChange={(e) => setForm({ ...form, full_name: e.target.value })} required />
              </div>
            </div>
            <div className="login-field">
              <label htmlFor="register-email">Email address</label>
              <div className="login-input-wrap">
                <Mail aria-hidden="true" />
                <input id="register-email" name="email" type="email" autoComplete="email" placeholder="you@company.com"
                  value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} required />
              </div>
            </div>
            <div className="login-field">
              <label htmlFor="register-phone">Phone (optional)</label>
              <div className="login-input-wrap">
                <Phone aria-hidden="true" />
                <input id="register-phone" name="phone" type="tel" autoComplete="tel" placeholder="+91 98765 43210"
                  value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })} />
              </div>
            </div>
            <div className="login-field">
              <label htmlFor="register-password">Password</label>
              <div className="login-input-wrap">
                <Lock aria-hidden="true" />
                <input id="register-password" name="password" type={showPassword ? 'text' : 'password'} autoComplete="new-password" className="password-input"
                  placeholder="••••••••••" value={form.password}
                  onChange={(e) => setForm({ ...form, password: e.target.value })} required minLength={10} />
                <button type="button" className="password-toggle" onClick={() => setShowPassword((shown) => !shown)}
                  aria-label={showPassword ? 'Hide password' : 'Show password'} aria-pressed={showPassword}>
                  {showPassword ? <EyeOff aria-hidden="true" /> : <Eye aria-hidden="true" />}
                </button>
              </div>
              <p className="register-password-hint">At least 10 characters</p>
            </div>
            {error && <div className="login-error" role="alert">{error}</div>}
            <button type="submit" className="login-submit" disabled={loading} aria-busy={loading}>
              {loading ? <><Loader className="animate-spin" /> Creating account...</> : <>Create account <ArrowRight aria-hidden="true" /></>}
            </button>
          </form>
          <div className="login-divider" aria-hidden="true"><span /></div>
          <p className="login-register">Already have an account? <Link to="/login">Sign in</Link></p>
        </section>
      </div>
    </main>
  )
}

function Loader({ className }: { className?: string }) {
  return <div className={`inline-block w-4 h-4 border-2 border-current border-t-transparent rounded-full ${className}`} />
}
