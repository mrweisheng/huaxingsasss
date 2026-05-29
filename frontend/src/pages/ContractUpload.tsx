import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Upload, Button, message, Card, Steps, Progress } from 'antd'
import { InboxOutlined } from '@ant-design/icons'
import { contractApi } from '@/services/contract'

const { Dragger } = Upload

export default function ContractUpload() {
  const navigate = useNavigate()
  const [uploading, setUploading] = useState(false)
  const [contractId, setContractId] = useState<number | null>(null)
  const [parsing, setParsing] = useState(false)
  const [parseProgress, setParseProgress] = useState(0)

  const handleUpload = async (file: File) => {
    setUploading(true)
    setContractId(null)
    setParsing(false)
    setParseProgress(0)
    try {
      const result = await contractApi.uploadAndParse(file)
      setContractId(result.contract_id)
      setUploading(false)

      // 轮询解析状态
      setParsing(true)
      setParseProgress(30)
      let attempts = 0
      const maxAttempts = 20
      const poll = setInterval(async () => {
        attempts++
        try {
          const status = await contractApi.getParseStatus(result.contract_id!)
          if (status.data?.status === 'completed') {
            clearInterval(poll)
            setParseProgress(100)
            setParsing(false)
            message.success('合同解析完成')
            setTimeout(() => navigate(`/contracts/${result.contract_id}`), 1000)
          } else {
            setParseProgress(Math.min(30 + attempts * 5, 90))
          }
        } catch {
          // 解析状态查询失败不影响主流程
        }
        if (attempts >= maxAttempts) {
          clearInterval(poll)
          setParsing(false)
          message.info('解析时间较长，请稍后在合同列表查看结果')
        }
      }, 3000)
    } catch (error: any) {
      message.error(error.response?.data?.detail || '上传失败')
      setUploading(false)
    }
    return false
  }

  if (contractId) {
    return (
      <Card title="上传合同">
        <Steps
          current={parsing ? 1 : 2}
          items={[
            { title: '上传文件', description: '已完成' },
            { title: 'AI 解析', description: parsing ? '解析中...' : '已完成' },
            { title: '完成' },
          ]}
          style={{ marginBottom: 24 }}
        />
        {parsing && <Progress percent={parseProgress} status="active" />}
        <div style={{ marginTop: 16, textAlign: 'center' }}>
          <Button onClick={() => navigate('/contracts')}>返回合同列表</Button>
          <Button type="link" onClick={() => navigate(`/contracts/${contractId}`)}>查看合同</Button>
        </div>
      </Card>
    )
  }

  return (
    <Card title="上传合同">
      <Dragger
        accept="image/jpeg,image/png,image/jpg,.pdf"
        maxCount={1}
        customRequest={({ file }) => handleUpload(file as File)}
        showUploadList={false}
        disabled={uploading}
      >
        <p className="ant-upload-drag-icon"><InboxOutlined /></p>
        <p className="ant-upload-text">点击或拖拽合同文件到此区域</p>
        <p className="ant-upload-hint">支持 JPG/PNG 图片和 PDF 格式，最大 50MB</p>
      </Dragger>
    </Card>
  )
}
