import * as IconPark from '@icon-park/svg'
import { BaseContextMenu } from './baseContextMenu'

/**
 * 计划任务右键菜单管理器
 */
export class CronContextMenu extends BaseContextMenu {
  protected idPrefix = 'cron'
  protected menuId = 'cron-context-menu'
  protected modalId = 'cron-detail-modal'
  protected accountSelectId = 'cron-account-select'
  protected aiExpertRole = 'Linux系统管理和cron专家，擅长分析计划任务、cron表达式、命令安全性等'
  protected aiInfoType = '以下计划任务信息'

  private currentCron: {
    user: string
    schedule: string
    command: string
    source: string
  } | null = null

  constructor() {
    super()
    this.createContextMenu()
    this.createModal()
    this.setupEventListeners()
    this.loadAccountList()
  }

  /**
   * 创建右键菜单
   */
  protected createContextMenu() {
    const menu = document.createElement('div')
    menu.id = 'cron-context-menu'
    menu.style.cssText = `
      position: fixed;
      display: none;
      background: var(--bg-secondary);
      border: 1px solid var(--border-color);
      border-radius: var(--border-radius);
      box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
      z-index: 10000;
      min-width: 200px;
      padding: var(--spacing-xs) 0;
    `

    menu.innerHTML = `
      <div class="menu-account-selector" style="
        padding: 8px 12px;
        border-bottom: 1px solid var(--border-color);
        background: var(--bg-tertiary);
      ">
        <label style="
          display: block;
          font-size: 11px;
          color: var(--text-secondary);
          margin-bottom: 4px;
        ">执行账号:</label>
        <select id="cron-account-select" style="
          width: 100%;
          padding: 4px 8px;
          background: var(--bg-secondary);
          border: 1px solid var(--border-color);
          border-radius: 4px;
          color: var(--text-primary);
          font-size: 12px;
          outline: none;
          cursor: pointer;
        ">
          <option value="">默认账号</option>
        </select>
      </div>

      <div class="menu-item menu-parent">
        <span class="menu-label">
          ${IconPark.FileCode({ theme: 'outline', size: '16', fill: 'currentColor' })}
          <span>源文件操作</span>
        </span>
        <span class="arrow">▶</span>
        <div class="submenu">
          <div class="menu-item" data-action="view-source">
            <span class="menu-label">
              ${IconPark.Find({ theme: 'outline', size: '14', fill: 'currentColor' })}
              <span>查看源文件内容</span>
            </span>
          </div>
          <div class="menu-item" data-action="delete-task-file">
            <span class="menu-label">
              ${IconPark.Delete({ theme: 'outline', size: '14', fill: 'currentColor' })}
              <span>删除任务及文件</span>
            </span>
          </div>
        </div>
      </div>

      <div class="menu-item menu-parent">
        <span class="menu-label">
          ${IconPark.Info({ theme: 'outline', size: '16', fill: 'currentColor' })}
          <span>基本信息</span>
        </span>
        <span class="arrow">▶</span>
        <div class="submenu">
          <div class="menu-item" data-action="details">
            <span class="menu-label">
              ${IconPark.FileText({ theme: 'outline', size: '14', fill: 'currentColor' })}
              <span>查看任务详情</span>
            </span>
          </div>
          <div class="menu-item" data-action="schedule">
            <span class="menu-label">
              ${IconPark.Schedule({ theme: 'outline', size: '14', fill: 'currentColor' })}
              <span>查看执行时间表</span>
            </span>
          </div>
          <div class="menu-item" data-action="command">
            <span class="menu-label">
              ${IconPark.Terminal({ theme: 'outline', size: '14', fill: 'currentColor' })}
              <span>查看执行命令</span>
            </span>
          </div>
          <div class="menu-item" data-action="copy-command">
            <span class="menu-label">
              ${IconPark.Copy({ theme: 'outline', size: '14', fill: 'currentColor' })}
              <span>复制命令</span>
            </span>
          </div>
        </div>
      </div>

      <div class="menu-item menu-parent">
        <span class="menu-label">
          ${IconPark.SettingConfig({ theme: 'outline', size: '16', fill: 'currentColor' })}
          <span>任务管理</span>
        </span>
        <span class="arrow">▶</span>
        <div class="submenu">
          <div class="menu-item" data-action="run-now">
            <span class="menu-label">
              ${IconPark.Play({ theme: 'outline', size: '14', fill: 'currentColor' })}
              <span>立即执行</span>
            </span>
          </div>
          <div class="menu-item" data-action="test-command">
            <span class="menu-label">
              ${IconPark.Experiment({ theme: 'outline', size: '14', fill: 'currentColor' })}
              <span>测试命令</span>
            </span>
          </div>
          <div class="menu-item" data-action="view-crontab">
            <span class="menu-label">
              ${IconPark.FileSearch({ theme: 'outline', size: '14', fill: 'currentColor' })}
              <span>查看完整crontab</span>
            </span>
          </div>
        </div>
      </div>

      <div class="menu-item menu-parent">
        <span class="menu-label">
          ${IconPark.Log({ theme: 'outline', size: '16', fill: 'currentColor' })}
          <span>执行历史</span>
        </span>
        <span class="arrow">▶</span>
        <div class="submenu">
          <div class="menu-item" data-action="execution-logs">
            <span class="menu-label">
              ${IconPark.FileText({ theme: 'outline', size: '14', fill: 'currentColor' })}
              <span>查看执行日志</span>
            </span>
          </div>
          <div class="menu-item" data-action="recent-runs">
            <span class="menu-label">
              ${IconPark.History({ theme: 'outline', size: '14', fill: 'currentColor' })}
              <span>最近执行记录</span>
            </span>
          </div>
          <div class="menu-item" data-action="error-logs">
            <span class="menu-label">
              ${IconPark.Caution({ theme: 'outline', size: '14', fill: 'currentColor' })}
              <span>查看错误日志</span>
            </span>
          </div>
        </div>
      </div>

      <div class="menu-item menu-parent">
        <span class="menu-label">
          ${IconPark.Time({ theme: 'outline', size: '16', fill: 'currentColor' })}
          <span>时间分析</span>
        </span>
        <span class="arrow">▶</span>
        <div class="submenu">
          <div class="menu-item" data-action="parse-cron">
            <span class="menu-label">
              ${IconPark.Analysis({ theme: 'outline', size: '14', fill: 'currentColor' })}
              <span>解析cron表达式</span>
            </span>
          </div>
          <div class="menu-item" data-action="next-run">
            <span class="menu-label">
              ${IconPark.Timer({ theme: 'outline', size: '14', fill: 'currentColor' })}
              <span>下次执行时间</span>
            </span>
          </div>
          <div class="menu-item" data-action="frequency">
            <span class="menu-label">
              ${IconPark.ChartLine({ theme: 'outline', size: '14', fill: 'currentColor' })}
              <span>执行频率分析</span>
            </span>
          </div>
        </div>
      </div>

      <div class="menu-item menu-parent">
        <span class="menu-label">
          ${IconPark.Protection({ theme: 'outline', size: '16', fill: 'currentColor' })}
          <span>安全检查</span>
        </span>
        <span class="arrow">▶</span>
        <div class="submenu">
          <div class="menu-item" data-action="security-check">
            <span class="menu-label">
              ${IconPark.Shield({ theme: 'outline', size: '14', fill: 'currentColor' })}
              <span>命令安全性检查</span>
            </span>
          </div>
          <div class="menu-item" data-action="check-path">
            <span class="menu-label">
              ${IconPark.FolderOpen({ theme: 'outline', size: '14', fill: 'currentColor' })}
              <span>检查命令路径</span>
            </span>
          </div>
          <div class="menu-item" data-action="suspicious-check">
            <span class="menu-label">
              ${IconPark.Attention({ theme: 'outline', size: '14', fill: 'currentColor' })}
              <span>可疑命令检测</span>
            </span>
          </div>
        </div>
      </div>

      <div class="menu-item menu-parent">
        <span class="menu-label">
          ${IconPark.SettingTwo({ theme: 'outline', size: '16', fill: 'currentColor' })}
          <span>高级操作</span>
        </span>
        <span class="arrow">▶</span>
        <div class="submenu">
          <div class="menu-item" data-action="backup">
            <span class="menu-label">
              ${IconPark.Save({ theme: 'outline', size: '14', fill: 'currentColor' })}
              <span>备份crontab</span>
            </span>
          </div>
          <div class="menu-item" data-action="export">
            <span class="menu-label">
              ${IconPark.Export({ theme: 'outline', size: '14', fill: 'currentColor' })}
              <span>导出任务配置</span>
            </span>
          </div>
        </div>
      </div>
    `

    const style = document.createElement('style')
    style.textContent = `
      #cron-context-menu .menu-item {
        padding: 8px 12px;
        cursor: pointer;
        font-size: 13px;
        color: var(--text-primary);
        transition: background-color 0.2s ease;
        position: relative;
        display: flex;
        justify-content: space-between;
        align-items: center;
      }
      #cron-context-menu .menu-item:hover {
        background: var(--bg-tertiary);
      }
      #cron-context-menu .menu-label {
        display: flex;
        align-items: center;
        gap: 8px;
      }
      #cron-context-menu .menu-label svg {
        flex-shrink: 0;
      }
      #cron-context-menu .menu-parent {
        position: relative;
      }
      #cron-context-menu .menu-parent .arrow {
        font-size: 10px;
        color: var(--text-secondary);
        margin-left: 8px;
      }
      #cron-context-menu .submenu {
        display: none;
        position: absolute;
        left: 100%;
        top: 0;
        background: var(--bg-secondary);
        border: 1px solid var(--border-color);
        border-radius: var(--border-radius);
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
        min-width: 200px;
        z-index: 10001;
      }
      #cron-context-menu .menu-parent:hover > .submenu {
        display: block;
      }
      #cron-context-menu .submenu .menu-item {
        padding: 8px 16px;
      }
    `
    document.head.appendChild(style)

    document.body.appendChild(menu)
    this.contextMenu = menu
  }

