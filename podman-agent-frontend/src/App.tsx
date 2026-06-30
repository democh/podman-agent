import { useState, useCallback, useRef } from 'react'
import { useAgent } from '@/hooks/useAgent'
import { useKeyboard } from '@/hooks/useKeyboard'
import { TopBar } from '@/components/topbar/TopBar'
import { Sidebar } from '@/components/sidebar/Sidebar'
import { ChatArea } from '@/components/chat/ChatArea'
import { InputArea } from '@/components/chat/InputArea'
import { SettingsPanel } from '@/components/settings/SettingsPanel'

function App() {
  const agent = useAgent()
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [settingsOpen, setSettingsOpen] = useState(false)
  const inputRef = useRef<HTMLTextAreaElement>(null)

  const toggleSidebar = useCallback(() => setSidebarOpen((v) => !v), [])

  // 快捷键系统
  useKeyboard({
    onNewChat: agent.reset,
    onStopAgent: agent.stop,
    onFocusInput: () => inputRef.current?.focus(),
  })

  return (
    <div className="app-layout">
      <Sidebar
        open={sidebarOpen}
        onClose={toggleSidebar}
        skills={agent.skills}
        onToggleSkill={agent.toggleSkill}
        memoryResult={agent.memoryResult}
        onRefreshMemory={agent.refreshMemory}
      />
      <div className="main-area">
        <TopBar
          model={agent.model}
          tools={agent.tools}
          skills={agent.skills}
          status={agent.status}
          busy={agent.busy}
          totalTokens={agent.totalTokens}
          tokenWarning={agent.tokenWarning}
          onToggleSidebar={toggleSidebar}
          onReset={agent.reset}
          onCompress={agent.compress}
          onToggleSettings={() => setSettingsOpen((v) => !v)}
        />
        <ChatArea messages={agent.messages} busy={agent.busy} onConfirm={agent.confirm} onRetry={agent.retry} onSend={agent.send} />
        <InputArea busy={agent.busy} connected={agent.status === 'connected'} onSend={agent.send} onStop={agent.stop} />
      </div>
      <SettingsPanel open={settingsOpen} onClose={() => setSettingsOpen(false)} />
      <div className="toast-container" id="toast-container" />
    </div>
  )
}

export default App
