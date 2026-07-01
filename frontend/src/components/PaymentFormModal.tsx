import { useEffect, useState, useRef } from 'react'
import { Button, Modal, Form, Input, InputNumber, Select, Space, DatePicker, Upload, Alert, message, Avatar } from 'antd'
const { useWatch } = Form
import { PlusOutlined, InboxOutlined, FilePdfOutlined, FileOutlined, DeleteOutlined, WarningOutlined, WechatOutlined, UserOutlined, SwapOutlined, CloseOutlined, RobotOutlined } from '@ant-design/icons'
import dayjs from 'dayjs'
import {
  paymentApi,
  type PaymentCreatePayload,
  type PaymentUpdatePayload,
  type CounterpartyAccount,
  type ExtractedReceiptData,
} from '@/services/payment'
import { paymentAccountApi, type PaymentAccount } from '@/services/paymentAccount'
import { compressImage } from '@/utils/imageCompress'
import { isNoReceipt } from '@/utils/payment'
import { currencySymbol } from '@/utils/moneyFormat'
import { groupMismatchLevel, normalizeForCompare } from '@/utils/textNormalize'
import type { Payment } from '@/types'
import './PaymentFormModal.css'

/**
 * 收款账户类型 → 付款方式的映射。
 * payment_method 的合法值：bank_transfer/wechat/alipay/cash/check（见后端 models/payment.py）。
 * account_type 的合法值：bank/alipay/wechat/cash/other（见 services/paymentAccount.ts）。
 * 两套枚举命名不同（bank vs bank_transfer），此处归一；other 不映射，交后端 AI 凭证检测补全。
 */
const ACCOUNT_TYPE_TO_METHOD: Record<string, string> = {
  bank: 'bank_transfer',
  alipay: 'alipay',
  wechat: 'wechat',
  cash: 'cash',
}

/** 根据所选收款账户推导付款方式；找不到或类型为 other 返回 undefined。 */
function deriveMethodFromAccount(accountId: number | undefined, accounts: PaymentAccount[]): string | undefined {
  if (!accountId) return undefined
  const acc = accounts.find(a => a.id === accountId)
  if (!acc) return undefined
  return ACCOUNT_TYPE_TO_METHOD[acc.account_type]
}

// 业务色徽章映射：与设计系统业务色保持一致（仅在此标识业务类型）
const BIZ_BADGE_STYLE: Record<string, { className: string; label: string }> = {
  '两地牌过户': { className: 'biz-license-chip', label: '两地牌' },
  '车辆买卖': { className: 'biz-vehicle-chip', label: '车辆' },
  '年检保险': { className: 'biz-insurance-chip', label: '年检保险' },
  '其他': { className: 'biz-other-chip', label: '其他业务' },
}

// 第一步文本框 placeholder：贴合收款 7 项 / 转出 6 项固定模板，引导用户照填（编号可省）
const INPUT_PLACEHOLDER_INCOME = `粘贴收款信息（可参考模板，编号可省）：
1、收款（款项说明）
2、2025年6月13日
3、收款账户：高山香港账户
4、收款对象：客户名
5、金额：HKD 210479
6、结算状态：已结清 / 未结清
7、对应业务：群名称`

const INPUT_PLACEHOLDER_EXPENSE = `粘贴转出信息（可参考模板，编号可省）：
1、转出（款项说明）
2、2025年6月13日
3、转出账户：户名 / 卡号 / 开户行
4、金额：17万 RMB
5、结算状态：已结清 / 未结清
6、对应业务：群名称`

// 格式化日期为 MM/DD（极简展示，年份省略）
function fmtShortDate(d?: string) {
  if (!d) return ''
  const parts = d.split('-')  // YYYY-MM-DD
  if (parts.length !== 3) return d
  return `${parts[1]}/${parts[2]}`
}

// 已有记录的状态标签文案 + 颜色类
function existingStatusOf(p: Payment): { text: string; cls: string } {
  if (p.status === 'paid') {
    if (isNoReceipt(p)) return { text: '无凭证', cls: 'st-no-receipt' }
    return { text: '已入账', cls: 'st-paid' }
  }
  // pending
  if (p.verification_status === 'failed') return { text: '待放行', cls: 'st-failed' }
  if (p.verification_status === 'pending') return { text: '校验中', cls: 'st-pending' }
  return { text: '待入账', cls: 'st-pending' }
}

function formatVerificationValue(value: unknown, currency?: string): string {
  if (value === null || value === undefined || value === '') return '-'
  if (typeof value === 'number') {
    const text = value.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
    return currency ? `${currency} ${text}` : text
  }
  return String(value)
}