  /**
   * 显示右键菜单
   */
  async showContextMenu(x: number, y: number, cron: {
    user: string
    schedule: string
    command: string
    source: string
  }) {
    if (!this.contextMenu) return

    this.currentCron = cron

    await this.loadAccountList()

    const menuWidth = 200
    const menuHeight = 600
    const adjustedX = Math.min(x, window.innerWidth - menuWidth)
    const adjustedY = Math.min(y, window.innerHeight - menuHeight)

    this.contextMenu.style.left = `${adjustedX}px`
    this.contextMenu.style.top = `${adjustedY}px`
    this.contextMenu.style.display = 'block'
  }

  /**
   * 执行操作
   */
  protected async executeAction(action: string) {
    if (!this.currentCron) return

    const { user, schedule, command, source } = this.currentCron
    let cmd = ''
    let title = ''
    let actionName = ''

    switch (action) {
      case 'view-source':
        if (source && source.startsWith('/')) {
            cmd = `echo "=== 源文件: ${source} ==="; echo ""; cat "${source}" 2>&1 || echo "无法读取文件"`
            title = `源文件 - ${source}`
        } else if (source && source.startsWith('crontab:')) {
             const u = source.split(':')[1];
             cmd = `echo "=== 用户Crontab: ${u} ==="; echo ""; crontab -u ${u} -l`
             title = `用户Crontab - ${u}`
        } else {
             this.showModal('提示', '无法确定源文件位置');
             return;
        }
        actionName = '查看源文件'
        break

      case 'delete-task-file':
         if (source && source.startsWith('/')) {
             if (source === '/etc/crontab') {
                 this.showModal('错误', '不能删除系统主crontab文件 (/etc/crontab)');
                 return;
             }
             cmd = `echo "正在删除文件: ${source}"; rm -f "${source}" && echo "✓ 删除成功" || echo "✗ 删除失败"`
             title = `删除任务文件 - ${source}`
             actionName = '删除任务文件'
         } else {
             this.showModal('提示', '此任务不是通过独立文件配置的，无法通过删除文件来删除任务。\n\n如果是用户任务，请使用"crontab -e"编辑。');
             return;
         }
         break

      case 'copy-command':
        navigator.clipboard.writeText(command)
        this.showModal('复制成功', `已复制命令: ${command}`)
        return

      case 'details':
        cmd = `echo "=== 计划任务详情 ==="; echo ""; echo "用户: ${user}"; echo "时间表: ${schedule}"; echo "命令: ${command}"; echo ""; echo "=== 任务状态 ==="; crontab -u ${user} -l 2>/dev/null | grep -F "${command}" || echo "任务可能已被删除或修改"`
        title = `计划任务详情 - ${user}`
        actionName = '查看任务详情'
        break

      case 'schedule':
        cmd = `echo "=== 执行时间表分析 ==="; echo ""; echo "Cron表达式: ${schedule}"; echo ""; echo "字段说明:"; echo "分钟(0-59) 小时(0-23) 日(1-31) 月(1-12) 星期(0-7)"; echo ""; echo "当前表达式解析:"; echo "${schedule}" | awk '{print "分钟: "$1; print "小时: "$2; print "日期: "$3; print "月份: "$4; print "星期: "$5}'`
        title = `执行时间表 - ${schedule}`
        actionName = '查看执行时间表'
        break

      case 'command':
        cmd = `echo "=== 执行命令 ==="; echo ""; echo "${command}"; echo ""; echo "=== 命令分析 ==="; which ${command.split(' ')[0]} 2>/dev/null || echo "命令路径: 未找到或不在PATH中"`
        title = `执行命令 - ${command.substring(0, 50)}...`
        actionName = '查看执行命令'
        break

      case 'run-now':
        cmd = `echo "立即执行计划任务"; echo ""; echo "用户: ${user}"; echo "命令: ${command}"; echo ""; echo "执行中..."; echo ""; ${command}`
        title = `立即执行 - ${command.substring(0, 50)}...`
        actionName = '立即执行任务'
        break

      case 'test-command':
        cmd = `echo "=== 测试命令 ==="; echo ""; echo "命令: ${command}"; echo ""; echo "检查命令语法..."; bash -n -c "${command}" 2>&1 && echo "✓ 语法检查通过" || echo "✗ 语法错误"; echo ""; echo "⚠️ 提示：这只是语法检查，实际执行可能需要其他条件"`
        title = `测试命令 - ${command.substring(0, 50)}...`
        actionName = '测试命令'
        break

      case 'view-crontab':
        cmd = `crontab -u ${user} -l 2>/dev/null || echo "用户 ${user} 没有crontab"`
        title = `完整crontab - ${user}`
        actionName = '查看完整crontab'
        break

      case 'execution-logs':
        cmd = `echo "=== 计划任务执行日志 ==="; echo ""; echo "搜索关键词: ${command.split(' ')[0]}"; echo ""; grep CRON /var/log/syslog 2>/dev/null | grep "${user}" | grep "${command.split(' ')[0]}" | tail -50 || journalctl -u cron 2>/dev/null | grep "${user}" | grep "${command.split(' ')[0]}" | tail -50 || echo "无执行日志或日志文件不可访问"`
        title = `执行日志 - ${command.substring(0, 50)}...`
        actionName = '查看执行日志'
        break

      case 'recent-runs':
        cmd = `echo "=== 最近执行记录 ==="; echo ""; grep CRON /var/log/syslog 2>/dev/null | grep "(${user})" | tail -20 || journalctl -u cron 2>/dev/null | grep "${user}" | tail -20 || echo "无执行记录"`
        title = `最近执行记录 - ${user}`
        actionName = '查看最近执行记录'
        break

      case 'error-logs':
        cmd = `echo "=== 错误日志 ==="; echo ""; grep -i "error\\|fail\\|cron" /var/log/syslog 2>/dev/null | grep "${user}" | tail -30 || journalctl -p err 2>/dev/null | grep cron | grep "${user}" | tail -30 || echo "无错误日志"`
        title = `错误日志 - ${user}`
        actionName = '查看错误日志'
        break

      case 'parse-cron':
        cmd = `echo "=== Cron表达式解析 ==="; echo ""; echo "表达式: ${schedule}"; echo ""; if [[ "${schedule}" == "@hourly" ]]; then echo "含义: 每小时执行一次 (0 * * * *)"; elif [[ "${schedule}" == "@daily" ]] || [[ "${schedule}" == "@midnight" ]]; then echo "含义: 每天午夜执行 (0 0 * * *)"; elif [[ "${schedule}" == "@weekly" ]]; then echo "含义: 每周日午夜执行 (0 0 * * 0)"; elif [[ "${schedule}" == "@monthly" ]]; then echo "含义: 每月1号午夜执行 (0 0 1 * *)"; elif [[ "${schedule}" == "@yearly" ]] || [[ "${schedule}" == "@annually" ]]; then echo "含义: 每年1月1日午夜执行 (0 0 1 1 *)"; elif [[ "${schedule}" == "@reboot" ]]; then echo "含义: 系统启动时执行"; else echo "标准cron表达式"; echo "${schedule}" | awk '{print "分钟: "$1" (0-59)"; print "小时: "$2" (0-23)"; print "日期: "$3" (1-31)"; print "月份: "$4" (1-12)"; print "星期: "$5" (0-7, 0和7都表示周日)"}'; fi`
        title = `Cron表达式解析 - ${schedule}`
        actionName = '解析cron表达式'
        break

      case 'next-run':
        cmd = `echo "=== 下次执行时间 ==="; echo ""; echo "当前时间: $(date '+%Y-%m-%d %H:%M:%S')"; echo "时间表: ${schedule}"; echo ""; echo "⚠️ 注意：精确计算需要安装croniter等工具"; echo ""; if [[ "${schedule}" == "@hourly" ]]; then echo "下次执行: 下一个整点"; elif [[ "${schedule}" == "@daily" ]]; then echo "下次执行: 明天 00:00"; elif [[ "${schedule}" == "@weekly" ]]; then echo "下次执行: 下周日 00:00"; elif [[ "${schedule}" == "@monthly" ]]; then echo "下次执行: 下月1日 00:00"; else echo "标准cron表达式，请使用cron计算工具"; fi`
        title = `下次执行时间 - ${schedule}`
        actionName = '查看下次执行时间'
        break

      case 'frequency':
        cmd = `echo "=== 执行频率分析 ==="; echo ""; echo "时间表: ${schedule}"; echo ""; if [[ "${schedule}" == "@hourly" ]]; then echo "频率: 每小时1次"; echo "每天: 24次"; echo "每月: ~720次"; elif [[ "${schedule}" == "@daily" ]]; then echo "频率: 每天1次"; echo "每月: ~30次"; echo "每年: 365次"; elif [[ "${schedule}" == "@weekly" ]]; then echo "频率: 每周1次"; echo "每月: ~4次"; echo "每年: 52次"; elif [[ "${schedule}" == "@monthly" ]]; then echo "频率: 每月1次"; echo "每年: 12次"; elif [[ "${schedule}" =~ ^\\*.*\\*.*\\*.*\\*.*\\*$ ]]; then echo "频率: 每分钟1次"; echo "每小时: 60次"; echo "每天: 1440次"; else echo "自定义频率"; echo "请根据cron表达式计算"; fi`
        title = `执行频率 - ${schedule}`
        actionName = '执行频率分析'
        break

      case 'security-check':
        cmd = `echo "=== 命令安全性检查 ==="; echo ""; echo "命令: ${command}"; echo ""; echo "1. 检查危险命令:"; if echo "${command}" | grep -qE "rm -rf|dd if=|mkfs|fdisk|>/dev/"; then echo "⚠️ 包含危险命令"; else echo "✓ 未发现明显危险命令"; fi; echo ""; echo "2. 检查网络操作:"; if echo "${command}" | grep -qE "wget|curl|nc|telnet|ssh"; then echo "⚠️ 包含网络操作命令"; else echo "✓ 未检测到网络操作"; fi; echo ""; echo "3. 检查权限提升:"; if echo "${command}" | grep -qE "sudo|su -"; then echo "⚠️ 包含权限提升命令"; else echo "✓ 未检测到权限提升"; fi`
        title = `安全检查 - ${command.substring(0, 50)}...`
        actionName = '命令安全性检查'
        break

      case 'check-path':
        cmd = `echo "=== 命令路径检查 ==="; echo ""; cmd_name="${command.split(' ')[0]}"; echo "命令: $cmd_name"; echo ""; which "$cmd_name" 2>/dev/null && echo "" && ls -la $(which "$cmd_name") 2>/dev/null || echo "⚠️ 命令不在PATH中或不存在"`
        title = `路径检查 - ${command.split(' ')[0]}`
        actionName = '检查命令路径'
        break

      case 'suspicious-check':
        cmd = `echo "=== 可疑命令检测 ==="; echo ""; echo "命令: ${command}"; echo ""; echo "检测项:"; echo ""; echo "1. 编码/混淆:"; if echo "${command}" | grep -qE "base64|eval|exec"; then echo "⚠️ 可能包含编码或混淆"; else echo "✓ 未发现编码"; fi; echo ""; echo "2. 反弹shell:"; if echo "${command}" | grep -qE "bash -i|/bin/sh|nc.*-e"; then echo "⚠️ 可能是反弹shell"; else echo "✓ 未发现反弹shell特征"; fi; echo ""; echo "3. 下载执行:"; if echo "${command}" | grep -qE "curl.*\\||wget.*\\||chmod\\+x"; then echo "⚠️ 可能下载并执行文件"; else echo "✓ 未发现下载执行"; fi`
        title = `可疑检测 - ${command.substring(0, 50)}...`
        actionName = '可疑命令检测'
        break

      case 'backup':
        cmd = `echo "=== 备份crontab ==="; echo ""; backup_file="/tmp/crontab_${user}_$(date +%Y%m%d_%H%M%S).bak"; crontab -u ${user} -l > "$backup_file" 2>/dev/null && echo "✓ 备份成功" && echo "备份文件: $backup_file" && echo "" && cat "$backup_file" || echo "✗ 备份失败"`
        title = `备份crontab - ${user}`
        actionName = '备份crontab'
        break

      case 'export':
        cmd = `echo "=== 导出任务配置 ==="; echo ""; echo "用户: ${user}"; echo "时间表: ${schedule}"; echo "命令: ${command}"; echo ""; echo "JSON格式:"; echo "{"; echo '  "user": "'${user}'",'; echo '  "schedule": "'${schedule}'",'; echo '  "command": "'${command}'"'; echo "}"`
        title = `导出配置 - ${command.substring(0, 50)}...`
        actionName = '导出任务配置'
        break

      default:
        console.warn(`未知操作: ${action}`)
        this.showModal('错误', `未知操作: ${action}`)
        return
    }

    await this.executeCommand(cmd, title, actionName)
  }
}
