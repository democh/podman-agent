import { useState, useRef, useCallback } from 'react'
import { Upload, X, FileText, FileSpreadsheet, FileCode, File } from 'lucide-react'

// 支持的文件类型
const ACCEPTED_TYPES = [
  // Office
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document', // .docx
  'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', // .xlsx
  'application/vnd.openxmlformats-officedocument.presentationml.presentation', // .pptx
  // PDF
  'application/pdf',
  // 文本文件
  'text/plain',
  'text/markdown',
  'text/csv',
  'application/json',
  'text/xml',
  'application/xml',
  'text/yaml',
  'text/x-yaml',
  'text/x-python',
  'text/javascript',
  'text/typescript',
  'text/html',
  'text/css',
  'text/x-sh',
  'text/x-shellscript',
]

// 文件扩展名映射
const EXT_MAP: Record<string, string> = {
  docx: 'word', xlsx: 'excel', pptx: 'powerpoint', pdf: 'pdf',
  txt: 'text', md: 'text', csv: 'text', json: 'text', xml: 'text',
  yaml: 'text', yml: 'text', log: 'text', ini: 'text', cfg: 'text',
  py: 'text', js: 'text', ts: 'text', html: 'text', css: 'text',
  sh: 'text', bash: 'text',
}

const MAX_FILES = 10
const MAX_FILE_SIZE = 10 * 1024 * 1024 // 10MB

export interface UploadedFile {
  filename: string
  path: string
  size: number
  type: string
  markdown: string
}

export interface UploadError {
  filename: string
  message: string
}

interface FileUploadProps {
  onUploadComplete?: (files: UploadedFile[], errors: UploadError[]) => void
  onClose?: () => void
}

