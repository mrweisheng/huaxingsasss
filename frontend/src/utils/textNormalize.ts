/**
 * 群名/客户名校验工具：归一化 + 关键 token 交集。
 *
 * 用于判断「解析文本提取的值」与「合同实际值」的不匹配程度，分三档：
 *   match  归一化后相等或互相包含
 *   minor  归一化后不等，但关键 token（数字串 / 中文词片段）有交集
 *          → 多为大小写/空格/繁简差异，提醒即可
 *   major  关键 token 完全无交集 → 实质性不匹配（不同客户/业务），应拦截
 *
 * 设计取舍：不引入外部繁简转换库，用一张覆盖本项目群名常见字的精简映射表
 * 做归一化；未覆盖的字靠 keyTokens 的数字 + 中文词交集兜底判断 major/minor。
 */

/** 精简繁→简映射表（覆盖本项目群名/客户名/业务词常见字）。 */
const T2S: Record<string, string> = {
  '車': '车', '兩': '两', '過': '过', '辦': '办', '續': '续', '險': '险',
  '戶': '户', '證': '证', '網': '网', '號': '号', '時': '时', '蓮': '莲',
  '關': '关', '陸': '陆', '寶': '宝', '東': '东', '記': '记', '檢': '检',
  '輛': '辆', '權': '权', '責': '责', '業': '业', '務': '务', '員': '员',
  '張': '张', '陳': '陈', '劉': '刘', '華': '华', '興': '兴', '買': '买',
  '賣': '卖', '錢': '钱', '銀': '银', '現': '现', '轉': '转', '賬': '账',
  '餘': '余', '額': '额', '結': '结', '總': '总', '計': '计', '萬': '万',
  '億': '亿', '圓': '圆', '幣': '币', '個': '个', '對': '对', '應': '应',
  '當': '当', '還': '还', '這': '这', '們': '们', '來': '来', '國': '国',
  '港': '港', '新': '新', '牌': '牌', '岸': '岸', '姚': '姚', '敏': '敏',
}

/** 繁体转简体（仅映射表中收录的字，其余原样返回）。 */
function toSimplified(s: string): string {
  return s.replace(/[一-鿿]/g, (ch) => T2S[ch] ?? ch)
}

/**
 * 归一化用于比对：繁→简 + 转小写 + 去所有空格/标点/符号。
 * 例：「5月18日 姚嘉敏 新辦」→「5月18日姚嘉敏新办」
 */
export function normalizeForCompare(s: string | undefined | null): string {
  if (!s) return ''
  return toSimplified(s)
    .toLowerCase()
    .replace(/[\s\p{P}\p{S}_]+/gu, '')
    .trim()
}

/**
 * 提取关键 token 集合：连续数字串（≥2 位）+ 连续中文片段（≥2 字）。
 * 用于判断两个字符串是否在「关键信息」上有交集。
 */
export function keyTokens(s: string | undefined | null): Set<string> {
  if (!s) return new Set()
  const norm = toSimplified(s)
  const tokens = new Set<string>()
  for (const m of norm.match(/\d{2,}/g) ?? []) tokens.add(m)
  for (const m of norm.match(/[一-鿿]{2,}/g) ?? []) tokens.add(m)
  return tokens
}

export type MismatchLevel = 'match' | 'minor' | 'major'

/**
 * 群名不匹配分档。
 * - 任一为空 → match（无法判定，放行）
 * - 归一化后相等/包含 → match
 * - 关键 token 有交集 → minor（提醒）
 * - 关键 token 无交集 → major（拦截）
 */
export function groupMismatchLevel(
  extracted: string | undefined | null,
  actual: string | undefined | null,
): MismatchLevel {
  const e = normalizeForCompare(extracted)
  const a = normalizeForCompare(actual)
  if (!e || !a) return 'match'
  if (e === a || a.includes(e) || e.includes(a)) return 'match'
  const te = keyTokens(extracted)
  const ta = keyTokens(actual)
  let overlap = 0
  for (const t of te) if (ta.has(t)) overlap++
  return overlap > 0 ? 'minor' : 'major'
}
