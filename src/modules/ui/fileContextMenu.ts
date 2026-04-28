/**
 * 文件右键菜单和安全分析
 */

import { invoke } from '../../shims/@tauri-apps/api/core'
import { marked } from 'marked'
import { aiService } from '../ai/aiService'

// 命令历史记录接口
interface CommandHistory {
  timestamp: string
  action: string
  actionName: string
  filePath: string
  fileName: string
  command: string
  result: string
}

export class FileContextMenu {
  private commandHistory: CommandHistory[] = []
  private currentFilePath: string = ''
  private currentAnalysisType: string = ''
  private currentAnalysisResult: string = ''

  constructor() {
    this.setupEventListeners()
    console.log('📁 FileContextMenu 已加载（复用 processContextMenu 模态框，提供复制/AI 解释功能）')
  }

  /**
   * 设置事件监听器
   */
  private setupEventListeners() {
    // AI 解释按钮
    document.addEventListener('click', (e) => {
      const target = e.target as HTMLElement
      if (target.id === 'ai-analyze-btn' || target.closest('#ai-analyze-btn')) {
        // 检查当前是否是文件分析模态框
        const modal = document.getElementById('process-detail-modal')
        if (modal && modal.style.display === 'flex' && this.currentFilePath) {
          this.analyzeWithAI()
        }
      }
    })
  }

  /**
   * 显示模态框（复用 processContextMenu 的模态框）
   */
  private showModal(title: string, content: string) {
    const modal = document.getElementById('process-detail-modal')
    const titleEl = document.getElementById('modal-title')
    const contentEl = document.getElementById('modal-content')
    const explanationEl = document.getElementById('ai-explanation')

    if (!modal || !titleEl || !contentEl) {
      console.error('❌ [FileContextMenu] 找不到 processContextMenu 的模态框元素')
      return
    }

    // 设置标题和内容
    titleEl.textContent = title
    contentEl.textContent = content

    // 隐藏AI分析区域（每次显示新内容时重置）
    if (explanationEl) {
      explanationEl.style.display = 'none'
      const explanationContentEl = document.getElementById('ai-explanation-content')
      if (explanationContentEl) {
        explanationContentEl.textContent = ''
      }
    }

    // 显示模态框
    modal.style.display = 'flex'
  }

  /**
   * 关闭模态框
   */
  public hideModal() {
    const modal = document.getElementById('process-detail-modal')
    if (modal) {
      modal.style.display = 'none'
    }
  }

  /**
   * 执行文件分析命令（使用独立 session）
   */
  private async executeAnalysis(action: string, filePath: string) {
    try {
      const result = await invoke('sftp_file_analysis_independent', {
        action,
        path: filePath
      }) as any

      // 添加到历史记录
      this.addToHistory(result)

      return result.result as string
    } catch (error) {
      throw new Error(`分析失败: ${error}`)
    }
  }

  /**
   * 添加到历史记录
   */
  private addToHistory(data: any) {
    const actionName = this.getActionName(data.action)
    const fileName = data.file_path.split('/').pop() || data.file_path

    // 保存到历史记录数组
    const historyItem: CommandHistory = {
      timestamp: data.timestamp,
      action: data.action,
      actionName: actionName,
      filePath: data.file_path,
      fileName: fileName,
      command: this.getCommandForAction(data.action, data.file_path),
      result: data.result
    }

    // 插入到数组开头
    this.commandHistory.unshift(historyItem)

    // 限制历史记录数量（最多保留 50 条）
    if (this.commandHistory.length > 50) {
      this.commandHistory.pop()
    }
  }