export function FileUpload({ onUploadComplete, onClose }: FileUploadProps) {
  const [files, setFiles] = useState<File[]>([])
  const [uploading, setUploading] = useState(false)
  const [progress, setProgress] = useState(0)
  const [errors, setErrors] = useState<string[]>([])
  const [dragOver, setDragOver] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)

  const validateFiles = useCallback((newFiles: File[]): { valid: File[], errors: string[] } => {
    const valid: File[] = []
    const errors: string[] = []

    for (const file of newFiles) {
      // 检查文件类型
      const ext = file.name.split('.').pop()?.toLowerCase() || ''
      const isAccepted = ACCEPTED_TYPES.includes(file.type) || EXT_MAP[ext]
      
      if (!isAccepted) {
        errors.push(`${file.name}: 不支持的文件类型`)
        continue
      }

      // 检查文件大小
      if (file.size > MAX_FILE_SIZE) {
        errors.push(`${file.name}: 文件过大 (${(file.size / 1024 / 1024).toFixed(1)}MB > 10MB)`)
        continue
      }

      valid.push(file)
    }

    // 检查总数量
    const total = files.length + valid.length
    if (total > MAX_FILES) {
      errors.push(`最多上传 ${MAX_FILES} 个文件，当前已选择 ${files.length} 个`)
      return { valid: valid.slice(0, MAX_FILES - files.length), errors }
    }

    return { valid, errors }
  }, [files.length])

  const handleFileSelect = useCallback((newFiles: FileList | null) => {
    if (!newFiles) return
    const { valid, errors: newErrors } = validateFiles(Array.from(newFiles))
    setFiles(prev => [...prev, ...valid])
    if (newErrors.length > 0) {
      setErrors(prev => [...prev, ...newErrors])
    }
  }, [validateFiles])

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    setDragOver(false)
    handleFileSelect(e.dataTransfer.files)
  }, [handleFileSelect])

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    setDragOver(true)
  }, [])

  const handleDragLeave = useCallback(() => {
    setDragOver(false)
  }, [])

  const removeFile = useCallback((index: number) => {
    setFiles(prev => prev.filter((_, i) => i !== index))
  }, [])

  const clearErrors = useCallback(() => {
    setErrors([])
  }, [])

  const handleUpload = useCallback(async () => {
    if (files.length === 0) return

    setUploading(true)
    setProgress(0)
    setErrors([])

    const formData = new FormData()
    files.forEach(file => formData.append('files', file))

    try {
      const response = await fetch('/api/upload', {
        method: 'POST',
        body: formData,
      })

      if (!response.ok) {
        let errMsg = '上传失败'
        try {
          const err = await response.json()
          errMsg = err.detail || errMsg
        } catch {
          errMsg = `上传失败 (HTTP ${response.status})`
        }
        throw new Error(errMsg)
      }

      const text = await response.text()
      if (!text) throw new Error('服务器返回空响应')
      const result = JSON.parse(text)
      setProgress(100)

      const uploadedFiles: UploadedFile[] = result.uploaded || []
      const uploadErrors: UploadError[] = (result.errors || []).map((msg: string) => ({
        filename: msg.split(':')[0],
        message: msg,
      }))

      onUploadComplete?.(uploadedFiles, uploadErrors)
      
      if (uploadErrors.length > 0) {
        setErrors(uploadErrors.map(e => e.message))
      }

      // 清空已上传的文件
      setFiles([])
    } catch (err) {
      setErrors([err instanceof Error ? err.message : '上传失败'])
    } finally {
      setUploading(false)
    }
  }, [files, onUploadComplete])

  const getFileIcon = (filename: string) => {
    const ext = filename.split('.').pop()?.toLowerCase() || ''
    switch (ext) {
      case 'docx':
      case 'doc':
        return <FileText size={20} className="file-icon word" />
      case 'xlsx':
      case 'xls':
        return <FileSpreadsheet size={20} className="file-icon excel" />
      case 'pdf':
        return <FileText size={20} className="file-icon pdf" />
      case 'py':
      case 'js':
      case 'ts':
      case 'html':
      case 'css':
      case 'json':
        return <FileCode size={20} className="file-icon code" />
      default:
        return <File size={20} className="file-icon" />
    }
  }

  const formatSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
    return `${(bytes / 1024 / 1024).toFixed(1)} MB`
  }

  return (
    <div className="file-upload-overlay" onClick={onClose}>
      <div className="file-upload-panel" onClick={e => e.stopPropagation()}>
        <div className="file-upload-header">
          <h3>上传文件</h3>
          <button className="close-btn" onClick={onClose}>
            <X size={18} />
          </button>
        </div>

        <div
          className={`upload-dropzone${dragOver ? ' drag-over' : ''}`}
          onDrop={handleDrop}
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onClick={() => inputRef.current?.click()}
        >
          <Upload size={32} />
          <p>拖拽文件到此处，或点击选择</p>
          <p className="upload-hint">
            支持 Office、PDF、文本文件，每个不超过 10MB，最多 10 个
          </p>
          <input
            ref={inputRef}
            type="file"
            multiple
            accept={ACCEPTED_TYPES.join(',')}
            onChange={e => handleFileSelect(e.target.files)}
            style={{ display: 'none' }}
          />
        </div>

        {errors.length > 0 && (
          <div className="upload-errors">
            {errors.map((err, i) => (
              <div key={i} className="error-item">
                <span>{err}</span>
                <button onClick={clearErrors}><X size={14} /></button>
              </div>
            ))}
          </div>
        )}

        {files.length > 0 && (
          <div className="file-list">
            <div className="file-list-header">
              <span>已选择 {files.length} 个文件</span>
              <button className="clear-btn" onClick={() => setFiles([])}>清空</button>
            </div>
            {files.map((file, i) => (
              <div key={i} className="file-item">
                {getFileIcon(file.name)}
                <div className="file-info">
                  <span className="file-name">{file.name}</span>
                  <span className="file-size">{formatSize(file.size)}</span>
                </div>
                <button className="remove-btn" onClick={() => removeFile(i)}>
                  <X size={14} />
                </button>
              </div>
            ))}
          </div>
        )}

        <div className="upload-actions">
          {uploading && (
            <div className="upload-progress">
              <div className="progress-bar" style={{ width: `${progress}%` }} />
            </div>
          )}
          <button
            className="btn btn-primary"
            disabled={files.length === 0 || uploading}
            onClick={handleUpload}
          >
            {uploading ? '上传中...' : `上传${files.length > 0 ? ` (${files.length})` : ''}`}
          </button>
        </div>
      </div>
    </div>
  )
}
