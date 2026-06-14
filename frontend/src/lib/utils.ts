import { type ClassValue, clsx } from 'clsx'
import { twMerge } from 'tailwind-merge'

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export function formatTime(iso: string): string {
  const d = new Date(iso)
  const now = new Date()
  const diff = now.getTime() - d.getTime()
  const mins = Math.floor(diff / 60000)
  if (mins < 1) return '刚刚'
  if (mins < 60) return `${mins} 分钟前`
  const hours = Math.floor(mins / 60)
  if (hours < 24) return `${hours} 小时前`
  const days = Math.floor(hours / 24)
  if (days < 7) return `${days} 天前`
  return d.toLocaleDateString('zh-CN')
}

export function truncate(str: string, len: number): string {
  if (str.length <= len) return str
  return str.slice(0, len) + '…'
}

export function evidenceColor(level: string): string {
  switch (level) {
    case 'strong': return 'text-emerald-400'
    case 'moderate': return 'text-yellow-400'
    case 'weak': return 'text-orange-400'
    default: return 'text-red-400'
  }
}

export function evidenceLabel(level: string): string {
  const labels: Record<string, string> = {
    strong: '证据充分',
    moderate: '证据一般',
    weak: '证据较弱',
    none: '无证据',
  }
  return labels[level] || level
}
