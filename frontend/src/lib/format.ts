import { format as dateFnsFormat, parseISO } from 'date-fns'

export function formatMoney(value: number | null | undefined): string {
  const n = value ?? 0
  return new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency: 'INR',
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(n)
}

export function formatNumber(value: number | null | undefined, decimals = 2): string {
  const n = value ?? 0
  return new Intl.NumberFormat('en-IN', {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  }).format(n)
}

export function formatDate(value: string | null | undefined): string {
  if (!value) return '-'
  try {
    return dateFnsFormat(parseISO(value), 'dd MMM yyyy')
  } catch {
    return value
  }
}

export function formatDateInput(value: string | null | undefined): string {
  if (!value) return ''
  return value.slice(0, 10)
}

export function capitalize(str: string): string {
  if (!str) return str
  return str.charAt(0).toUpperCase() + str.slice(1)
}
