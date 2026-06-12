/**
 * useAgentFile — 历史会话附件按 file_id 拉取并转为 Blob URL
 *
 * 为什么不用 <img src={url}>：现有体系是 Bearer Token，浏览器拉图不会带 Authorization 头，
 * 改 Cookie 又会破坏当前认证模型。这里 fetch 拿 blob → ObjectURL，组件卸载时统一释放。
 *
 * 用法：
 *   const { url, loading, error } = useAgentFile(fileId)
 *   <img src={url} /> 或 <a href={url} download>下载</a>
 */
import { useEffect, useRef, useState } from 'react'
import { API_BASE_URL } from '../services/api'

interface UseAgentFileResult {
  url: string | null
  loading: boolean
  error: 'not_found' | 'gone' | 'forbidden' | 'unknown' | null
}

// 进程内 file_id → ObjectURL 缓存：同会话多次渲染同一附件不重复 fetch
const _urlCache = new Map<string, string>()
const _inflight = new Map<string, Promise<string>>()

export function useAgentFile(fileId: string | undefined | null): UseAgentFileResult {
  const [url, setUrl] = useState<string | null>(fileId ? _urlCache.get(fileId) || null : null)
  const [loading, setLoading] = useState<boolean>(!!(fileId && !_urlCache.has(fileId)))
  const [error, setError] = useState<UseAgentFileResult['error']>(null)
  const cancelled = useRef(false)

  useEffect(() => {
    cancelled.current = false
    if (!fileId) {
      setUrl(null); setLoading(false); setError(null)
      return
    }
    if (_urlCache.has(fileId)) {
      setUrl(_urlCache.get(fileId)!); setLoading(false); setError(null)
      return
    }

    setLoading(true); setError(null)

    let promise = _inflight.get(fileId)
    if (!promise) {
      const token = localStorage.getItem('access_token')
      promise = fetch(`${API_BASE_URL}/agent/files/${fileId}`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      }).then(async (res) => {
        if (res.status === 404) throw new Error('not_found')
        if (res.status === 403) throw new Error('forbidden')
        if (res.status === 410) throw new Error('gone')
        if (!res.ok) throw new Error('unknown')
        const blob = await res.blob()
        const objectUrl = URL.createObjectURL(blob)
        _urlCache.set(fileId, objectUrl)
        return objectUrl
      }).finally(() => {
        _inflight.delete(fileId)
      })
      _inflight.set(fileId, promise)
    }

    promise.then((u) => {
      if (cancelled.current) return
      setUrl(u); setLoading(false)
    }).catch((e: Error) => {
      if (cancelled.current) return
      setLoading(false)
      const m = e.message as UseAgentFileResult['error']
      setError(m && ['not_found', 'gone', 'forbidden', 'unknown'].includes(m) ? m : 'unknown')
    })

    return () => { cancelled.current = true }
  }, [fileId])

  return { url, loading, error }
}
