/**
 * usePendingFiles — 待发送附件管理 + HEIC 提前上传
 *
 * 行为约定：
 * - 选 HEIC/HEIF 文件 → 立即触发后端上传（浏览器无法原生预览 HEIC，必须先上传拿 thumbnail）
 * - 选其他格式文件 → 不上传，发送时统一处理
 * - 上传中：send button 应禁用；上传完成：替换为 thumbnailUrl 作为预览
 *
 * 用法：
 *   const { pendingFiles, addFiles, removeFile, clear, hasUploading, toSendPayload } = usePendingFiles()
 */
import { useCallback, useRef, useState } from 'react'
import { agentApi } from '../services/agent'
import type { UploadResult } from '../types/agent'

export type PendingFileStatus = 'idle' | 'uploading' | 'done' | 'error'

export interface PendingFile {
  /** 稳定 id（addFiles 时生成），用于 uploadOne 按 id 精准更新 */
  id: string
  file: File
  /** 仅 HEIC 提前上传用：上传完成的服务端结果（含 thumbnailUrl） */
  uploaded?: UploadResult
  status: PendingFileStatus
  /** 缩略图 URL（HEIC done 时 = uploaded.thumbnailUrl，其他 idle） */
  preview?: string
}

function isHeic(file: File): boolean {
  const name = file.name.toLowerCase()
  return name.endsWith('.heic') || name.endsWith('.heif')
}

function genId(): string {
  return `pf_${Date.now()}_${Math.random().toString(36).slice(2, 10)}`
}

export interface UsePendingFiles {
  pendingFiles: PendingFile[]
  addFiles: (incoming: File[]) => void
  removeFile: (index: number) => void
  clear: () => void
  /** 是否有文件正在上传（用于禁用发送按钮） */
  hasUploading: boolean
  /** 把 PendingFile[] 转成 store.sendMessage 接受的载荷（已上传的 HEIC 带 uploaded 字段，跳过后端上传） */
  toSendPayload: () => Array<{ file: File; uploaded?: UploadResult }>
}

export function usePendingFiles(): UsePendingFiles {
  const [pendingFiles, setPendingFiles] = useState<PendingFile[]>([])
  // StrictMode 双调用保护：同一个 id 不会重复触发上传
  const inFlightRef = useRef<Set<string>>(new Set())

  const uploadOne = useCallback((id: string, file: File) => {
    if (inFlightRef.current.has(id)) return
    inFlightRef.current.add(id)
    setPendingFiles(prev => prev.map(p =>
      p.id === id ? { ...p, status: 'uploading' as const } : p,
    ))
    agentApi
      .uploadFile(file)
      .then(res => {
        inFlightRef.current.delete(id)
        setPendingFiles(prev => prev.map(p => {
          if (p.id !== id) return p
          return {
            ...p,
            status: 'done' as const,
            uploaded: res.data,
            preview: res.data.thumbnailUrl ?? undefined,
          }
        }))
      })
      .catch(() => {
        inFlightRef.current.delete(id)
        setPendingFiles(prev => prev.map(p =>
          p.id === id ? { ...p, status: 'error' as const } : p,
        ))
      })
  }, [])

  const addFiles = useCallback((incoming: File[]) => {
    if (incoming.length === 0) return
    const newFiles: PendingFile[] = incoming.map(file => ({
      id: genId(),
      file,
      status: 'idle' as const,
    }))
    setPendingFiles(prev => [...prev, ...newFiles])
    // 触发 HEIC 提前上传（按稳定 id，不依赖数组 index）
    newFiles.forEach(({ id, file }) => {
      if (isHeic(file)) uploadOne(id, file)
    })
  }, [uploadOne])

  const removeFile = useCallback((index: number) => {
    setPendingFiles(prev => prev.filter((_, i) => i !== index))
  }, [])

  const clear = useCallback(() => setPendingFiles([]), [])

  const hasUploading = pendingFiles.some(p => p.status === 'uploading')

  const toSendPayload = useCallback(
    () => pendingFiles.map(p => ({ file: p.file, uploaded: p.uploaded })),
    [pendingFiles],
  )

  return { pendingFiles, addFiles, removeFile, clear, hasUploading, toSendPayload }
}