  /**
   * 获取动作对应的命令
   */
  private getCommandForAction(action: string, filePath: string): string {
    const commands: Record<string, string> = {
      'hash': `md5sum "${filePath}" && sha1sum "${filePath}" && sha256sum "${filePath}"`,
      'signature': `file -b "${filePath}"`,
      'permissions': `ls -lh "${filePath}" && stat -c '%A %a %U:%G' "${filePath}"`,
      'timestamps': `stat "${filePath}"`,
      'inode': `stat -c 'Inode: %i\\nLinks: %h\\nDevice: %d\\nSize: %s bytes' "${filePath}"`,
      'mime-type': `file -b --mime-type "${filePath}"`,
      'file-size': `du -h "${filePath}" && ls -lh "${filePath}"`,
      'strings': `strings -n 8 "${filePath}" | head -100`,
      'hex-dump': `xxd "${filePath}" | head -50`,
      'line-count': `wc -l "${filePath}"`,
      'archive-list': `tar -tzf "${filePath}" 2>/dev/null || unzip -l "${filePath}" 2>/dev/null`,
      'elf-header': `readelf -h "${filePath}"`,
      'processes': `lsof "${filePath}" 2>/dev/null || fuser -v "${filePath}" 2>/dev/null`,
      'package-owner': `dpkg -S "${filePath}" 2>/dev/null || rpm -qf "${filePath}" 2>/dev/null`,
      'hard-links': `find / -samefile "${filePath}" 2>/dev/null`,
      'process-maps': `grep "${filePath}" /proc/*/maps 2>/dev/null`,
      'xattr': `getfattr -d "${filePath}" 2>/dev/null || xattr -l "${filePath}" 2>/dev/null`,
      'capabilities': `getcap "${filePath}"`,
      'selinux-context': `ls -Z "${filePath}"`,
      'dynamic-deps': `ldd "${filePath}" 2>/dev/null`,
      'config-references': `grep -r "${filePath}" /etc/ 2>/dev/null | head -20`,
      'symlink-analysis': `ls -l "${filePath}" && readlink -f "${filePath}"`,
      'suspicious-path': `echo "${filePath}" | grep -E '(/tmp/|/dev/shm/|/var/tmp/|\\.\\.)'`,
      'hidden-file': `basename "${filePath}" | grep '^\\.'`,
      'suid-sgid': `find "${filePath}" -perm /6000 -ls`,
      'webshell': `grep -E '(eval|base64_decode|system|exec|shell_exec|passthru)' "${filePath}"`,
      'backdoor': `grep -E '(nc -e|/bin/bash|/bin/sh.*-i)' "${filePath}"`,
      'crypto-mining': `grep -E '(xmrig|stratum|cryptonight|monero)' "${filePath}"`,
      'reverse-shell': `grep -E '(bash -i|sh -i|nc.*-e|/dev/tcp/)' "${filePath}"`
    }
    return commands[action] || `未知命令: ${action}`
  }

  /**
   * 显示历史记录模态框
   */
  public showHistoryModal() {
    const modal = document.getElementById('process-detail-modal')
    const titleEl = document.getElementById('modal-title')
    const contentEl = document.getElementById('modal-content')
    const explanationEl = document.getElementById('ai-explanation')

    if (!modal || !titleEl || !contentEl || !explanationEl) {
      console.error('模态框元素不存在')
      return
    }

    // 设置标题
    titleEl.textContent = '📋 命令执行历史'

    // 隐藏 AI 解释区域
    explanationEl.style.display = 'none'

    // 生成历史记录 HTML
    let historyHTML = ''

    if (this.commandHistory.length === 0) {
      historyHTML = '<div style="text-align: center; padding: 40px; color: var(--text-tertiary);">暂无历史记录</div>'
    } else {
      historyHTML = '<div style="max-height: 600px; overflow-y: auto;">'
      historyHTML += '<div style="margin-bottom: 20px;">'
      historyHTML += `<button id="clear-history-btn" style="
        background: linear-gradient(135deg, #ef4444 0%, #dc2626 100%);
        color: white;
        border: none;
        padding: 8px 16px;
        border-radius: 6px;
        cursor: pointer;
        font-size: 13px;
        transition: all 0.3s;
      " onmouseover="this.style.transform='scale(1.05)'" onmouseout="this.style.transform='scale(1)'">
        🗑️ 清空历史
      </button>`
      historyHTML += '</div>'

      this.commandHistory.forEach((item) => {
        const time = new Date(item.timestamp).toLocaleString('zh-CN')
        historyHTML += `<div style="
          background: var(--panel-bg);
          border: 1px solid var(--border-color);
          border-radius: 12px;
          padding: 16px;
          margin-bottom: 12px;
        ">
          <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
            <div style="display: flex; align-items: center; gap: 8px;">
              <span style="font-size: 18px;">📁</span>
              <span style="font-weight: 600; color: var(--text-primary);">${this.escapeHtml(item.fileName)}</span>
            </div>
            <span style="font-size: 12px; color: var(--text-tertiary);">${time}</span>
          </div>
          <div style="font-size: 13px; color: var(--text-secondary); margin-bottom: 6px;">
            🔍 命令: <span style="color: var(--text-primary);">${item.actionName}</span>
          </div>
          <div style="font-size: 12px; color: var(--text-tertiary); margin-bottom: 8px;">
            📂 ${this.escapeHtml(item.filePath)}
          </div>
          <div style="font-size: 12px; color: var(--text-tertiary); background: var(--bg-color); padding: 8px; border-radius: 6px; font-family: monospace; max-height: 100px; overflow-y: auto; white-space: pre-wrap;">
            📊 结果: ${this.escapeHtml(item.result.substring(0, 300))}${item.result.length > 300 ? '...' : ''}
          </div>
        </div>`
      })
      historyHTML += '</div>'
    }

    // 显示模态框
    this.showModal('📋 命令执行历史', historyHTML)

    // 绑定清空按钮事件
    const clearBtn = document.getElementById('clear-history-btn')
    if (clearBtn) {
      clearBtn.addEventListener('click', () => {
        if (confirm('确定要清空所有历史记录吗？')) {
          this.commandHistory = []
          this.showHistoryModal()
        }
      })
    }
  }

