import { useEffect, useState } from 'react'
import { useAuth } from '@/context/AuthContext'
import api from '@/api/index'
import { Loader2, Save, X, Plus, Users, ShieldCheck, Mail, Trash2, Edit2, RefreshCcw } from 'lucide-react'

export default function Members() {
  const { isOwner, permissions } = useAuth()
  const canManage = permissions.includes('settings.users.manage')

  if (!canManage) {
    return (
      <div className="p-6 card">
        <h1 className="text-2xl font-bold text-gray-900 mb-2">Members</h1>
        <p className="text-gray-500">You do not have permission to manage members.</p>
      </div>
    )
  }

  const [roles, setRoles] = useState<any[]>([])
  const [members, setMembers] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')

  const [inviteOpen, setInviteOpen] = useState(false)
  const [inviteForm, setInviteForm] = useState({ name: '', email: '', password: '', role_id: '' })

  useEffect(() => {
    load()
  }, [])

  const load = async () => {
    setLoading(true)
    try {
      const [r, m] = await Promise.all([api.get('/roles'), api.get('/members')])
      setRoles(r.data as any[])
      setMembers(m.data as any[])
    } catch (e: any) {
      setError(e.message || 'Failed to load members')
    } finally {
      setLoading(false)
    }
  }

  const invite = async () => {
    setError('')
    setSaving(true)
    try {
      await api.post('/members/add', { name: inviteForm.name, email: inviteForm.email, password: inviteForm.password, role_id: inviteForm.role_id })
      setSuccess('Member added')
      setSaving(false)
      setInviteOpen(false)
      load()
    } catch (e: any) {
      setError(e.message || 'Add member failed')
      setSaving(false)
    }
  }

  const changeRole = async (membershipId: string, roleId: string) => {
    try {
      await api.patch(`/members/${membershipId}/role`, { role_id: roleId })
      setSuccess('Role updated')
      load()
    } catch (e: any) {
      setError(e.message || 'Role change failed')
    }
  }

  const removeMember = async (membershipId: string) => {
    if (!window.confirm('Remove this member?')) return
    try {
      await api.delete(`/members/${membershipId}`)
      setSuccess('Member removed')
      load()
    } catch (e: any) {
      setError(e.message || 'Remove failed')
    }
  }

  return (
    <div className="p-6">
      <div className="flex flex-col md:flex-row md:items-center justify-between mb-6 gap-3">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Members</h1>
          <p className="text-gray-500">Manage staff and their roles in this company.</p>
        </div>
        <button onClick={() => setInviteOpen(true)} className="btn-primary flex items-center gap-2">
          <Plus className="w-4 h-4" /> Add member
        </button>
      </div>

      {error && <div className="mb-4 rounded-md bg-red-50 p-3 text-sm text-red-700 border border-red-100">{error}</div>}
      {success && <div className="mb-4 rounded-md bg-green-50 p-3 text-sm text-green-700 border border-green-100">{success}</div>}

      <div className="card">
        <div className="overflow-x-auto">
          <table className="min-w-full">
            <thead>
              <tr>
                <th>Name</th>
                <th className="text-center">Email</th>
                <th className="text-center">Role(s)</th>
                <th className="text-center">Status</th>
                <th className="text-center">Owner</th>
                <th className="text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr><td colSpan={6} className="p-4 text-center"><Loader2 className="w-5 h-5 animate-spin" /> Loading...</td></tr>
              ) : members.length === 0 ? (
                <tr><td colSpan={6} className="p-4 text-center text-gray-400">No members found.</td></tr>
              ) : (
                members.map((m) => (
                  <tr key={m.membership_id} className="border-b border-gray-100 hover:bg-gray-50">
                    <td className="font-medium">{m.full_name}</td>
                    <td className="text-center text-gray-600 text-sm">{m.email}</td>
                    <td className="text-center text-sm">{m.roles.join(', ') || '—'}</td>
                    <td className="text-center">
                      <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium ${m.status === 'active' ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-700'}`}>
                        {m.status.charAt(0).toUpperCase() + m.status.slice(1)}
                      </span>
                    </td>
                    <td className="text-center">{m.is_owner ? 'Yes' : 'No'}</td>
                    <td className="text-right">
                      <select
                        className="input input-sm border border-gray-300 rounded px-2 py-1"
                        value={m.roles[0] || ''}
                        onChange={(e) => changeRole(m.membership_id, e.target.value)}
                      >
                        <option value="">Change role</option>
                        {roles.map((r) => (
                          <option key={r.id} value={r.id}>{r.name}</option>
                        ))}
                      </select>
                      {!m.is_owner && (
                        <button onClick={() => removeMember(m.membership_id)} className="text-red-500 hover:text-red-700 ml-2 text-sm"><Trash2 className="w-4 h-4" /></button>
                      )}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {inviteOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center" onClick={(e) => { if (e.target === e.currentTarget) setInviteOpen(false) }}>
          <div className="fixed inset-0 z-40 bg-black/40 backdrop-blur-sm" onClick={() => setInviteOpen(false)} />
          <div className="relative z-50 bg-white rounded-xl shadow-lg w-full max-w-md p-6 border border-gray-200">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-bold text-gray-900">Add member</h3>
              <button onClick={() => setInviteOpen(false)} className="text-gray-400 hover:text-gray-600"><X className="w-5 h-5" /></button>
            </div>
            {error && <div className="mb-3 rounded-md bg-red-50 p-2 text-sm text-red-700">{error}</div>}
            {success && <div className="mb-3 rounded-md bg-green-50 p-2 text-sm text-green-700">{success}</div>}
            <form onSubmit={(e) => { e.preventDefault(); invite() }} className="space-y-3">
              <div>
                <label className="label">Full name *</label>
                <input className="input" value={inviteForm.name} onChange={(e) => setInviteForm({ ...inviteForm, name: e.target.value })} required />
              </div>
              <div>
                <label className="label">Email *</label>
                <input className="input" type="email" value={inviteForm.email} onChange={(e) => setInviteForm({ ...inviteForm, email: e.target.value })} required />
              </div>
              <div>
                <label className="label">Password *</label>
                <input className="input" type="password" value={inviteForm.password} onChange={(e) => setInviteForm({ ...inviteForm, password: e.target.value })} required />
                <p className="text-xs text-gray-500 mt-1">At least 10 characters</p>
              </div>
              <div>
                <label className="label">Role *</label>
                <select className="input" value={inviteForm.role_id} onChange={(e) => setInviteForm({ ...inviteForm, role_id: e.target.value })} required>
                  <option value="">Select role</option>
                  {roles.map((r) => (
                    <option key={r.id} value={r.id}>{r.name}</option>
                  ))}
                </select>
              </div>
              <div className="flex justify-end gap-2 pt-2">
                <button type="button" onClick={() => setInviteOpen(false)} className="btn-secondary">Cancel</button>
                <button type="submit" className="btn-primary" disabled={saving}>{saving ? <Loader2 className="w-4 h-4" /> : <Save className="w-4 h-4" />} Add</button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}



