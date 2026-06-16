import { useEffect, useState } from 'react'
import { Modal, Form, Input, InputNumber, Select, DatePicker, Upload, Alert, message } from 'antd'
const { useWatch } = Form
import { PlusOutlined, InboxOutlined, FilePdfOutlined, FileOutlined, DeleteOutlined, EyeOutlined } from '@ant-design/icons'
import dayjs from 'dayjs'
import {
  paymentApi,
  type PaymentCreatePayload,
  type PaymentUpdatePayload,
  type CounterpartyAccount,
} from '@/services/payment'
import { paymentAccountApi, type PaymentAccount } from '@/services/paymentAccount'
import { compressImage } from '@/utils/imageCompress'
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

interface Props {
  open: boolean
  mode: 'add' | 'edit'
  /** 合同上下文（add 必填；edit 时用于回显） */
  contractId?: number
  contractNumber?: string
  customerName?: string
  contractTitle?: string
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
 * - 收入：凭证必传，收款账户下拉（预设 payment_accounts，可选"其他"即时新增）；
 *   提交后后端异步校验凭证金额/付款方，不符则标红置顶不结算。
 * - 支出：对方账户手填（供应商不固定），凭证可选，无凭证可声明。
 */
export default function PaymentFormModal({
  open, mode, contractId, customerName, contractTitle,
  currency, paymentType, editing, onClose, onSuccess,
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

  // 打开时初始化表单
  useEffect(() => {
    if (!open) return
    // 清理旧的预览 URL
    if (uploadedFile?.preview_url) URL.revokeObjectURL(uploadedFile.preview_url)
    setUploadedFileId(undefined)
    setUploadedFile(null)
    setReceiptCleared(false)
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

  // 收入必须已上传凭证才能提交；编辑时若未换凭证且未清除，沿用原凭证
  const canSubmit = !submitting && !uploading && (
    !isIncome || !!uploadedFileId || (isEdit && !!editing?.receipt_image_path && !receiptCleared)
  )

  const handleUpload = async (file: File) => {
    setUploading(true)
    try {
      const isImage = file.type.startsWith('image/')
      // 先创建预览 URL（用原始文件，保证预览清晰度）
      const previewUrl = isImage ? URL.createObjectURL(file) : undefined
      const compressed = await compressImage(file)
      const res = await paymentApi.uploadReceipt(compressed)
      // 清理旧预览 URL
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
    return false  // 阻止 antd 默认上传
  }

  const handleRemoveFile = () => {
    if (uploadedFile?.preview_url) URL.revokeObjectURL(uploadedFile.preview_url)
    setUploadedFile(null)
    setUploadedFileId(undefined)
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
    try {
      const values = await form.validateFields()
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
          if (!uploadedFileId) {
            message.error('收入必须上传凭证')
            return
          }
          payload.receipt_file_id = uploadedFileId
        } else {
          payload.payee_name = values.payee_name?.trim() || undefined
          const cp: CounterpartyAccount = {}
          if (values.account_name) cp.account_name = values.account_name.trim()
          if (values.account_number) cp.account_number = values.account_number.trim()
          if (values.bank_name) cp.bank_name = values.bank_name.trim()
          if (values.branch) cp.branch = values.branch.trim()
          if (Object.keys(cp).length) payload.counterparty_account = cp
          if (uploadedFileId) payload.receipt_file_id = uploadedFileId
          else payload.no_receipt = true
        }
        await paymentApi.create(contractId!, payload)
        message.success(`${typeLabel}已录入${isIncome ? '，正在校验凭证…' : ''}`)
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
          payload.counterparty_account = Object.keys(cp).length ? cp : undefined
        }
        // 凭证变化
        if (uploadedFileId) payload.receipt_file_id = uploadedFileId
        else if (receiptCleared) payload.receipt_file_id = ''
        await paymentApi.update(editing!.id, payload)
        message.success(`${typeLabel}已更新${isIncome && (uploadedFileId || receiptCleared) ? '，正在重新校验…' : ''}`)
      }
      onSuccess()
      onClose()
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
      onOk={handleOk}
      onCancel={onClose}
      confirmLoading={submitting}
      okButtonProps={{ disabled: !canSubmit }}
      okText={isEdit ? '保存' : '提交'}
      cancelText="取消"
      destroyOnClose
      maskClosable={false}
      width={760}
      className={`pfm-modal ${themeClass}`}
    >
      {/* 顶部信息区：业务描述 + 客户（去冗余，不展示合同编号） */}
      {(contractTitle || customerName) && (
        <div className={`pfm-context ${themeClass}`}>
          {contractTitle && <div className="pfm-context-title">{contractTitle}</div>}
          {customerName && <div className="pfm-context-sub">客户 · {customerName}</div>}
        </div>
      )}

      <Form form={form} layout="vertical" requiredMark="optional" className="pfm-form">
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

        {/* 凭证上传区（底部） */}
        <div className={`pfm-receipt-section ${themeClass}`}>
          <div className="pfm-receipt-header">
            <span className="pfm-receipt-title">
              <i className="pfm-seq">6</i>凭证
              {isIncome
                ? <span className="pfm-receipt-tag pfm-required">必传</span>
                : <span className="pfm-receipt-tag pfm-optional">可选</span>}
            </span>
            <span className="pfm-receipt-hint">
              {isIncome
                ? (uploadedFileId ? '✓ 已上传，提交后自动校验' : '收入必须上传凭证')
                : (uploadedFileId ? '✓ 已上传（仅做校验提醒）' : '不上传则标记为无凭证支出')}
            </span>
          </div>

          {!uploadedFile ? (
            <Upload.Dragger
              accept="image/*,.pdf"
              maxCount={1}
              showUploadList={false}
              beforeUpload={handleUpload}
              className="pfm-uploader pfm-uploader-compact"
            >
              <p className="ant-upload-drag-icon" style={{ marginBottom: 4 }}><InboxOutlined style={{ fontSize: 22 }} /></p>
              <p className="ant-upload-text" style={{ fontSize: 13, marginBottom: 2 }}>点击或拖拽上传凭证</p>
              <p className="ant-upload-hint" style={{ fontSize: 11 }}>支持 JPG / PNG / HEIC / PDF，单文件 ≤ 50MB</p>
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
                    {uploadedFile.preview_url && (
                      <a
                        className="pfm-file-preview-link"
                        href={uploadedFile.preview_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        onClick={(e) => e.stopPropagation()}
                      >
                        <EyeOutlined /> 预览
                      </a>
                    )}
                  </span>
                </div>
              </div>
              <a className="pfm-file-remove" onClick={handleRemoveFile}>
                <DeleteOutlined /> 删除
              </a>
            </div>
          )}

          {isEdit && editing?.receipt_image_path && !uploadedFileId && (
            <div className="pfm-clear-receipt">
              <a className="pfm-clear-link" onClick={() => setReceiptCleared(!receiptCleared)}>
                {receiptCleared ? '✓ 已标记清除（需重新上传才能提交）' : '清除原凭证'}
              </a>
            </div>
          )}
        </div>
      </Form>

      {currencyMismatch && (
        <Alert
          type="warning"
          showIcon
          style={{ marginTop: 4 }}
          message={`所选币种与合同币种（${contractCurrency}）不一致，系统将按所选币种记账并折算。`}
        />
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
