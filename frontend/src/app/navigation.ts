import { BarChart3, BookOpen, ClipboardList, MessageSquare, Settings } from 'lucide-react'
import type React from 'react'

export type ViewType = 'chat' | 'browser' | 'jobs' | 'dashboard' | 'settings'

export const APP_NAV_ITEMS: { view: ViewType; icon: React.ComponentType<{ className?: string }>; label: string }[] = [
  { view: 'chat', icon: MessageSquare, label: '聊天' },
  { view: 'browser', icon: BookOpen, label: '知识库' },
  { view: 'jobs', icon: ClipboardList, label: '任务' },
  { view: 'dashboard', icon: BarChart3, label: '指标' },
  { view: 'settings', icon: Settings, label: '设置' },
]