function renderVerificationPanel(payment: Payment | null | undefined) {
  const result = payment?.verification_result
  if (payment?.verification_status !== 'failed' || !result) return null

  const rows = [
    {
      key: 'amount',
      label: '金额',
      expected: formatVerificationValue(result.expected?.amount, result.expected?.currency),
      extracted: formatVerificationValue(result.extracted?.amount, result.extracted?.currency || result.expected?.currency),
      matched: result.match?.amount,
    },
    {
      key: 'currency',
      label: '币种',
      expected: formatVerificationValue(result.expected?.currency),
      extracted: formatVerificationValue(result.extracted?.currency),
      matched: result.match?.currency,
    },
    {
      key: 'payer',
      label: '付款方',
      expected: formatVerificationValue(result.expected?.payer),
      extracted: formatVerificationValue(result.extracted?.payer_name),
      matched: result.match?.payer,
    },
  ]

  return (
    <div className="pfm-verification-panel">
      <div className="pfm-verification-head">
        <span className="pfm-verification-title"><WarningOutlined /> AI 凭证核对不通过</span>
        {typeof result.confidence === 'number' && (
          <span className="pfm-verification-confidence">置信度 {Math.round(result.confidence * 100)}%</span>
        )}
      </div>
      <div className="pfm-verification-reason">{result.reason || '凭证与表单填写不一致，请核对。'}</div>
      <div className="pfm-verification-grid">
        {rows.map(row => (
          <div key={row.key} className={`pfm-verification-row ${row.matched === false ? 'is-mismatch' : ''}`}>
            <span className="pfm-v-field">{row.label}</span>
            <span className="pfm-v-value"><i>表单</i>{row.expected}</span>
            <span className="pfm-v-value"><i>凭证</i>{row.extracted}</span>
            <span className="pfm-v-result">{row.matched === false ? '不一致' : row.matched === true ? '一致' : '未判断'}</span>
          </div>
        ))}
      </div>
    </div>
  )
}

/** 结构化不匹配项：业务群 / 客户 / 收支类型，按字段分行展示「合同 vs 识别」对比 */
type MismatchItem = {
  field: 'type' | 'group' | 'customer'
  label: string
  extracted: string
  actual: string
  /** 可选副标题；type 不匹配时解释"为什么不能用对方向" */
  hint?: string
  /** true = 阻断提交（方向不符 / 群名严重不符）；false = 仅提醒可放行 */
  blocking?: boolean
}

interface Props {
  open: boolean
  mode: 'add' | 'edit'
  /** 合同上下文（add 必填；edit 时用于回显） */
  contractId?: number
  contractNumber?: string
  customerName?: string
  contractTitle?: string
  wechatGroup?: string
  businessType?: string   // 车辆买卖 / 两地牌过户 / 年检保险 / 其他（header 业务徽章）
  status?: string         // 合同状态 active / completed（header 状态标）
  totalAmount?: number
  currency?: string
  /** 收支方向（add 必填；edit 由 editing 推断） */
  paymentType?: 'income' | 'expense'
  /** 编辑时的原记录 */
  editing?: Payment | null
  onClose: () => void
  onSuccess: () => void
}

/**
 * 收支录入表单 Modal（add/edit 共用，mode 区分）。
 * 纯表单 CRUD，不走 Agent。对应 CLAUDE.md：字段固定的结构化录入用表单。
 *
 * - 收入：收款账户下拉（预设 payment_accounts，可选"其他"即时新增）；
 *   凭证现阶段可选（INCOME_RECEIPT_REQUIRED=False）——有凭证走异步校验，无凭证标记
 *   「无凭证收入」直接入账，后续可补传。开关切回 True 时恢复必传。
 * - 支出：对方账户手填（供应商不固定），凭证可选，无凭证可声明。
 */
