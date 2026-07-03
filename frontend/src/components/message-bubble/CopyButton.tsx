import { useState } from 'react'
import { CheckCircle, Copy } from 'lucide-react'

export default function CopyButton({ content }: { content: string }) {
  const [copied, setCopied] = useState(false)

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(content)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch (error) {
      console.error('复制失败', error)
    }
  }

  return (
    <button
      onClick={handleCopy}
      className={`p-1 rounded transition-colors ${copied ? 'text-emerald-400' : 'text-muted-foreground/40 hover:text-foreground'}`}
      title={copied ? '已复制' : '复制回答'}
    >
      {copied ? <CheckCircle className="h-3 w-3" /> : <Copy className="h-3 w-3" />}
    </button>
  )
}
