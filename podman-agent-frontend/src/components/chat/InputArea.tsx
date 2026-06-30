import { useRef, useEffect, useCallback, useState } from 'react'
import { SendHorizontal, Square, Paperclip } from 'lucide-react'
import { FileUpload } from './FileUpload'
import type { UploadedFile, UploadError } from './FileUpload'
import type { UploadedFileInfo } from '@/lib/types'

interface InputAreaProps {
  busy: boolean
  connected: boolean
  onSend: (content: string, files?: UploadedFileInfo[]) => void
  onStop: () => void
}

export function InputArea({ busy, connected, onSend, onStop }: InputAreaProps) {
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const [showUpload, setShowUpload] = useState(false)
  const [uploadedFiles, setUploadedFiles] = useState<UploadedFile[]>([])

  const autoResize = useCallback(() => {
    const el = textareaRef.current
    if (!el) return
    el.style.height = 'auto'
    el.style.height = Math.min(el.scrollHeight, 200) + 'px'
  }, [])

  useEffect(() => {
    autoResize()
  }, [autoResize])

  const handleSend = useCallback(() => {
    // 忙碌时点击按钮 = 停止（优先检查，不受 textarea 内容影响）
    if (busy) {
      onStop()
      return
    }
    const el = textareaRef.current
    if (!el) return
    const text = el.value.trim()
    if (!text || !connected) return
    // 将上传文件转换为 UploadedFileInfo 并随消息发送
    const files: UploadedFileInfo[] | undefined = uploadedFiles.length > 0
      ? uploadedFiles.map(f => ({
          filename: f.filename,
          path: f.path,
          size: f.size,
          type: f.type,
          markdown: f.markdown,
        }))
      : undefined
    onSend(text, files)
    el.value = ''
    setUploadedFiles([])
    autoResize()
  }, [busy, connected, onSend, onStop, autoResize, uploadedFiles])

  const handleKeyDown = useCallback((e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }, [handleSend])

  const handleFilesUploaded = useCallback((files: UploadedFile[], errors: UploadError[]) => {
    setUploadedFiles(prev => [...prev, ...files])
    if (errors.length === 0) {
      setShowUpload(false)
    }
  }, [])

  return (
    <div className="input-area">
      <div className="input-container">
        {/* 已上传文件列表 */}
        {uploadedFiles.length > 0 && (
          <div className="uploaded-files-bar">
            {uploadedFiles.map((file, i) => (
              <span key={i} className="uploaded-file-tag">
                {file.filename}
                <button onClick={() => setUploadedFiles(prev => prev.filter((_, idx) => idx !== i))}>
                  ×
                </button>
              </span>
            ))}
          </div>
        )}
        <div className="input-wrapper">
          <button
            className="upload-btn"
            onClick={() => setShowUpload(true)}
            disabled={busy}
            title="上传文件"
          >
            <Paperclip size={18} />
          </button>
          <div className="input-box">
            <textarea
              ref={textareaRef}
              placeholder="输入消息... (Enter 发送 · Shift+Enter 换行)"
              rows={1}
              disabled={busy}
              onInput={autoResize}
              onKeyDown={handleKeyDown}
            />
          </div>
          <button
            className={`btn btn-primary${busy ? ' btn-stop-mode' : ''}`}
            style={{ minHeight: 42 }}
            disabled={!busy && !connected}
            onClick={handleSend}
          >
            {busy ? <Square size={14} /> : <SendHorizontal size={14} />}
            <span>{busy ? '停止' : '发送'}</span>
          </button>
        </div>
      </div>

      {showUpload && (
        <FileUpload
          onUploadComplete={handleFilesUploaded}
          onClose={() => setShowUpload(false)}
        />
      )}
    </div>
  )
}
