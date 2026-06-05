import { Grid } from 'antd'
import { useEffect, useState } from 'react'

/**
 * 响应式 hook — 检测是否处于移动端视图 (< 768px)
 *
 * 使用 antd Grid.useBreakpoint()，首次渲染时默认为桌面端，
 * 避免 SSR/Hydration 闪烁。
 */
export function useMobile() {
  const screens = Grid.useBreakpoint()
  const [isMobile, setIsMobile] = useState(false)

  useEffect(() => {
    // screens.md 在 antd 中对应 768px 断点
    // 首次渲染时 screens 可能为全 undefined，此时默认 false（桌面端）
    setIsMobile(!(screens.md ?? true))
  }, [screens.md])

  return { isMobile, screens }
}
