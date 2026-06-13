import { useEffect, useState } from 'react'
import { Modal, Form, Input, InputNumber, Select, DatePicker, Alert, message } from 'antd'
import dayjs from 'dayjs'
import type { ContractAdditionalItem } from '@/types'
import { additionalItemApi, type AdditionalItemInput } from '@/services/contractAdditionalItem'

interface Props {
  open: boolean
  mode: 'add' | 'edit'
  contractId: number
  /** 合同主币种：用于默认值 + 币种不一致弱提醒 */
  contractCurrency: string
  editing?: ContractAdditionalItem | null
  onClose: () => void
  onSuccess: () => void
}

/**
 * 合同附加项 新增/编辑 表单 Modal（add/edit 共用，mode 区分）。
 * 纯表单 CRUD，不走 Agent（CLAUDE.md 铁律：字段固定的结构化录入用表单）。
 * 币种与合同不一致时底部黄色弱提醒，不拦截提交。
 */
export default function AdditionalItemFormModal({
  open, mode, contractId, contractCurrency, editing, onClose, onSuccess,
}: Props) {
  const [form] = Form.useForm()
  const [submitting, setSubmitting] = useState(false)
  const isEdit = mode === 'edit'
  const currency = Form.useWatch('currency', form)
  const currencyMismatch = !!currency && currency !== contractCurrency

  useEffect(() => {
    if (!open) return
    if (isEdit && editing) {
      form.setFieldsValue({
        name: editing.name,
        amount: editing.amount,
        currency: editing.currency,
        paid_to: editing.paid_to,
        description: editing.description,
        occurred_date: editing.occurred_date ? dayjs(editing.occurred_date) : undefined,
        remarks: editing.remarks,
      })
    } else {
      form.resetFields()
      form.setFieldsValue({ currency: contractCurrency })
    }
  }, [open, isEdit, editing, form, contractCurrency])

  const handleOk = async () => {
    try {
      const values = await form.validateFields()
      setSubmitting(true)
      const payload: AdditionalItemInput = {
        name: values.name.trim(),
        amount: Number(values.amount),
        currency: values.currency,
        paid_to: values.paid_to?.trim() || undefined,
        description: values.description?.trim() || undefined,
        occurred_date: values.occurred_date ? values.occurred_date.format('YYYY-MM-DD') : undefined,
        remarks: values.remarks?.trim() || undefined,
      }
      if (isEdit && editing) {
        await additionalItemApi.update(editing.id, payload)
        message.success('附加项已更新')
      } else {
        await additionalItemApi.create(contractId, payload)
        message.success('附加项已添加')
      }
      onSuccess()
      onClose()
    } catch (e: any) {
      // 表单校验失败（errorFields）由 antd 自行展示，不重复提示
      if (e?.errorFields) return
      message.error(e?.response?.data?.detail || '操作失败')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <Modal
      title={isEdit ? '编辑附加项' : '添加附加项'}
      open={open}
      onOk={handleOk}
      onCancel={onClose}
      confirmLoading={submitting}
      okText={isEdit ? '保存' : '添加'}
      cancelText="取消"
      destroyOnClose
      maskClosable={false}
    >
      <Form form={form} layout="vertical" requiredMark="optional">
        <Form.Item name="name" label="项目名称" rules={[{ required: true, message: '请输入项目名称' }]}>
          <Input placeholder="如：车险、保养改装、过户费、人工费" maxLength={200} />
        </Form.Item>
        <div style={{ display: 'flex', gap: 12 }}>
          <Form.Item name="amount" label="金额" rules={[{ required: true, message: '请输入金额' }]} style={{ flex: 1 }}>
            <InputNumber style={{ width: '100%' }} min={0} precision={2} placeholder="0.00" />
          </Form.Item>
          <Form.Item name="currency" label="货币单位" rules={[{ required: true }]} style={{ width: 130 }}>
            <Select
              options={[
                { label: '人民币 CNY', value: 'CNY' },
                { label: '港币 HKD', value: 'HKD' },
              ]}
            />
          </Form.Item>
        </div>
        <Form.Item name="paid_to" label="付给谁">
          <Input placeholder="如：太平洋保险、XX修理厂" maxLength={200} />
        </Form.Item>
        <Form.Item name="occurred_date" label="发生日期">
          <DatePicker style={{ width: '100%' }} placeholder="备查用，可选" />
        </Form.Item>
        <Form.Item name="description" label="费用说明">
          <Input.TextArea rows={2} placeholder="如：基础三责险 + 车损" maxLength={500} />
        </Form.Item>
        <Form.Item name="remarks" label="备注">
          <Input.TextArea rows={2} maxLength={500} />
        </Form.Item>
      </Form>
      {currencyMismatch && (
        <Alert
          type="warning"
          showIcon
          style={{ marginTop: 4 }}
          message="附加项币种与合同币种不一致，系统将按所选币种独立记账，不自动折算汇率。"
        />
      )}
    </Modal>
  )
}
