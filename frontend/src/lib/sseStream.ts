/**
 * SSE 流读取 + 事件分发（共享给 useAgentStore / ReceiptChatModal）
 *
 * 设计：
 *  - `readSSEStream` 是纯 AsyncGenerator，从 Response body 解码 data: 行
 *  - `computeEventUpdates` 是纯函数：SSEEvent + 上下文 → 描述「该做什么」的 result
 *  - 调用方（store / modal）把 result 翻译成自己的 state 变更
 *
 * 这样 store 和 modal 行为永远一致；新增事件只需在这里改一处。
 */
import type { SSEEvent } from '@/types/agent'

/** 异步读取 SSE 事件流。自动跳过空行和无法解析的 JSON。*/
export async function* readSSEStream(
  response: Response,
  signal: AbortSignal | null,
): AsyncGenerator<SSEEvent> {
  if (!response.body) return
  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  try {
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      if (signal?.aborted) break

      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() || ''

      for (const line of lines) {
        if (!line.startsWith('data: ')) continue
        const raw = line.slice(6).trim()
        if (!raw) continue
        try {
          yield JSON.parse(raw) as SSEEvent
        } catch {
          /* 忽略坏 JSON 行，避免单个错误中断整流 */
        }
      }
    }
  } finally {
    reader.releaseLock()
  }
}

/** 调度结果：告知调用方该做什么，以及如何更新自己持有的状态。*/
export type DispatchAction =
  | 'continue'         // 继续读取下一个事件
  | 'done-normal'      // done（正常完成），收尾 thought 步骤
  | 'error'            // error 事件，到达

export interface DispatchContext {
  /** 当前助手消息的 ID（用于把 text/tool_call 写入正确位置）*/
  assistantId: number
  /** 下一个 thought 步骤的序号（自增）*/
  thoughtStepId: number
  /** 调用方是否已有 session_id（用于判断 done.session_id 是否需要同步）*/
  hasCurrentSessionId: boolean
}

export interface DispatchResult {
  action: DispatchAction
  nextThoughtId: number

  /** text 事件：追加到助手消息 content*/
  textAppend?: string

  /** tool_call 事件：追加到助手消息 toolCalls*/
  toolCallAppend?: {
    id: string
    name: string
    arguments: string
  }

  /** tool_result 事件：填充最后一个 toolCall.result*/
  toolResultLast?: { result: string }

  /** thinking 事件：推入新的 running 步骤，并标记上一个为 done*/
  thoughtAppend?: { id: string; message: string }

  /** done 事件（正常完成）：收尾最后一个 running 步骤*/
  thoughtFinalizeLast?: true

  /** done 事件：需要同步的 session_id（仅在调用方还没有时）*/
  sessionIdSync?: string

  /** error 事件：错误消息*/
  errorMessage?: string
}

/** 把 SSE 事件转换为「状态更新描述」 — 调用方按需应用到自己的 state。*/
export function computeEventUpdates(
  event: SSEEvent,
  ctx: DispatchContext,
): DispatchResult {
  const data = event.data

  if (event.event === 'text') {
    return {
      action: 'continue',
      nextThoughtId: ctx.thoughtStepId,
      textAppend: data.content || '',
    }
  }

  if (event.event === 'tool_call') {
    return {
      action: 'continue',
      nextThoughtId: ctx.thoughtStepId,
      toolCallAppend: {
        id: data.id || `tc_${Date.now()}`,
        name: data.name,
        arguments: data.arguments,
      },
    }
  }

  if (event.event === 'tool_result') {
    return {
      action: 'continue',
      nextThoughtId: ctx.thoughtStepId,
      toolResultLast: { result: data.result },
    }
  }

  if (event.event === 'thinking') {
    return {
      action: 'continue',
      nextThoughtId: ctx.thoughtStepId + 1,
      thoughtAppend: {
        id: `thought_${ctx.thoughtStepId}`,
        message: data.message || '思考中...',
      },
    }
  }

  if (event.event === 'done') {
    return {
      action: 'done-normal',
      nextThoughtId: ctx.thoughtStepId,
      thoughtFinalizeLast: true,
      sessionIdSync: !ctx.hasCurrentSessionId ? data.session_id : undefined,
    }
  }

  if (event.event === 'error') {
    return {
      action: 'error',
      nextThoughtId: ctx.thoughtStepId,
      errorMessage: data.message,
    }
  }

  return { action: 'continue', nextThoughtId: ctx.thoughtStepId }
}

/** 将多条 text 片段合并为一次 content 追加（用于 rAF 合并渲染）。*/
export function mergeTextAppends(chunks: string[]): string {
  return chunks.join('')
}

/** 把 DispatchResult 应用到 ChatMessage 列表，返回新数组。*/
import type { ChatMessage } from '@/types/agent'

export function applyMessageUpdates(
  messages: ChatMessage[],
  result: DispatchResult,
  assistantId: number,
): ChatMessage[] {
  if (
    !result.textAppend &&
    !result.toolCallAppend &&
    !result.toolResultLast &&
    !result.thoughtAppend &&
    !result.thoughtFinalizeLast
  ) {
    return messages
  }

  // 用索引直接定位目标消息，避免 map 遍历整条数组
  const idx = messages.findIndex(m => m.id === assistantId)
  if (idx === -1) return messages

  const m = messages[idx]

  // text: 追加到 content
  if (result.textAppend !== undefined) {
    const updated = { ...m, content: m.content + result.textAppend }
    const next = messages.slice()
    next[idx] = updated
    return next
  }

  // tool_call: 推入 toolCalls
  if (result.toolCallAppend) {
    const updated = {
      ...m,
      toolCalls: [...(m.toolCalls || []), result.toolCallAppend],
    }
    const next = messages.slice()
    next[idx] = updated
    return next
  }

  // tool_result: 填充最后一个 toolCall.result
  if (result.toolResultLast && m.toolCalls?.length) {
    const calls = [...m.toolCalls]
    calls[calls.length - 1] = {
      ...calls[calls.length - 1],
      result: result.toolResultLast.result,
    }
    const next = messages.slice()
    next[idx] = { ...m, toolCalls: calls }
    return next
  }

  // thinking: 标记上一个 running 为 done，推入新的 running
  if (result.thoughtAppend) {
    const thoughts = [...(m.thoughts || [])]
    if (thoughts.length > 0 && thoughts[thoughts.length - 1].status === 'running') {
      thoughts[thoughts.length - 1] = {
        ...thoughts[thoughts.length - 1],
        status: 'done' as const,
      }
    }
    thoughts.push({ id: result.thoughtAppend.id, message: result.thoughtAppend.message, status: 'running' })
    const next = messages.slice()
    next[idx] = { ...m, thoughts }
    return next
  }

  // done: 收尾最后一个 running 步骤
  if (result.thoughtFinalizeLast && m.thoughts?.length) {
    const thoughts = [...m.thoughts]
    const last = thoughts[thoughts.length - 1]
    if (last && last.status === 'running') {
      thoughts[thoughts.length - 1] = { ...last, status: 'done' as const }
    }
    const next = messages.slice()
    next[idx] = { ...m, thoughts }
    return next
  }

  return messages
}
