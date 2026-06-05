import { useRef, useCallback } from 'react'

/**
 * 防抖 hook，返回一个带延迟的回调函数。
 * 连续调用时只执行最后一次，前一次会被取消。
 */
export function useDebounce<T extends (...args: never[]) => void>(
  callback: T,
  delay = 400
): T {
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  const debounced = useCallback(
    (...args: Parameters<T>) => {
      if (timerRef.current) clearTimeout(timerRef.current)
      timerRef.current = setTimeout(() => callback(...args), delay)
    },
    [callback, delay]
  ) as T

  return debounced
}
