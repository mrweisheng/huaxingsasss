/**
 * useDropZone — 稳定的拖拽上传 hook
 *
 * 解决原生 DnD 的两个经典坑：
 * 1. 子元素会触发父元素的 dragenter/dragleave，导致 isOver 闪烁 ——
 *    用 dragCounter 计数，只有真正离开容器（计数归零）才清除 isOver。
 * 2. 浏览器默认会打开拖进来的文件 —— onDragOver/onDragEnter 必须 preventDefault。
 *
 * 用法：
 *   const { isOver, dropHandlers } = useDropZone({
 *     onDrop: (files) => addFiles(files),
 *     accept: ['image/*', '.pdf', '.doc', '.docx'],
 *   })
 *   <div {...dropHandlers} className={isOver ? 'dragging' : ''}>
 *
 * accept 留空表示接受所有文件；传数组时按文件 type（image/*）或扩展名（.pdf）匹配。
 */
import { useCallback, useRef, useState } from 'react'

export interface DropZoneOptions {
  /** 文件放下时的回调 */
  onDrop: (files: File[]) => void
  /** 允许的文件类型，留空 = 全部；支持 MIME（image/*）或扩展名（.pdf） */
  accept?: string[]
  /** 拖拽中是否禁用（如正在流式输出时） */
  disabled?: boolean
}

export interface DropZoneHandlers {
  onDrop: (e: React.DragEvent) => void
  onDragEnter: (e: React.DragEvent) => void
  onDragOver: (e: React.DragEvent) => void
  onDragLeave: (e: React.DragEvent) => void
}

function matchesAccept(file: File, accept?: string[]): boolean {
  if (!accept || accept.length === 0) return true
  const name = file.name.toLowerCase()
  return accept.some((rule) => {
    if (rule.startsWith('.')) {
      // 扩展名匹配，如 .pdf
      return name.endsWith(rule.toLowerCase())
    }
    if (rule.endsWith('/*')) {
      // MIME 通配，如 image/*
      const prefix = rule.slice(0, -1) // "image/"
      return file.type.startsWith(prefix)
    }
    // 精确 MIME，如 image/png
    return file.type === rule
  })
}

export function useDropZone(options: DropZoneOptions): { isOver: boolean; dropHandlers: DropZoneHandlers } {
  const { onDrop, accept, disabled } = options
  const [isOver, setIsOver] = useState(false)
  // 用 ref 存计数器和最新回调，避免重渲染导致回调闭包过期
  const dragCounter = useRef(0)
  const onDropRef = useRef(onDrop)
  const acceptRef = useRef(accept)
  const disabledRef = useRef(disabled)

  // 每次渲染同步最新值到 ref（不触发重渲染）
  onDropRef.current = onDrop
  acceptRef.current = accept
  disabledRef.current = disabled

  const handleDragEnter = useCallback((e: React.DragEvent) => {
    if (disabledRef.current) return
    e.preventDefault()
    e.stopPropagation()
    dragCounter.current += 1
    if (e.dataTransfer.items && e.dataTransfer.items.length > 0) {
      setIsOver(true)
    }
  }, [])

  const handleDragOver = useCallback((e: React.DragEvent) => {
    if (disabledRef.current) return
    e.preventDefault()
    e.stopPropagation()
    // 拖拽时给个 dropEffect，让光标显示"复制"图标
    if (e.dataTransfer) {
      e.dataTransfer.dropEffect = 'copy'
    }
  }, [])

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    if (disabledRef.current) return
    e.preventDefault()
    e.stopPropagation()
    dragCounter.current -= 1
    // 只有计数归零（真正离开容器）才清除高亮，避免子元素切换时闪烁
    if (dragCounter.current <= 0) {
      dragCounter.current = 0
      setIsOver(false)
    }
  }, [])

  const handleDrop = useCallback((e: React.DragEvent) => {
    if (disabledRef.current) return
    e.preventDefault()
    e.stopPropagation()
    dragCounter.current = 0
    setIsOver(false)
    const files = Array.from(e.dataTransfer.files)
    if (files.length === 0) return
    const filtered = files.filter((f) => matchesAccept(f, acceptRef.current))
    if (filtered.length === 0) return
    onDropRef.current(filtered)
  }, [])

  return {
    isOver,
    dropHandlers: {
      onDrop: handleDrop,
      onDragEnter: handleDragEnter,
      onDragOver: handleDragOver,
      onDragLeave: handleDragLeave,
    },
  }
}
