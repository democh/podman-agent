import { Download } from 'lucide-react'
import { getFileIcon, getFileType, formatFileSize } from '@/lib/fileUtils'

interface FileCardProps {
  filename: string
  path: string
  size: number
  description?: string
}

export function FileCard({ filename, path, size, description }: FileCardProps) {
  const ft = getFileType(filename)
  const sizeStr = formatFileSize(size)
  const downloadUrl = `http://${window.location.hostname}:8000/api/download?path=${encodeURIComponent(path)}`

  return (
    <div className="file-card">
      <div className="file-card-icon">
        {getFileIcon(filename, 36)}
      </div>
      <div className="file-card-info">
        <div className="file-card-name">
          {filename}
          <span className="file-card-badge" style={{ background: ft.color }}>{ft.label}</span>
        </div>
        <div className="file-card-meta">
          {sizeStr}
          {description ? (sizeStr ? ' · ' : '') + description : ''}
        </div>
      </div>
      <a
        className="file-card-download"
        href={downloadUrl}
        download={filename}
      >
        <Download size={14} />
        下载
      </a>
    </div>
  )
}
