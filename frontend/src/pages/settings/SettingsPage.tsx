import { useState, useEffect } from 'react'
import { toast } from 'sonner'
import { ScrollArea, Separator } from '@/components/ui'
import { PanelRightOpen, Save, AlertTriangle, Check, Loader2 } from 'lucide-react'
import * as api from '@/shared/api'
import { MASKED_SECRET_VALUE } from '@/shared/api'
import type { RuntimeSettings } from '@/shared/api'
import type { ViewType } from '@/app/navigation'
import AdminUsersPanel from '@/pages/settings/AdminUsersPanel'

interface SettingsPageProps {
  onOpenSidebar: () => void
  sidebarOpen: boolean
  onNavigate: (v: ViewType) => void
}

type SettingsKey = keyof RuntimeSettings
type SettingsGroup = {
  title: string
  keys: SettingsKey[]
}

const PHASE_LABELS: Record<SettingsKey, string> = {
  siliconflow_api_key: '硅基流动 API Key',
  siliconflow_base_url: '硅基流动 Base URL',
  embedding_model: 'Embedding 模型',
  llm_model: 'LLM 模型',
  llm_temperature: 'LLM 温度',
  tavily_api_key: 'Tavily API Key',
  api_key: '系统 API Key',
  chunk_size: 'Chunk 大小',
  chunk_overlap: 'Chunk 重叠',
  top_k_retrieval: 'Top-K 检索',
  top_k_rerank: 'Top-K 重排',
  enable_quality_check: '质量检查',
  enable_contextual_retrieval: 'Contextual Retrieval',
}

const GROUP_ORDER: SettingsGroup[] = [
  { title: 'API 密钥', keys: ['siliconflow_api_key', 'tavily_api_key', 'api_key'] },
  { title: '模型', keys: ['llm_model', 'embedding_model', 'llm_temperature', 'siliconflow_base_url'] },
  { title: '检索', keys: ['chunk_size', 'chunk_overlap', 'top_k_retrieval', 'top_k_rerank'] },
  { title: '质量', keys: ['enable_quality_check', 'enable_contextual_retrieval'] },
]

function numericFieldMin(key: SettingsKey): number {
  if (key === 'chunk_overlap') return 0
  return 1
}

function parseNumericFieldValue(key: SettingsKey, rawValue: string): number {
  const parsed = Number.parseInt(rawValue, 10)
  if (Number.isNaN(parsed)) return numericFieldMin(key)
  return Math.max(numericFieldMin(key), parsed)
}