export default function PaymentFormModal({
  open, mode, contractId, customerName, contractTitle, wechatGroup,
  businessType, status, currency, totalAmount, paymentType, editing, onClose, onSuccess,
}: Props) {
  const [form] = Form.useForm()
  const [submitting, setSubmitting] = useState(false)
  const [accounts, setAccounts] = useState<PaymentAccount[]>([])
  const [addAccountOpen, setAddAccountOpen] = useState(false)
  const [newAccount, setNewAccount] = useState({ account_type: 'bank', title: '', account_name: '', account_number: '', bank_name: '', branch: '' })
  const [uploading, setUploading] = useState(false)
  const [uploadedFileId, setUploadedFileId] = useState<string | undefined>(undefined)
  const [uploadedFile, setUploadedFile] = useState<{
    file_id: string; file_name: string; file_type: string; preview_url?: string
  } | null>(null)
  const [receiptCleared, setReceiptCleared] = useState(false)
  const [mismatchItems, setMismatchItems] = useState<MismatchItem[] | null>(null)
  // 本合同已有的同类型（income/expense）记录，打开时加载，录入成功后刷新
  const [existingPayments, setExistingPayments] = useState<Payment[]>([])
  const [step, setStep] = useState<'input' | 'form'>('input')
  const [inputText, setInputText] = useState('')
  const [parsing, setParsing] = useState(false)
  const extractedCounterpartyRef = useRef<Partial<CounterpartyAccount> | null>(null)
  const isMountedRef = useRef(true)
  const isEdit = mode === 'edit'
  const isIncome = isEdit ? editing?.type === 'income' : paymentType === 'income'
  const contractCurrency = editing?.contract_currency || currency

  // 支出付款方式联动：监听当前选的付款方式，决定对方账户字段显示哪些
  const expenseMethod = useWatch('payment_method', form)
  // 银行转账/支票 → 需要银行账户字段；现金 → 只留收款方名称；微信/支付宝 → 留选填账号
  const showBankFields = !isIncome && (expenseMethod === 'bank_transfer' || expenseMethod === 'check')
  const showAccountNoField = !isIncome && expenseMethod !== 'cash'

  const typeLabel = isIncome ? '收款' : '转出'
  const themeClass = isIncome ? 'pfm-income' : 'pfm-expense'
  // 序号动态：收入 收款账户=3/金额=4/备注=5；支出 付款方式=3/收款方=4/金额=5/备注=6
  const seqAmount = isIncome ? 4 : 5
  const seqNotes = isIncome ? 5 : 6

  // 加载收款账户列表
  useEffect(() => {
    if (!open || !isIncome) return
    paymentAccountApi.list().then((list: any) => {
      const arr = Array.isArray(list) ? list : list?.data ?? []
      setAccounts(arr)
    }).catch(() => setAccounts([]))
  }, [open, isIncome])

  // 加载本合同已有的同类型收支记录（add 模式顶部展示，录入成功后刷新）
  const loadExistingPayments = async () => {
    if (!contractId || !paymentType) return
    try {
      const resp = await paymentApi.getContractPayments(contractId)
      // axios 拦截器返回整个 body，真正的 payload 在 resp.data
      const payload = resp?.data || resp
      const group = payload?.[paymentType]
      setExistingPayments(Array.isArray(group?.payments) ? group.payments : [])
    } catch {
      setExistingPayments([])
    }
  }

  // 打开时加载已有记录（仅 add 模式）
  useEffect(() => {
    if (!open || isEdit || !contractId) return
    loadExistingPayments()
  }, [open, isEdit, contractId, paymentType])

  // 组件卸载标记，防止 async 回调在关闭后触发状态更新
  useEffect(() => {
    isMountedRef.current = true
    return () => { isMountedRef.current = false }
  }, [])

  // 打开时初始化表单
  useEffect(() => {
    if (!open) return
    // 清理旧的预览 URL
    if (uploadedFile?.preview_url) URL.revokeObjectURL(uploadedFile.preview_url)
    setUploadedFileId(undefined)
    setUploadedFile(null)
    setReceiptCleared(false)
    setMismatchItems(null)
    extractedCounterpartyRef.current = null
    setStep(isEdit ? 'form' : 'input')
    setInputText('')
    setParsing(false)
    if (isEdit && editing) {
      form.setFieldsValue({
        amount: editing.paid_amount,
        currency: editing.currency,
        paid_date: editing.paid_date ? dayjs(editing.paid_date) : undefined,
        installment_name: editing.installment_name,
        description: editing.description,
        notes: editing.notes,
        payment_account_id: editing.payment_account_id,
        // 支出回显付款方式；收入由收款账户推导（不回显此字段）
        payment_method: !isIncome ? editing.payment_method : undefined,
        payee_name: editing.payee_name,
        ...editing.counterparty_account,
      })
    } else {
      form.resetFields()
      form.setFieldsValue({
        currency: contractCurrency || 'CNY',
        paid_date: dayjs(),
        // 支出默认付款方式银行转账（最常见场景）
        payment_method: !isIncome ? 'bank_transfer' : undefined,
      })
    }
  }, [open, isEdit, editing, form, contractCurrency, isIncome])

  // 凭证提交门槛：现阶段（INCOME_RECEIPT_REQUIRED=False）收入凭证可选；
  // 支出本就可选；编辑时若未换凭证且未清除，沿用原凭证
  const canSubmit = !submitting && !uploading

  // ── 凭证上传（左列）：只上传，不识别 ──
  const handleReceiptUpload = async (file: File) => {
    setUploading(true)
    try {
      const isImage = file.type.startsWith('image/')
      const previewUrl = isImage ? URL.createObjectURL(file) : undefined
      const compressed = await compressImage(file)
      const res = await paymentApi.uploadReceipt(compressed)
      if (uploadedFile?.preview_url) URL.revokeObjectURL(uploadedFile.preview_url)
      setUploadedFile({
        file_id: res.file_id,
        file_name: file.name,
        file_type: file.type,
        preview_url: previewUrl,
      })
      setUploadedFileId(res.file_id)
      setReceiptCleared(false)
      message.success('凭证已上传')
    } catch (e: any) {
      message.error(e?.response?.data?.detail || '凭证上传失败')
    } finally {
      setUploading(false)
    }
    return false
  }

  // 共享填充逻辑：校验类型 + 填表 + 不匹配警告（无 file/preview 处理）
  const applyExtractedData = (extracted: ExtractedReceiptData) => {
    // 函数自身负责清自己写的状态：每次重新识别都先抹掉上一次的红卡
    setMismatchItems(null)

    // 检查类型是否匹配
    if (extracted.type && extracted.type !== paymentType) {
      const expectedLabel = paymentType === 'income' ? '收入' : '支出'
      const actualLabel = extracted.type === 'income' ? '收入' : '支出'
      setMismatchItems([{
        field: 'type',
        label: '收支类型',
        extracted: actualLabel,
        actual: expectedLabel,
        hint: `当前入口只能录入${expectedLabel}，请改用「录入${actualLabel}」入口`,
        blocking: true,
      }])
      message.error(`识别结果「${actualLabel}」，与当前「${expectedLabel}」录入方向不一致`)
      return
    }

    // 自动填充表单字段
    const formValues: Record<string, any> = {}
    if (extracted.installment_name) formValues.installment_name = extracted.installment_name
    if (extracted.paid_date) {
      const date = dayjs(extracted.paid_date)
      if (date.isValid()) formValues.paid_date = date
    }
    if (extracted.amount) formValues.amount = extracted.amount
    if (extracted.currency) formValues.currency = extracted.currency
    if (extracted.notes) formValues.notes = extracted.notes
    if (extracted.payment_method) formValues.payment_method = extracted.payment_method

    if (isIncome) {
      // 收款账户简称匹配：后端 _attach_payment_account_id 已模糊匹配出 ID，这里直接填表单下拉
      if (extracted.payment_account_id) formValues.payment_account_id = extracted.payment_account_id
    } else {
      if (extracted.payee_name) formValues.payee_name = extracted.payee_name
      if (extracted.counterparty_account) {
        if (extracted.counterparty_account.account_name) formValues.account_name = extracted.counterparty_account.account_name
        if (extracted.counterparty_account.account_number) formValues.account_number = extracted.counterparty_account.account_number
        if (extracted.counterparty_account.bank_name) formValues.bank_name = extracted.counterparty_account.bank_name
        if (extracted.counterparty_account.branch) formValues.branch = extracted.counterparty_account.branch
      }
    }
    form.setFieldsValue(formValues)

    if (extracted.counterparty_account) {
      extractedCounterpartyRef.current = extracted.counterparty_account
    }

    // 检查其他不匹配
    const mismatches: MismatchItem[] = []
    // 业务群名：分两档——major（关键信息完全对不上）拦截，minor（大小写/空格/繁简差异）提醒
    const actualGroup = wechatGroup || editing?.contract_wechat_group
    if (extracted.wechat_group && actualGroup) {
      const level = groupMismatchLevel(extracted.wechat_group, actualGroup)
      if (level === 'major') {
        mismatches.push({
          field: 'group', label: '业务群名',
          extracted: extracted.wechat_group, actual: actualGroup,
          blocking: true,
          hint: '关键信息（客户/业务/时间）完全对不上，请确认是否选错合同',
        })
      } else if (level === 'minor') {
        mismatches.push({
          field: 'group', label: '业务群名',
          extracted: extracted.wechat_group, actual: actualGroup,
          blocking: false,
        })
      }
    }
    // 客户姓名：归一化后仍不一致则提醒（非阻断）
    if (extracted.customer_name_hint && customerName) {
      const ec = normalizeForCompare(extracted.customer_name_hint)
      const ac = normalizeForCompare(customerName)
      if (ec && ac && !ac.includes(ec) && !ec.includes(ac)) {
        mismatches.push({
          field: 'customer', label: '客户姓名',
          extracted: extracted.customer_name_hint, actual: customerName,
          blocking: false,
        })
      }
    }
    // 收款账户简称有但后端没匹配到 ID → 提示用户手动选择
    if (isIncome && extracted.payment_account_hint && !extracted.payment_account_id) {
      message.warning(`未在系统中找到匹配的收款账户「${extracted.payment_account_hint}」，请手动选择`)
    }
    if (mismatches.length > 0) {
      setMismatchItems(mismatches)
    }

    if (extracted.confidence && extracted.confidence < 0.7) {
      message.warning('识别置信度较低，请核对填充信息')
    } else {
      message.success('已自动识别并填充表单')
    }
  }

  const handleRemoveReceipt = () => {
    if (uploadedFile?.preview_url) URL.revokeObjectURL(uploadedFile.preview_url)
    setUploadedFile(null)
    setUploadedFileId(undefined)
    setReceiptCleared(false)
  }

  // ── 两步式：下一步（文本解析 → 填充表单） ──
  const handleNextStep = async () => {
    if (!inputText.trim()) {
      message.warning('请输入文本')
      return
    }
    setParsing(true)
    try {
      const extracted = await paymentApi.extractText(inputText.trim())
      if (!isMountedRef.current) return
      applyExtractedData(extracted)
      setStep('form')
    } catch (e: any) {
      console.warn('识别失败', e)
      message.warning('识别失败，请手动填写')
      // 失败也进表单，不锁死在第一步
      setStep('form')
    } finally {
      setParsing(false)
    }
  }

  const handleAddAccount = async () => {
    if (!newAccount.title.trim() || !newAccount.account_name.trim()) {
      message.warning('请填写账户标题和户名')
      return
    }
    try {
      const created: any = await paymentAccountApi.create({
        account_type: newAccount.account_type as any,
        title: newAccount.title.trim(),
        account_name: newAccount.account_name.trim(),
        account_number: newAccount.account_number || undefined,
        bank_name: newAccount.bank_name || undefined,
        branch: newAccount.branch || undefined,
      })
      const list = await paymentAccountApi.list() as any
      const arr = Array.isArray(list) ? list : list?.data ?? []
      setAccounts(arr)
      form.setFieldValue('payment_account_id', created.id)
      setAddAccountOpen(false)
      setNewAccount({ account_type: 'bank', title: '', account_name: '', account_number: '', bank_name: '', branch: '' })
      message.success('收款账户已添加')
    } catch (e: any) {
      message.error(e?.response?.data?.detail || '添加账户失败')
    }
  }

  const handleOk = async () => {
    // 阻断项（方向不符 / 群名严重不符）必须先处理，禁止提交
    if (mismatchItems?.some(m => m.blocking)) {
      message.error('存在需处理的不匹配项（收支方向 / 业务群名），请核对后再提交')
      return
    }
    try {
      const values = await form.validateFields()
      // 新建必传凭证：凭证只作存储 + 前端可查看，不做校验识别，但必须上传
      if (!isEdit && !uploadedFileId) {
        message.error('请上传凭证')
        return
      }
      setSubmitting(true)

      if (!isEdit) {
        // ── 新建 ──
        // payment_method：收入按所选收款账户的 account_type 推导（bank→bank_transfer 等）；
        // 支出由用户在表单里直接选择（银行转账/微信/支付宝/现金/支票）。
        const paymentMethod = isIncome
          ? deriveMethodFromAccount(values.payment_account_id, accounts)
          : values.payment_method
        const payload: PaymentCreatePayload = {
          type: paymentType!,
          currency: values.currency,
          amount: Number(values.amount),
          paid_date: values.paid_date.format('YYYY-MM-DD'),
          payment_method: paymentMethod,
          installment_name: values.installment_name?.trim() || undefined,
          description: values.description?.trim() || undefined,
          notes: values.notes?.trim() || undefined,
        }
        if (isIncome) {
          payload.payment_account_id = values.payment_account_id
          payload.receipt_file_id = uploadedFileId!
        } else {
          payload.payee_name = values.payee_name?.trim() || undefined
          const cp: CounterpartyAccount = {}
          if (values.account_name) cp.account_name = values.account_name.trim()
          if (values.account_number) cp.account_number = values.account_number.trim()
          if (values.bank_name) cp.bank_name = values.bank_name.trim()
          if (values.branch) cp.branch = values.branch.trim()
          // 合并提取的额外字段（如 swift_code）
          if (extractedCounterpartyRef.current) {
            if (!cp.swift_code && extractedCounterpartyRef.current.swift_code) cp.swift_code = extractedCounterpartyRef.current.swift_code
          }
          if (Object.keys(cp).length) payload.counterparty_account = cp
          payload.receipt_file_id = uploadedFileId!
        }
        await paymentApi.create(contractId!, payload)
        // 收入有凭证才异步校验；无凭证（no_receipt）直接入账
        message.success(`${typeLabel}已录入${isIncome && uploadedFileId ? '，正在校验凭证…' : ''}`)
      } else {
        // ── 编辑 ──
        // 收入：按（可能变更后的）收款账户重新推导 payment_method，保持与账户一致；
        // 支出：用用户在表单里选的付款方式。
        const paymentMethod = isIncome
          ? deriveMethodFromAccount(values.payment_account_id, accounts)
          : values.payment_method
        const payload: PaymentUpdatePayload = {
          amount: Number(values.amount),
          currency: values.currency,
          paid_date: values.paid_date.format('YYYY-MM-DD'),
          payment_method: paymentMethod,
          installment_name: values.installment_name?.trim() || undefined,
          description: values.description?.trim() || undefined,
          notes: values.notes?.trim() || undefined,
        }
        if (isIncome) {
          payload.payment_account_id = values.payment_account_id
        } else {
          payload.payee_name = values.payee_name?.trim() || undefined
          const cp: CounterpartyAccount = {}
          if (values.account_name) cp.account_name = values.account_name.trim()
          if (values.account_number) cp.account_number = values.account_number.trim()
          if (values.bank_name) cp.bank_name = values.bank_name.trim()
          if (values.branch) cp.branch = values.branch.trim()
          // 合并提取的额外字段（如 swift_code）
          if (extractedCounterpartyRef.current) {
            if (!cp.swift_code && extractedCounterpartyRef.current.swift_code) cp.swift_code = extractedCounterpartyRef.current.swift_code
          }
          payload.counterparty_account = Object.keys(cp).length ? cp : undefined
        }
        // 凭证变化
        if (uploadedFileId) payload.receipt_file_id = uploadedFileId
        else if (receiptCleared) payload.receipt_file_id = ''
        await paymentApi.update(editing!.id, payload)
        message.success(`${typeLabel}已更新${isIncome && (uploadedFileId || receiptCleared) ? '，正在重新校验…' : ''}`)
      }
      if (!isEdit) {
        // 新建：刷新已有记录 + 重置回文本输入步（支持连续录入），保持弹窗打开
        await loadExistingPayments()
        form.resetFields()
        form.setFieldsValue({
          currency: contractCurrency || 'CNY',
          paid_date: dayjs(),
          payment_method: !isIncome ? 'bank_transfer' : undefined,
        })
        setUploadedFileId(undefined)
        setUploadedFile(null)
        setReceiptCleared(false)
        setMismatchItems(null)
        extractedCounterpartyRef.current = null
        setInputText('')
        setStep('input')
        onSuccess()
      } else {
        onSuccess()
        onClose()
      }
    } catch (e: any) {
      if (e?.errorFields) return  // antd 表单校验失败
      message.error(e?.response?.data?.detail || '操作失败')
    } finally {
      setSubmitting(false)
    }
  }

  const currencyMismatch = !!form.getFieldValue('currency') && form.getFieldValue('currency') !== contractCurrency

  return (
    <Modal
      title={
        <span className="pfm-title">
          <span className={`pfm-title-bar ${themeClass}`} />
          {isEdit ? '编辑' : '录入'}{typeLabel}
        </span>
      }
      open={open}
      onCancel={onClose}
      destroyOnClose
      maskClosable={false}
      width={760}
      className={`pfm-modal ${themeClass}`}
      footer={step === 'input' ? (
        <Space>
          <Button onClick={onClose}>取消</Button>
          <Button type="primary" onClick={handleNextStep} loading={parsing} disabled={!inputText.trim()}>下一步</Button>
        </Space>
      ) : (
        <Space>
          <Button onClick={onClose}>取消</Button>
          <Button type="primary" onClick={handleOk} loading={submitting} disabled={!canSubmit}>{isEdit ? '保存' : '提交'}</Button>
        </Space>
      )}
    >
      {renderVerificationPanel(editing)}

      {/* 顶部合同信息 header：Avatar + 业务徽章 + 群名 + 状态 + 金额 + 客户·合同 */}
      {(wechatGroup || customerName || contractTitle || businessType) && (
        <div className={`pfm-header ${themeClass}`}>
          <Avatar icon={<RobotOutlined />} className="pfm-header-avatar" size={38} />
          <div className="pfm-header-info">
            <div className="pfm-header-main">
              {businessType && BIZ_BADGE_STYLE[businessType] && (
                <span className={`pfm-header-biz-chip ${BIZ_BADGE_STYLE[businessType].className}`}>
                  {BIZ_BADGE_STYLE[businessType].label}
                </span>
              )}
              <span className="pfm-header-groupname" title={wechatGroup}>
                {wechatGroup || '未设置业务群'}
              </span>
              {status && (
                <span className={`pfm-header-status ${status}`}>
                  {status === 'active' ? '执行中' : status === 'completed' ? '已完成' : status}
                </span>
              )}
              {totalAmount != null && (
                <span className="pfm-header-amount">
                  <span className="pfm-header-amount-cur">{currencySymbol[contractCurrency || currency || 'CNY'] || '¥'}</span>
                  <span className="pfm-header-amount-num">
                    {totalAmount.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                  </span>
                </span>
              )}
            </div>
            <div className="pfm-header-sub">
              <span className="pfm-header-customer">{customerName || '—'}</span>
              {contractTitle && (
                <>
                  <span className="pfm-header-dot">·</span>
                  <span className="pfm-header-contract-title" title={contractTitle}>{contractTitle}</span>
                </>
              )}
            </div>
          </div>
        </div>
      )}

      {/* 已有同类型收支记录（仅 add 模式且有记录时展示） */}
      {!isEdit && existingPayments.length > 0 && (
        <div className={`pfm-existing ${themeClass}`}>
          <div className="pfm-existing-title">本合同已有 {existingPayments.length} 笔{typeLabel}</div>
          <div className="pfm-existing-list">
            {existingPayments.map((p) => {
              const st = existingStatusOf(p)
              const label = p.installment_name || p.description || '未命名'
              return (
                <div key={p.id} className="pfm-existing-row">
                  <span className="pfm-existing-name" title={label}>{label}</span>
                  <span className="pfm-existing-amount">
                    {currencySymbol[p.currency] || '¥'}{(p.paid_amount ?? p.amount).toLocaleString('zh-CN', { maximumFractionDigits: 2 })}
                  </span>
                  <span className="pfm-existing-date">{fmtShortDate(p.paid_date)}</span>
                  <span className={`pfm-existing-status ${st.cls}`}>{st.text}</span>
                </div>
              )
            })}
          </div>
        </div>
      )}

      {/* 不匹配警告（顶部醒目位置）— 自定义卡片，字段化对比，强呼吸 */}
      {mismatchItems && mismatchItems.length > 0 && (
        <div className="pfm-mismatch-card" role="alert">
          <div className="pfm-mismatch-glow" aria-hidden="true" />
          <div className="pfm-mismatch-head">
            <span className="pfm-mismatch-badge">
              <WarningOutlined className="pfm-mismatch-badge-icon" />
            </span>
            <div className="pfm-mismatch-title">
              <strong>信息不匹配</strong>
              <span className="pfm-mismatch-count">差异 · {mismatchItems.length} 处</span>
            </div>
            <button
              type="button"
              className="pfm-mismatch-close"
              aria-label="关闭"
              onClick={() => setMismatchItems(null)}
            >
              <CloseOutlined />
            </button>
          </div>
          <ul className="pfm-mismatch-list">
            {mismatchItems.map((item) => {
              const Icon = item.field === 'group' ? WechatOutlined : item.field === 'customer' ? UserOutlined : SwapOutlined
              return (
                <li key={item.field} className={`pfm-mismatch-row${item.blocking ? ' is-blocking' : ''}`}>
                  <div className="pfm-mismatch-row-head">
                    <Icon className="pfm-mismatch-row-icon" />
                    <span className="pfm-mismatch-row-label">{item.label}</span>
                    {item.blocking && <span className="pfm-mismatch-block-tag">需处理</span>}
                  </div>
                  {item.hint && <div className="pfm-mismatch-row-hint">{item.hint}</div>}
                  <div className="pfm-mismatch-pair">
                    <div className="pfm-mismatch-line is-actual">
                      <span className="pfm-mismatch-tag">合同</span>
                      <span className="pfm-mismatch-val">{item.actual}</span>
                    </div>
                    <div className="pfm-mismatch-line is-extracted">
                      <span className="pfm-mismatch-tag">识别</span>
                      <span className="pfm-mismatch-val">{item.extracted}</span>
                    </div>
                  </div>
                </li>
              )
            })}
          </ul>
        </div>
      )}

      {step === 'form' ? (<><Form form={form} layout="vertical" requiredMark="optional" className="pfm-form">
        {/* 1. 款项说明 + 2. 日期（一行两列） */}
        <div className="pfm-row">
          <Form.Item
            name="installment_name"
            label={<span className="pfm-label"><i className="pfm-seq">1</i>款项说明</span>}
            rules={[{ required: true, message: '请填写款项说明' }]}
          >
            <Input placeholder="如：定金、尾款、现牌款、保险费" maxLength={100} />
          </Form.Item>

          <Form.Item
            name="paid_date"
            label={<span className="pfm-label"><i className="pfm-seq">2</i>日期</span>}
            rules={[{ required: true, message: '请选择日期' }]}
          >
            <DatePicker style={{ width: '100%' }} placeholder="选择付款日期" />
          </Form.Item>
        </div>

        {/* 3. 收款账户（收入）/ 收款方（支出） */}
        {isIncome ? (
          <Form.Item
            name="payment_account_id"
            label={<span className="pfm-label"><i className="pfm-seq">3</i>收款账户</span>}
            rules={[{ required: true, message: '请选择收款账户' }]}
          >
            <Select
              placeholder="选择己方收款账户"
              showSearch
              optionFilterProp="label"
              options={accounts.map(a => ({
                label: a.title + (a.account_number ? ` · ${a.account_number}` : ''),
                value: a.id,
              }))}
              dropdownRender={(menu) => (
                <>
                  {menu}
                  <div className="pfm-account-add">
                    <a onClick={(e) => { e.preventDefault(); setAddAccountOpen(true) }}>
                      <PlusOutlined /> 新增其他账户
                    </a>
                  </div>
                </>
              )}
            />
          </Form.Item>
        ) : (
          <div className="pfm-counterparty">
            {/* 3a. 付款方式（支出专属，决定下方字段联动） */}
            <Form.Item
              name="payment_method"
              label={<span className="pfm-label"><i className="pfm-seq">3</i>付款方式</span>}
              rules={[{ required: true, message: '请选择付款方式' }]}
            >
              <Select
                placeholder="选择这笔支出的付款方式"
                options={[
                  { label: '银行转账', value: 'bank_transfer' },
                  { label: '微信', value: 'wechat' },
                  { label: '支付宝', value: 'alipay' },
                  { label: '现金', value: 'cash' },
                  { label: '支票', value: 'check' },
                ]}
              />
            </Form.Item>
            {/* 3b. 收款方名称（始终需要） */}
            <Form.Item
              name="payee_name"
              label={<span className="pfm-label"><i className="pfm-seq">4</i>收款方</span>}
              rules={[{ required: true, message: '请填写收款方名称' }]}
            >
              <Input placeholder="如：陈丽思、XX修理厂" maxLength={200} />
            </Form.Item>
            {/* 3c. 银行账户信息（仅银行转账/支票时显示） */}
            {showBankFields && (
              <>
                <div className="pfm-row-2">
                  <Form.Item name="bank_name" label="开户行">
                    <Input placeholder="如：中信银行" maxLength={100} />
                  </Form.Item>
                  <Form.Item name="branch" label="网点">
                    <Input placeholder="如：深圳梅林支行" maxLength={200} />
                  </Form.Item>
                </div>
                <div className="pfm-row-2">
                  <Form.Item name="account_name" label="户名">
                    <Input placeholder="对方账户户名" maxLength={200} />
                  </Form.Item>
                  <Form.Item name="account_number" label="卡号/账号">
                    <Input placeholder="对方银行卡号或账号" maxLength={100} />
                  </Form.Item>
                </div>
              </>
            )}
            {/* 3d. 非现金方式（微信/支付宝/支票）可选填账号 */}
            {showAccountNoField && !showBankFields && (
              <Form.Item name="account_number" label="账号（选填）">
                <Input placeholder="对方微信/支付宝/支票账号" maxLength={100} />
              </Form.Item>
            )}
          </div>
        )}

        {/* 金额 + 币种 */}
        <Form.Item label={<span className="pfm-label"><i className="pfm-seq">{seqAmount}</i>金额</span>} required>
          <div className="pfm-amount-row">
            <Form.Item name="amount" noStyle rules={[{ required: true, message: '请输入金额' }]}>
              <InputNumber style={{ width: '100%' }} min={0} precision={2} placeholder="0.00" className="pfm-amount-input" />
            </Form.Item>
            <Form.Item name="currency" noStyle rules={[{ required: true }]}>
              <Select
                className="pfm-currency-select"
                options={[
                  { label: '人民币 CNY', value: 'CNY' },
                  { label: '港币 HKD', value: 'HKD' },
                ]}
              />
            </Form.Item>
          </div>
        </Form.Item>

        {/* 结算状态/备注 */}
        <Form.Item
          name="notes"
          label={<span className="pfm-label"><i className="pfm-seq">{seqNotes}</i>结算状态 / 备注</span>}
        >
          <Input.TextArea rows={2} placeholder="如：车辆总价+杂费已结清" maxLength={500} />
        </Form.Item>

        {/* ── 凭证 + 收支模板图（一行两列） ── */}
        <div className={`pfm-upload-section ${themeClass}`}>
          <div className="pfm-upload-columns">
            {/* 左列：凭证 */}
            <div className="pfm-upload-col pfm-upload-col-receipt">
              <div className="pfm-col-header">
                <span className="pfm-col-title">
                  <i className="pfm-seq">{seqNotes + 1}</i>凭证
                  <span className="pfm-receipt-tag pfm-required">必传</span>
                </span>
              </div>
              <div className="pfm-col-content">
                {!uploadedFile ? (
                  <Upload.Dragger
                    accept="image/*,.pdf,.heic,.heif"
                    maxCount={1}
                    showUploadList={false}
                    beforeUpload={handleReceiptUpload}
                    className="pfm-uploader pfm-uploader-compact"
                  >
                    <p className="ant-upload-drag-icon" style={{ marginBottom: 4 }}><InboxOutlined style={{ fontSize: 22 }} /></p>
                    <p className="ant-upload-text" style={{ fontSize: 13, marginBottom: 2 }}>点击或拖拽上传凭证</p>
                    <p className="ant-upload-hint" style={{ fontSize: 11 }}>JPG / PNG / PDF</p>
                  </Upload.Dragger>
                ) : (
                  <div className="pfm-file-preview">
                    <div className="pfm-file-preview-left">
                      {uploadedFile.preview_url ? (
                        <div className="pfm-file-thumb-wrap">
                          <img src={uploadedFile.preview_url} alt={uploadedFile.file_name} className="pfm-file-thumb" />
                        </div>
                      ) : uploadedFile.file_type === 'application/pdf' ? (
                        <div className="pfm-file-icon-wrap pfm-pdf">
                          <FilePdfOutlined style={{ fontSize: 28 }} />
                        </div>
                      ) : (
                        <div className="pfm-file-icon-wrap pfm-generic">
                          <FileOutlined style={{ fontSize: 28 }} />
                        </div>
                      )}
                      <div className="pfm-file-meta">
                        <span className="pfm-file-name" title={uploadedFile.file_name}>{uploadedFile.file_name}</span>
                        <span className="pfm-file-status">
                          <span className="pfm-file-check">✓</span> 已上传
                        </span>
                      </div>
                    </div>
                    <a className="pfm-file-remove" onClick={handleRemoveReceipt}>
                      <DeleteOutlined />
                    </a>
                  </div>
                )}
              </div>
              <div className="pfm-col-hint">必传：仅作存储，可在合同详情查看</div>
            </div>
          </div>

        </div>
      </Form>

      {currencyMismatch && (
        <Alert
          type="warning"
          showIcon
          style={{ marginTop: 4 }}
          message={`所选币种与合同币种（${contractCurrency}）不一致，系统将按所选币种记账并折算。`}
        />
      )}</>
      ) : (
        <div className="pfm-input-step" style={{ minHeight: 320, display: 'flex', flexDirection: 'column', gap: 16 }}>
          <Input.TextArea
            value={inputText}
            onChange={e => setInputText(e.target.value)}
            placeholder={isIncome ? INPUT_PLACEHOLDER_INCOME : INPUT_PLACEHOLDER_EXPENSE}
            rows={10}
            maxLength={8000}
            showCount
          />
        </div>
      )}

      {/* 新增收款账户子弹窗 */}
      <Modal
        title="新增收款账户"
        open={addAccountOpen}
        onOk={handleAddAccount}
        onCancel={() => setAddAccountOpen(false)}
        okText="添加"
        cancelText="取消"
        destroyOnClose
      >
        <Form layout="vertical">
          <Form.Item label="账户类型" required>
            <Select
              value={newAccount.account_type}
              onChange={(v) => setNewAccount({ ...newAccount, account_type: v })}
              options={[
                { label: '银行账户', value: 'bank' },
                { label: '支付宝', value: 'alipay' },
                { label: '微信', value: 'wechat' },
                { label: '现金', value: 'cash' },
                { label: '其他', value: 'other' },
              ]}
            />
          </Form.Item>
          <Form.Item label="展示标题" required>
            <Input value={newAccount.title} onChange={(e) => setNewAccount({ ...newAccount, title: e.target.value })} placeholder="如：高山香港账户" />
          </Form.Item>
          <Form.Item label="户名" required>
            <Input value={newAccount.account_name} onChange={(e) => setNewAccount({ ...newAccount, account_name: e.target.value })} placeholder="账户所有人姓名/公司名" />
          </Form.Item>
          <div style={{ display: 'flex', gap: 12 }}>
            <Form.Item label="银行名称" style={{ flex: 1 }}>
              <Input value={newAccount.bank_name} onChange={(e) => setNewAccount({ ...newAccount, bank_name: e.target.value })} placeholder="如：华侨银行" />
            </Form.Item>
            <Form.Item label="账号" style={{ flex: 1 }}>
              <Input value={newAccount.account_number} onChange={(e) => setNewAccount({ ...newAccount, account_number: e.target.value })} placeholder="银行账号" />
            </Form.Item>
          </div>
          <Form.Item label="网点">
            <Input value={newAccount.branch} onChange={(e) => setNewAccount({ ...newAccount, branch: e.target.value })} placeholder="如：汕尾海丰东门头支行" />
          </Form.Item>
        </Form>
      </Modal>
    </Modal>
  )
}
