import { X } from 'lucide-react'

type ModalProps = {
  open: boolean
  onClose: () => void
  title?: string
  className?: string
  children: React.ReactNode
}

export default function Modal({ open, onClose, title, className, children }: ModalProps) {
  if (!open) return null

  return (
    <div
      className="fixed inset-0 z-40 flex items-center justify-center"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose()
      }}
    >
      {/* Frosted backdrop — blurs only the page behind, never the modal content */}
      <div className="absolute inset-0 bg-black/40 backdrop-blur-sm" onClick={onClose} />
      {/* Modal content — isolated stacking context on top of the backdrop, scrollable when tall */}
      <div
        className={`relative z-50 w-full max-w-md max-h-[85vh] overflow-y-auto p-6 bg-white rounded-xl shadow-lg border border-gray-200 isolate ${className || ''}`}
      >
        {title && (
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-lg font-bold text-gray-900">{title}</h3>
            <button onClick={onClose} className="text-gray-400 hover:text-gray-600">
              <X className="w-5 h-5" />
            </button>
          </div>
        )}
        {children}
      </div>
    </div>
  )
}