  /**
   * HTML 转义
   */
  private escapeHtml(text: string): string {
    const div = document.createElement('div')
    div.textContent = text
    return div.innerHTML
  }

  /**
   * 获取动作的中文名称
   */
  private getActionName(action: string): string {
    const names: Record<string, string> = {
      'hash': '哈希值',
      'signature': '文件类型',
      'permissions': '权限',
      'timestamps': '时间戳',
      'inode': 'Inode',
      'mime-type': 'MIME 类型',
      'file-size': '大小',
      'strings': '字符串',
      'hex-dump': 'HEX 转储',
      'line-count': '行数',
      'archive-list': '压缩列表',
      'elf-header': 'ELF头',
      'processes': '进程',
      'package-owner': '所属包',
      'hard-links': '硬链接',
      'process-maps': '内存映射',
      'xattr': '扩展属性',
      'capabilities': '能力',
      'selinux-context': 'SELinux',
      'dynamic-deps': '动态依赖',
      'config-references': '配置引用',
      'symlink-analysis': '符号链接',
      'suspicious-path': '可疑路径',
      'hidden-file': '隐藏文件',
      'suid-sgid': 'SUID/SGID',
      'webshell': 'Webshell',
      'backdoor': '后门',
      'crypto-mining': '挖矿',
      'reverse-shell': '反弹Shell'
    }
    return names[action] || action
  }

  /**
   * 处理菜单项点击
   */
  public async handleAction(action: string, filePath: string, menuItem: HTMLElement) {
    try {
      // 禁用菜单项
      menuItem.style.opacity = '0.5'
      menuItem.style.pointerEvents = 'none'
      menuItem.textContent = '⏳ 执行中...'

      // 获取动作名称
      const actionName = this.getActionName(action)

      // 执行分析命令（使用独立 session）
      const result = await this.executeAnalysis(action, filePath)

      // 保存当前分析信息，供 AI 解释使用
      this.currentFilePath = filePath
      this.currentAnalysisType = actionName
      this.currentAnalysisResult = result

      // 显示结果（复用 processContextMenu 的模态框）
      const displayTitle = `${actionName} - ${filePath.split('/').pop()}`
      const displayContent = result

      // 更新模态框内容（showModal 会自动隐藏 AI 解释区域）
      this.showModal(displayTitle, displayContent)

      // 重新启用菜单项
      menuItem.style.opacity = '1'
      menuItem.style.pointerEvents = 'auto'
      menuItem.textContent = menuItem.getAttribute('data-original-text') || actionName

    } catch (error) {
      console.error(`文件分析失败:`, error)
      this.showModal('错误', `文件分析失败: ${error}`)

      // 重新启用菜单项
      menuItem.style.opacity = '1'
      menuItem.style.pointerEvents = 'auto'
      menuItem.textContent = menuItem.getAttribute('data-original-text') || '重试'
    }
  }

