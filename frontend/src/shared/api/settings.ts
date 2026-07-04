import { req } from '@/shared/api/client'
import type { RuntimeSettings, RuntimeSettingsUpdate, SettingsUpdateResult } from '@/shared/api/types'

export const getSettings = () =>
  req<RuntimeSettings>('/settings')

export const updateSettings = (data: RuntimeSettingsUpdate) =>
  req<SettingsUpdateResult>('/settings', {
    method: 'PUT',
    body: JSON.stringify(data),
  })
