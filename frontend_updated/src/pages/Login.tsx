import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '@/context/AuthContext'
import { ShieldCheck, Mail, Lock, ArrowRight } from 'lucide-react'

export default function Login() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
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
    <div className="min-h-screen flex items-center justify-center px-4">
      <div className="relative w-full max-w-2xl h-[600px] bg-white rounded-3xl shadow-2xl overflow-hidden">
        {/* Decorative gradient background */}
        <div className="absolute inset-0 bg-gradient-to-br from-brand-500 to-brand-700 opacity-90 z-0 animate-float" />
        <div className="absolute top-0 right-0 w-64 h-64 bg-brand-400/20 rounded-full blur-3xl -mr-32 -mt-32" />
        <div className="absolute bottom-0 left-0 w-72 h-72 bg-brand-500/10 rounded-full blur-3xl -mb-32 -ml-32" />

        {/* Brand header */}
        <div className="absolute top-8 left-8 z-10 flex items-center gap-2">
          <div className="w-8 h-8 rounded-xl bg-white/20 backdrop-blur flex items-center justify-center border border-white/30">
            <ShieldCheck className="w-5 h-5 text-white" />
          </div>
          <span className="text-white font-bold text-xl tracking-tight">BillingSoft</span>
        </div>

        {/* Form card */}
        <div className="relative z-10 w-full max-w-md mx-auto mt-20 animate-slide-up">
          <div className="text-center mb-8">
            <h2 className="text-2xl font-bold text-slate-900 mb-2">Welcome back</h2>
            <p className="text-slate-500 text-sm">Sign in to your billing account</p>
          </div>

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="label">Email address</label>
              <div className="relative">
                <Mail className="absolute left-3 top-3 w-4 h-4 text-slate-400" />
                <input
                  type="email"
                  className="input pl-10"
                  placeholder="you@company.com"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  required
                />
              </div>
            </div>
            <div className="relative">
              <label className="label">Password</label>
              <Lock className="absolute left-3 top-3 w-4 h-4 text-slate-400" />
              <input
                type="password"
                className="input pl-10"
                placeholder="••••••••"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
              />
            </div>
            {error && (
              <div className="rounded-lg bg-red-50 p-3 text-sm text-red-700 border border-red-100">
                {error}
              </div>
            )}
            <button
              type="submit"
              className="btn-primary w-full flex items-center justify-center gap-2"
              disabled={loading}
            >
              {loading ? (
                <>
                  <Loader className="w-4 h-4 animate-spin" /> Signing in...
                </>
              ) : (
                <>
                  Sign in <ArrowRight className="w-4 h-4" />
                </>
              )}
            </button>
          </form>

          <p className="mt-8 text-center text-sm text-slate-600">
            Don't have an account?{' '}
            <Link to="/register" className="font-semibold text-brand-600 hover:text-brand-700 transition">
              Create an account
            </Link>
          </p>
        </div>

        {/* Trust footer */}
        <div className="absolute bottom-8 left-8 right-8 z-10 flex items-center justify-between text-xs text-slate-500">
          <div className="flex items-center gap-2">
            <div className="w-2 h-2 rounded-full bg-green-500" />
            <span>Secure connection</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-2 h-2 rounded-full bg-green-500" />
            <span>Encrypted data</span>
          </div>
        </div>
      </div>
    </div>
  )
}

function Loader({ className }: { className?: string }) {
  return <div className={`inline-block w-4 h-4 border-2 border-current border-t-transparent rounded-full ${className}`} />
}
