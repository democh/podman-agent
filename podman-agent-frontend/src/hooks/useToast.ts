import { useCallback } from 'react'

let toastId = 0

interface ToastOptions {
  message: string
  type?: 'info' | 'success' | 'warning' | 'error'
  duration?: number
}

/**
 * 轻量 Toast 通知系统：直接操作 DOM 注入通知节点。
 * 无需全局 state 管理，调用即显示。
 */
function showToast({ message, type = 'info', duration = 3000 }: ToastOptions) {
  const container = document.getElementById('toast-container')
  if (!container) return

  const id = ++toastId
  const el = document.createElement('div')
  el.className = `toast toast-${type}`
  el.setAttribute('data-toast-id', String(id))
  el.textContent = message

  container.appendChild(el)

  // 触发进入动画
  requestAnimationFrame(() => el.classList.add('toast-visible'))

  // 自动移除
  setTimeout(() => {
    el.classList.remove('toast-visible')
    el.addEventListener('transitionend', () => el.remove(), { once: true })
    // fallback: 如果 transitionend 未触发
    setTimeout(() => el.remove(), 300)
  }, duration)
}

/**
 * Toast hook：返回 toast 函数用于触发通知。
 */
export function useToast() {
  const toast = useCallback((message: string, type?: ToastOptions['type']) => {
    showToast({ message, type })
  }, [])

  return { toast }
}

export { showToast }