  /**
   * 使用 AI 解释分析结果（复用 processContextMenu 的 AI 解释区域）
   */
  private async analyzeWithAI() {
    if (!this.currentFilePath || !this.currentAnalysisResult) {
      console.warn('没有可分析的内容')
      return
    }

    // 显示 AI 解释区域
    const explanationEl = document.getElementById('ai-explanation')
    const explanationContentEl = document.getElementById('ai-explanation-content')

    if (!explanationEl || !explanationContentEl) {
      console.error('找不到 AI 解释区域')
      return
    }

    // 显示加载状态
    explanationEl.style.display = 'block'
    explanationContentEl.innerHTML = '<div style="text-align: center; padding: 20px;"><span style="display: inline-block; animation: spin 1s linear infinite;">⏳</span> 正在分析...</div>'

    if (!aiService.isConfigured()) {
      explanationContentEl.innerHTML = '<div style="text-align: center; padding: 20px; color: #ef4444;">⚠️ 请先在设置中配置 AI 模型</div>'
      return
    }

    // 构建提示词
    const prompt = `你是一个 Linux 安全专家和应急响应专家。

## 任务
分析以下文件安全分析结果，并提供专业的解释和建议。

## 文件信息
- 文件路径：${this.currentFilePath}
- 分析类型：${this.currentAnalysisType}

## 分析结果
\`\`\`
${this.currentAnalysisResult}
\`\`\`

## 输出要求
请按照以下顺序提供分析：
1. **结果概要**：简要总结分析结果
2. **关键发现**：列出重要的发现和特征
3. **安全评估**：评估潜在的安全风险（如果适用）
4. **建议操作**：提供具体的操作建议（如果适用）

请使用清晰的 Markdown 格式，确保内容结构化、易读。`

    try {
      // 清空"正在分析"提示
      explanationContentEl.innerHTML = ''

      // 累积内容
      let accumulatedContent = ''

      // 使用节流更新，避免闪烁（每 100ms 更新一次）
      let lastUpdateTime = 0
      const updateUI = (content: string) => {
        const now = Date.now()
        if (now - lastUpdateTime >= 100) {
          explanationContentEl.innerHTML = this.renderMarkdown(content)
          lastUpdateTime = now
        }
      }

      await aiService.chatStream(
        [
          { role: 'system', content: '你是一个专业的 Linux 安全分析专家，擅长分析系统文件和提供安全建议。请使用中文回答。' },
          { role: 'user', content: prompt }
        ],
        (chunk) => {
          accumulatedContent += chunk
          updateUI(accumulatedContent)
        }
      )

      // 确保最后一次更新
      explanationContentEl.innerHTML = this.renderMarkdown(accumulatedContent)

    } catch (error) {
      console.error('AI 分析失败:', error)
      explanationContentEl.innerHTML = `<div style="text-align: center; padding: 20px; color: #ef4444;">
        ❌ AI分析失败: ${error}<br><br>
        提示：请在设置中配置AI，或者检查AI服务是否可用。
      </div>`
    }
  }

  /**
   * Markdown 渲染器（使用 marked.js）
   */
  private renderMarkdown(text: string): string {
    try {
      // 检查 marked.js 是否已加载
      if (typeof marked === 'undefined') {
        console.warn('marked.js 未加载，使用简单渲染')
        return this.simpleMarkdownRender(text)
      }

      // 配置 marked
      marked.setOptions({
        gfm: true,  // 支持 GFM 换行
        breaks: true,  // 启用 GitHub Flavored Markdown
      })

      // 渲染 Markdown
      const html = marked.parse(text)

      // 添加自定义样式
      return `<style>
        .ai-content h1, .ai-content h2, .ai-content h3 { color: var(--text-primary); margin: 12px 0 8px 0; }
        .ai-content h1 { font-size: 1.4em; }
        .ai-content h2 { font-size: 1.2em; }
        .ai-content h3 { font-size: 1.1em; }
        .ai-content p { margin: 8px 0; line-height: 1.6; }
        .ai-content ul, .ai-content ol { margin: 8px 0 8px 20px; }
        .ai-content li { margin: 4px 0; }
        .ai-content code { background: var(--bg-color); padding: 2px 6px; border-radius: 4px; font-family: monospace; font-size: 0.9em; }
        .ai-content pre { background: var(--bg-color); padding: 12px; border-radius: 8px; overflow-x: auto; margin: 12px 0; }
        .ai-content pre code { background: none; padding: 0; }
        .ai-content blockquote { border-left: 3px solid var(--primary-color); padding-left: 12px; margin: 12px 0; color: var(--text-secondary); }
        .ai-content strong { color: var(--text-primary); font-weight: 600; }
        .ai-content a { color: var(--primary-color); text-decoration: underline; }
        .ai-content hr { border: none; border-top: 1px solid var(--border-color); margin: 16px 0; }
        .ai-content table { width: 100%; border-collapse: collapse; margin: 12px 0; }
        .ai-content th, .ai-content td { border: 1px solid var(--border-color); padding: 8px; text-align: left; }
        .ai-content th { background: var(--bg-color); font-weight: 600; }
      </style>
      <div class="ai-content">${html}</div>`
    } catch (e) {
      console.error('Markdown 渲染失败:', e)
      return this.simpleMarkdownRender(text)
    }
  }

  /**
   * 简单 Markdown 渲染（降级方案）
   */
  private simpleMarkdownRender(text: string): string {
    return text
      .replace(/^### (.+)$/gm, '<h3>$1</h3>')
      .replace(/^## (.+)$/gm, '<h2>$1</h2>')
      .replace(/^# (.+)$/gm, '<h1>$1</h1>')
      .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
      .replace(/\*(.+?)\*/g, '<em>$1</em>')
      .replace(/`(.+?)`/g, '<code>$1</code>')
      .replace(/\n/g, '<br>')
  }
}

// 全局实例（用于从其他模块访问）
declare global {
  interface Window {
    fileContextMenu: FileContextMenu
  }
}

export const fileContextMenu = new FileContextMenu()
if (typeof window !== 'undefined') {
  window.fileContextMenu = fileContextMenu
}
