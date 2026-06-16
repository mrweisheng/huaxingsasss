import { useEffect, useState } from 'react'
import { Modal, Form, Input, InputNumber, Select, DatePicker, Upload, Alert, message, Divider } from 'antd'
import { PlusOutlined, InboxOutlined } from '@ant-design/icons'
import dayjs from 'dayjs'
import type { UploadFile } from 'antd'
import {
  paymentApi,
  type PaymentCreatePayload,
  type PaymentUpdatePayload,
  type CounterpartyAccount,
} from '@/services/payment'
import { paymentAccountApi, type PaymentAccount } from '@/services/paymentAccount'
import { compressImage } from '@/utils/imageCompress'
import type { Payment } from '@/types'

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
  open, mode, contractId, contractNumber, customerName, contractTitle,
  totalAmount, currency, paymentType, editing, onClose, onSuccess,
}: Props) {
  const [form] = Form.useForm()
  const [submitting, setSubmitting] = useState(false)
  const [accounts, setAccounts] = useState<PaymentAccount[]>([])
  const [addAccountOpen, setAddAccountOpen] = useState(false)
  const [newAccount, setNewAccount] = useState({ account_type: 'bank', title: '', account_name: '', account_number: '', bank_name: '', branch: '' })
  const [uploading, setUploading] = useState(false)
  const [uploadedFileId, setUploadedFileId] = useState<string | undefined>(undefined)
  const [receiptCleared, setReceiptCleared] = useState(false)
  const isEdit = mode === 'edit'
  const isIncome = isEdit ? editing?.type === 'income' : paymentType === 'income'
  const contractCurrency = editing?.contract_currency || currency

  const typeLabel = isIncome ? '收入' : '支出'

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
    setUploadedFileId(undefined)
    setReceiptCleared(false)
    if (isEdit && editing) {
      form.setFieldsValue({
        amount: editing.paid_amount,
        currency: editing.currency,
        paid_date: editing.paid_date ? dayjs(editing.paid_date) : undefined,
        payment_method: editing.payment_method,
        installment_name: editing.installment_name,
        description: editing.description,
        notes: editing.notes,
        payment_account_id: editing.payment_account_id,
        payee_name: editing.payee_name,
        ...editing.counterparty_account,
      })
    } else {
      form.resetFields()
      form.setFieldsValue({
        currency: contractCurrency || 'CNY',
        paid_date: dayjs(),
        payment_method: isIncome ? 'bank_transfer' : 'bank_transfer',
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
      const compressed = await compressImage(file)
      const res = await paymentApi.uploadReceipt(compressed)
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
        const payload: PaymentCreatePayload = {
          type: paymentType!,
          currency: values.currency,
          amount: Number(values.amount),
          paid_date: values.paid_date.format('YYYY-MM-DD'),
          payment_method: values.payment_method,
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
        const payload: PaymentUpdatePayload = {
          amount: Number(values.amount),
          currency: values.currency,
          paid_date: values.paid_date.format('YYYY-MM-DD'),
          payment_method: values.payment_method,
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
      title={`${isEdit ? '编辑' : '录入'}${typeLabel}${contractNumber ? ` · ${contractNumber}` : ''}`}
      open={open}
      onOk={handleOk}
      onCancel={onClose}
      confirmLoading={submitting}
      okButtonProps={{ disabled: !canSubmit }}
      okText={isEdit ? '保存' : '提交'}
      cancelText="取消"
      destroyOnClose
      maskClosable={false}
      width={560}
    >
      {/* 合同上下文回显 */}
      {(contractTitle || customerName) && (
        <div style={{ marginBottom: 16, padding: '8px 12px', background: '#f5f5f5', borderRadius: 6, fontSize: 13 }}>
          {contractTitle && <div style={{ color: '#333' }}>业务：{contractTitle}</div>}
          {customerName && <div style={{ color: '#666', marginTop: 2 }}>客户：{customerName}</div>}
          {totalAmount != null && <div style={{ color: '#666', marginTop: 2 }}>合同金额：{totalAmount} {contractCurrency}</div>}
        </div>
      )}

      <Form form={form} layout="vertical" requiredMark="optional">
        <div style={{ display: 'flex', gap: 12 }}>
          <Form.Item name="amount" label="金额" rules={[{ required: true, message: '请输入金额' }]} style={{ flex: 1 }}>
            <InputNumber style={{ width: '100%' }} min={0} precision={2} placeholder="0.00" />
          </Form.Item>
          <Form.Item name="currency" label="货币单位" rules={[{ required: true }]} style={{ width: 130 }}>
            <Select options={[
              { label: '人民币 CNY', value: 'CNY' },
              { label: '港币 HKD', value: 'HKD' },
            ]} />
          </Form.Item>
        </div>

        <div style={{ display: 'flex', gap: 12 }}>
          <Form.Item name="paid_date" label="日期" rules={[{ required: true, message: '请选择日期' }]} style={{ flex: 1 }}>
            <DatePicker style={{ width: '100%' }} />
          </Form.Item>
          <Form.Item name="payment_method" label="方式" style={{ width: 160 }}>
            <Select allowClear placeholder="选择方式" options={[
              { label: '银行转账', value: 'bank_transfer' },
              { label: '微信', value: 'wechat' },
              { label: '支付宝', value: 'alipay' },
              { label: '现金', value: 'cash' },
              { label: '支票', value: 'check' },
            ]} />
          </Form.Item>
        </div>

        <Form.Item name="installment_name" label="款项说明" tooltip="对应模板第1项，如：定金、尾款、现牌款等">
          <Input placeholder="如：定金、尾款、现牌款" maxLength={100} />
        </Form.Item>

        {/* 收入专属：收款账户 */}
        {isIncome && (
          <>
            <Divider style={{ margin: '8px 0 16px', fontSize: 12 }} orientation="left" plain>
              收款账户（己方）
            </Divider>
            <Form.Item name="payment_account_id" label="收款账户" rules={[{ required: true, message: '请选择收款账户' }]}>
              <Select
                placeholder="选择收款账户"
                showSearch
                optionFilterProp="label"
                options={[
                  ...accounts.map(a => ({
                    label: a.title + (a.account_number ? ` · ${a.account_number}` : ''),
                    value: a.id,
                  })),
                ]}
                dropdownRender={(menu) => (
                  <>
                    {menu}
                    <div style={{ padding: '4px 8px', borderTop: '1px dashed #d9d9d9', marginTop: 4 }}>
                      <a onClick={(e) => { e.preventDefault(); setAddAccountOpen(true) }}>
                        <PlusOutlined /> 新增其他账户
                      </a>
                    </div>
                  </>
                )}
              />
            </Form.Item>
          </>
        )}

        {/* 支出专属：对方账户（供应商不固定，每次手填） */}
        {!isIncome && (
          <>
            <Divider style={{ margin: '8px 0 16px', fontSize: 12 }} orientation="left" plain>
              收款方（对方）
            </Divider>
            <Form.Item name="payee_name" label="收款方名称" rules={[{ required: true, message: '请填写收款方名称' }]}>
              <Input placeholder="如：陈丽思、XX修理厂" maxLength={200} />
            </Form.Item>
            <div style={{ display: 'flex', gap: 12 }}>
              <Form.Item name="bank_name" label="开户行" style={{ flex: 1 }}>
                <Input placeholder="如：中信银行" maxLength={100} />
              </Form.Item>
              <Form.Item name="branch" label="网点" style={{ flex: 1 }}>
                <Input placeholder="如：深圳梅林支行" maxLength={200} />
              </Form.Item>
            </div>
            <Form.Item name="account_name" label="户名">
              <Input placeholder="对方账户户名" maxLength={200} />
            </Form.Item>
            <Form.Item name="account_number" label="卡号/账号">
              <Input placeholder="对方银行卡号或账号" maxLength={100} />
            </Form.Item>
          </>
        )}

        {/* 凭证上传 */}
        <Divider style={{ margin: '8px 0 16px', fontSize: 12 }} orientation="left" plain>
          凭证 {isIncome && <span style={{ color: '#ff4d4f' }}>*必传</span>}
        </Divider>

        {isIncome ? (
          <Form.Item
            extra={
              uploadedFileId
                ? '✓ 已上传，提交后将自动校验凭证金额/付款方'
                : isEdit && editing?.receipt_image_path && !receiptCleared
                  ? '保留原凭证（如需更换请重新上传）'
                  : '收入必须上传凭证才能提交'
            }
          >
            <Upload.Dragger
              accept="image/*,.pdf"
              maxCount={1}
              showUploadList={!!uploadedFileId}
              beforeUpload={handleUpload}
              onRemove={() => { setUploadedFileId(undefined); return true }}
              fileList={uploadedFileId ? [{ uid: uploadedFileId, name: '凭证' } as UploadFile] : []}
            >
              <p className="ant-upload-drag-icon"><InboxOutlined /></p>
              <p className="ant-upload-text">点击或拖拽上传凭证</p>
              <p className="ant-upload-hint">支持 JPG/PNG/HEIC/PDF，单文件 ≤ 50MB</p>
            </Upload.Dragger>
            {isEdit && editing?.receipt_image_path && !uploadedFileId && (
              <div style={{ marginTop: 8 }}>
                <a style={{ color: '#ff4d4f' }} onClick={() => setReceiptCleared(true)}>
                  {receiptCleared ? '✓ 已标记清除凭证（需重新上传才能提交）' : '清除原凭证'}
                </a>
              </div>
            )}
          </Form.Item>
        ) : (
          <Form.Item
            extra={
              uploadedFileId
                ? '✓ 已上传凭证（支出凭证仅做校验提醒，不影响结算）'
                : '支出凭证可选；不上传将标记为无凭证支出'
            }
          >
            <Upload.Dragger
              accept="image/*,.pdf"
              maxCount={1}
              showUploadList={!!uploadedFileId}
              beforeUpload={handleUpload}
              onRemove={() => { setUploadedFileId(undefined); return true }}
              fileList={uploadedFileId ? [{ uid: uploadedFileId, name: '凭证' } as UploadFile] : []}
            >
              <p className="ant-upload-drag-icon"><InboxOutlined /></p>
              <p className="ant-upload-text">点击或拖拽上传凭证（可选）</p>
              <p className="ant-upload-hint">支持 JPG/PNG/HEIC/PDF</p>
            </Upload.Dragger>
          </Form.Item>
        )}

        <Form.Item name="notes" label="结算状态/备注" tooltip="对应模板第6项，如：车辆总价+杂费已结清">
          <Input.TextArea rows={2} placeholder="如：车辆总价+杂费已结清" maxLength={500} />
        </Form.Item>
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
