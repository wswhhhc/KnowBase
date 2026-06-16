import { formatTime, truncate, evidenceColor, evidenceLabel, cn } from '@/lib/utils'

describe('formatTime', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date('2026-06-16T12:00:00Z'))
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  function makeIso(secondsAgo: number): string {
    return new Date(Date.now() - secondsAgo * 1000).toISOString()
  }

  it('returns "刚刚" for less than 1 minute', () => {
    expect(formatTime(makeIso(30))).toBe('刚刚')
  })

  it('returns "X 分钟前" for less than 60 minutes', () => {
    expect(formatTime(makeIso(5 * 60))).toBe('5 分钟前')
  })

  it('returns "X 小时前" for less than 24 hours', () => {
    expect(formatTime(makeIso(2 * 3600))).toBe('2 小时前')
  })

  it('returns "X 天前" for less than 7 days', () => {
    expect(formatTime(makeIso(3 * 86400))).toBe('3 天前')
  })

  it('returns locale date string for 10 days ago', () => {
    const result = formatTime(makeIso(10 * 86400))
    // Should be a locale date string (zh-CN), e.g. "2026/6/6"
    expect(result).not.toMatch(/刚刚|\d+ (分钟|小时|天)前/)
    expect(result.length).toBeGreaterThan(0)
  })
})

describe('truncate', () => {
  it('returns the original string when shorter than limit', () => {
    expect(truncate('hello', 10)).toBe('hello')
  })

  it('returns the original string when equal to limit', () => {
    expect(truncate('hello', 5)).toBe('hello')
  })

  it('truncates with "…" when longer than limit', () => {
    expect(truncate('hello world', 5)).toBe('hello…')
  })
})

describe('evidenceColor', () => {
  it('returns emerald for strong', () => {
    expect(evidenceColor('strong')).toBe('text-emerald-400')
  })

  it('returns yellow for moderate', () => {
    expect(evidenceColor('moderate')).toBe('text-yellow-400')
  })

  it('returns orange for weak', () => {
    expect(evidenceColor('weak')).toBe('text-orange-400')
  })

  it('returns red for none', () => {
    expect(evidenceColor('none')).toBe('text-red-400')
  })

  it('returns red for unknown level', () => {
    expect(evidenceColor('unknown')).toBe('text-red-400')
  })
})

describe('evidenceLabel', () => {
  it('returns "证据充分" for strong', () => {
    expect(evidenceLabel('strong')).toBe('证据充分')
  })

  it('returns "证据一般" for moderate', () => {
    expect(evidenceLabel('moderate')).toBe('证据一般')
  })

  it('returns "证据较弱" for weak', () => {
    expect(evidenceLabel('weak')).toBe('证据较弱')
  })

  it('returns "无证据" for none', () => {
    expect(evidenceLabel('none')).toBe('无证据')
  })

  it('returns the input itself for unknown level', () => {
    expect(evidenceLabel('some_level')).toBe('some_level')
  })
})

describe('cn', () => {
  it('merges class names', () => {
    expect(cn('px-4', 'py-2')).toBe('px-4 py-2')
  })

  it('handles conditional classes (falsy)', () => {
    expect(cn('base', false && 'hidden', 'visible')).toBe('base visible')
  })

  it('handles conditional classes (truthy)', () => {
    expect(cn('base', true && 'extra')).toBe('base extra')
  })

  it('resolves tailwind conflicts via twMerge', () => {
    // twMerge should keep the last px value
    expect(cn('px-4', 'px-6')).toBe('px-6')
  })
})
