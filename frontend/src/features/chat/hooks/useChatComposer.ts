import { useEffect, useRef, useState } from 'react'

interface UseChatComposerOptions {
  isStreaming: boolean
  onSend: (question: string) => void
}

export function useChatComposer({ isStreaming, onSend }: UseChatComposerOptions) {
  const inputRef = useRef<HTMLTextAreaElement>(null)
  const [input, setInput] = useState('')

  const send = () => {
    const question = input.trim()
    if (!question || isStreaming) return
    setInput('')
    onSend(question)
  }

  const handleKeyDown = (event: React.KeyboardEvent) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault()
      send()
    }
  }

  useEffect(() => {
    if (inputRef.current) {
      inputRef.current.style.height = 'auto'
      inputRef.current.style.height = `${Math.min(inputRef.current.scrollHeight, 120)}px`
    }
  }, [input])

  return { input, setInput, inputRef, send, handleKeyDown }
}