export default function SettingsPage({ onOpenSidebar, sidebarOpen }: SettingsPageProps) {
  const [settings, setSettings] = useState<Partial<RuntimeSettings>>({})
  const [loading, setLoading] = useState(true)
  const [savingGroup, setSavingGroup] = useState<string | null>(null)
  const [savedGroup, setSavedGroup] = useState<string | null>(null)
  const [warnings, setWarnings] = useState<string[]>([])

  useEffect(() => {
    api.getSettings().then((data) => {
      setSettings(data)
      setLoading(false)
    }).catch((error) => {
      toast.error('设置加载失败', { description: String(error) })
      setLoading(false)
    })
  }, [])

  const handleChange = <K extends keyof RuntimeSettings>(key: K, value: RuntimeSettings[K]) => {
    setSettings((prev) => ({ ...prev, [key]: value }))
  }

  const handleSaveGroup = async (title: string, keys: SettingsKey[]) => {
    setSavingGroup(title)
    try {
      const payload = Object.fromEntries(keys.map((key) => [key, settings[key]])) as Partial<RuntimeSettings>
      const res = await api.updateSettings(payload)
      if (Object.prototype.hasOwnProperty.call(payload, 'api_key')) {
        const nextApiKey = payload.api_key?.trim() || ''
        if (nextApiKey && nextApiKey !== MASKED_SECRET_VALUE) localStorage.setItem('knowbase_api_key', nextApiKey)
        else if (!nextApiKey) localStorage.removeItem('knowbase_api_key')
      }
      setSavedGroup(title)
      const nextWarnings = res.warnings ?? []
      if (nextWarnings.length) {
        setWarnings((prev) => [...new Set([...prev, ...nextWarnings])])
      }
      toast.success(`${title}已保存`)
      setTimeout(() => {
        setSavedGroup((current) => current === title ? null : current)
      }, 2000)
    } catch (error) {
      toast.error('保存失败', { description: String(error) })
    }
    setSavingGroup((current) => current === title ? null : current)
  }

  const providerName = (() => {
    const baseUrl = String(settings.siliconflow_base_url || '').toLowerCase()
    if (baseUrl.includes('siliconflow')) return 'SiliconFlow'
    if (baseUrl.includes('openai')) return 'OpenAI Compatible'
    return '自定义网关'
  })()

  const modelFamily = (() => {
    const model = String(settings.llm_model || '').toLowerCase()
    if (model.includes('deepseek')) return 'DeepSeek'
    if (model.includes('gpt')) return 'GPT'
    if (model.includes('qwen')) return 'Qwen'
    return settings.llm_model || '未设置'
  })()

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full text-muted-foreground">
        <Loader2 className="h-5 w-5 animate-spin" />
      </div>
    )
  }

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-border px-4 py-3">
        <div className="flex items-center gap-2">
          {!sidebarOpen && (
            <button onClick={onOpenSidebar} className="p-1 rounded-md text-muted-foreground hover:text-foreground hover:bg-muted/50 transition-colors">
              <PanelRightOpen className="h-4 w-4" />
            </button>
          )}
          <h1 className="text-sm font-medium">设置</h1>
        </div>
      </div>

      <ScrollArea className="flex-1 p-4">
        <div className="max-w-2xl mx-auto space-y-6">
          {warnings.length > 0 && (
            <div className="rounded-lg border border-amber-500/30 bg-amber-500/10 p-3">
              <div className="flex items-start gap-2">
                <AlertTriangle className="h-4 w-4 text-amber-500 mt-0.5 shrink-0" />
                <div className="text-xs text-amber-600 dark:text-amber-400 space-y-1">
                  {warnings.map((w, i) => <p key={i}>{w}</p>)}
                </div>
              </div>
            </div>
          )}

          <AdminUsersPanel />

          {GROUP_ORDER.map((group) => (
            <div key={group.title}>
              <div className="mb-3 flex items-center justify-between">
                <h2 className="text-xs font-semibold text-muted-foreground tracking-wide uppercase">{group.title}</h2>
                <button
                  onClick={() => handleSaveGroup(group.title, group.keys)}
                  disabled={savingGroup === group.title}
                  className="flex items-center gap-1 text-2xs text-primary hover:text-primary/80 transition-colors disabled:opacity-50"
                >
                  {savingGroup === group.title ? (
                    <Loader2 className="h-3 w-3 animate-spin" />
                  ) : savedGroup === group.title ? (
                    <Check className="h-3 w-3" />
                  ) : (
                    <Save className="h-3 w-3" />
                  )}
                  {savedGroup === group.title ? '已保存' : `保存${group.title}设置`}
                </button>
              </div>
              <div className="space-y-4">
                {group.keys.map((key) => {
                  const value = settings[key]
                  const isBool = typeof value === 'boolean'
                  const isNum = typeof value === 'number'
                  const isSensitive = key.includes('api_key') || key.includes('token')

                  return (
                    <div key={key}>
                      <div className="mb-1">
                        <label className="text-xs font-medium text-foreground/80">{PHASE_LABELS[key]}</label>
                      </div>
                      {isBool ? (
                        <label className="flex items-center gap-2 cursor-pointer">
                          <input
                            type="checkbox"
                            checked={value}
                            onChange={(e) => handleChange(key, e.target.checked as RuntimeSettings[typeof key])}
                            aria-label={PHASE_LABELS[key]}
                            className="rounded border-border text-primary focus:ring-primary/30"
                          />
                          <span className="text-xs text-muted-foreground">{value ? '已开启' : '已关闭'}</span>
                        </label>
                      ) : isNum && key === 'llm_temperature' ? (
                        <div className="flex items-center gap-2">
                          <input
                            type="range"
                            min={0}
                            max={1}
                            step={0.05}
                            value={value}
                            onChange={(e) => handleChange(key, parseFloat(e.target.value) as RuntimeSettings[typeof key])}
                            aria-label={PHASE_LABELS[key]}
                            className="flex-1 accent-primary"
                          />
                          <span className="text-2xs text-muted-foreground font-mono w-8 text-right">{value}</span>
                        </div>
                      ) : isNum ? (
                        <input
                          type="number"
                          value={value}
                          min={numericFieldMin(key)}
                          max={10000}
                          onChange={(e) => handleChange(key, parseNumericFieldValue(key, e.target.value) as RuntimeSettings[typeof key])}
                          aria-label={PHASE_LABELS[key]}
                          className="w-full text-xs bg-transparent border border-border rounded-md px-2.5 py-1.5 text-foreground outline-none focus:border-primary/50"
                        />
                      ) : (
                        <input
                          type={isSensitive ? 'password' : 'text'}
                          value={value || ''}
                          onChange={(e) => handleChange(key, e.target.value as RuntimeSettings[typeof key])}
                          placeholder={isSensitive ? '••••••••' : ''}
                          aria-label={PHASE_LABELS[key]}
                          className="w-full text-xs bg-transparent border border-border rounded-md px-2.5 py-1.5 text-foreground outline-none focus:border-primary/50"
                        />
                      )}
                    </div>
                  )
                })}
              </div>
            </div>
          ))}

          <Separator />

          <div className="rounded-lg border border-border/60 bg-surface/20 p-3">
            <p className="text-xs font-medium text-foreground/80">当前供应商</p>
            <p className="mt-1 text-xs text-muted-foreground">
              API: {providerName} · 模型族: {modelFamily}
            </p>
            <p className="mt-1 text-2xs text-muted-foreground/50 break-all">
              {settings.siliconflow_base_url || '未配置 Base URL'}
            </p>
          </div>

          <p className="text-2xs text-muted-foreground/40 text-center pb-4">
            修改 embedding 模型后需要重新向量化所有文档才会生效。
            LLM 模型的修改会在下一次对话时生效。
          </p>
        </div>
      </ScrollArea>
    </div>
  )
}
