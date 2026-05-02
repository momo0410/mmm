/**
 * 系统信息仪表盘渲染器
 * 负责渲染系统监控信息和统计数据
 */

import type { SystemInfo } from '../ssh/sshManager';
import { sshConnectionManager } from '../remote/sshConnectionManager';
import { SystemDetector } from '../utils/systemDetector';
import {
  LinkOne,
  Dashboard as DashboardIcon,
  Refresh
} from '@icon-park/svg';

export class DashboardRenderer {
  private static readonly HISTORY_MAX = 20;

  private systemMetaCache: {
    os: string;
    kernel: string;
    arch: string;
    virtualization: string;
    timezone: string;
  } | null = null;

  private memoryHistory: number[] = [];
  private diskHistory: number[] = [];

  constructor() {
    (window as any).dashboardRendererInstance = this;
  }

  /**
   * 渲染系统信息仪表盘
   */
  renderDashboard(systemInfo?: SystemInfo, _theme: string = 'dark'): string {
    const isConnected = sshConnectionManager.isConnected();

    if (!isConnected) {
      return this.renderEmptyDashboard();
    }
    if (!systemInfo) {
      return this.renderConnectedButNoData();
    }

    setTimeout(() => {
      this.detectAndShowSystemType();
      this.loadSystemMeta();
    }, 100);

    const cpuUsage = parseFloat(this.getCpuUsage(systemInfo));
    const memUsage = parseFloat(this.getMemoryUsage(systemInfo));
    const diskUsage = parseFloat(this.getDiskUsage(systemInfo));

    this.memoryHistory.push(memUsage);
    this.diskHistory.push(diskUsage);
    while (this.memoryHistory.length > DashboardRenderer.HISTORY_MAX) this.memoryHistory.shift();
    while (this.diskHistory.length > DashboardRenderer.HISTORY_MAX) this.diskHistory.shift();
    const loadAvg = systemInfo.loadAverage || ['0', '0', '0'];
    const load1 = parseFloat(loadAvg[0]) || 0;
    const load5 = parseFloat(loadAvg[1]) || 0;
    const load15 = parseFloat(loadAvg[2]) || 0;
    const cores = systemInfo.cpuInfo.cores || 1;
    const loadPercent = Math.min((load5 / cores) * 100, 100);
    const meta = this.systemMetaCache || { os: '检测中...' };

    return `
      <div class="dashboard-v3">
        <div class="dash-v3-header">
          <div class="dash-v3-header-left">
            <div class="dash-v3-logo">${DashboardIcon({ theme: 'filled', size: '22', fill: 'currentColor' })}</div>
            <div class="dash-v3-title-group">
              <h2 class="dash-v3-title">系统监控仪表盘</h2>
              <span class="dash-v3-subtitle">最后更新: ${this.formatTime(systemInfo.lastUpdate)}</span>
            </div>
            <div class="dash-v3-system-status">
              <span class="dash-v3-status-dot"></span>
              <div class="dash-v3-system-status-copy">
                <span class="dash-v3-system-status-text">已检测到系统:</span>
                <strong id="dashboard-os-value" title="${meta.os}">${meta.os}</strong>
              </div>
            </div>
          </div>
          <div class="dash-v3-header-right">
            <div class="dash-v3-refresh-stack">
              <button class="dash-v3-refresh-btn" onclick="window.loadSystemDetailedInfo(true)">
                ${Refresh({ theme: 'outline', size: '14', fill: 'currentColor' })}
                <span>刷新数据</span>
              </button>
              <div class="dash-v3-auto-refresh">
                <span>自动刷新: <strong>30秒</strong></span>
              </div>
            </div>
          </div>
        </div>

        <div class="dash-v3-info-bar">
          <div class="dash-v3-info-col">
            <div class="dash-v3-info-item">
              <span class="dash-v3-info-label">主机名</span>
              <span class="dash-v3-info-value">${systemInfo.hostname}</span>
            </div>
            <div class="dash-v3-info-item">
              <span class="dash-v3-info-label">总内存</span>
              <span class="dash-v3-info-value">${systemInfo.memoryUsage.total}</span>
            </div>
          </div>
          <div class="dash-v3-info-col">
            <div class="dash-v3-info-item">
              <span class="dash-v3-info-label">处理器</span>
              <span class="dash-v3-info-value" title="${systemInfo.cpuInfo.model}">${systemInfo.cpuInfo.model}</span>
            </div>
            <div class="dash-v3-info-item">
              <span class="dash-v3-info-label">磁盘总量</span>
              <span class="dash-v3-info-value">${systemInfo.diskUsage.total}</span>
            </div>
          </div>
          <div class="dash-v3-info-col">
            <div class="dash-v3-info-item">
              <span class="dash-v3-info-label">核心数</span>
              <span class="dash-v3-info-value">${systemInfo.cpuInfo.cores}</span>
            </div>
            <div class="dash-v3-info-item">
              <span class="dash-v3-info-label">运行时间</span>
              <span class="dash-v3-info-value">${systemInfo.uptime}</span>
            </div>
          </div>
        </div>

        <div class="dash-v3-row dash-v3-row-charts">
          <div class="dash-v3-card">
            <div class="dash-v3-card-header">
              <span class="dash-v3-card-title">CPU使用率</span>
              <span class="dash-v3-card-value">${cpuUsage.toFixed(0)}<span class="dash-v3-card-unit">%</span></span>
            </div>
            <div class="dash-v3-card-body dash-v3-center">
              <div class="dash-v3-ring-wrap">
                <div class="dash-v3-ring" style="--ring-value: ${cpuUsage}; --ring-gradient: linear-gradient(135deg, #22d3ee 0%, #2563eb 52%, #7c3aed 100%);">
                  <div class="dash-v3-ring-inner">
                    <span class="dash-v3-ring-value">${cpuUsage.toFixed(0)}<span class="dash-v3-ring-unit">%</span></span>
                    <span class="dash-v3-ring-label">CPU使用率</span>
                  </div>
                </div>
                <div class="dash-v3-mini-bars">
                  ${this.renderMiniBarChart(this.memoryHistory.slice(-10), '#3b82f6')}
                </div>
              </div>
            </div>
          </div>

          <div class="dash-v3-card">
            <div class="dash-v3-card-header">
              <span class="dash-v3-card-title">磁盘空间分布</span>
              <span class="dash-v3-card-value">${systemInfo.diskUsage.used} / ${systemInfo.diskUsage.total}</span>
            </div>
            <div class="dash-v3-card-body dash-v3-center">
              <div class="dash-v3-ring" style="--ring-value: ${diskUsage}; --ring-gradient: linear-gradient(135deg, #fde047 0%, #f97316 55%, #ef4444 100%);">
                <div class="dash-v3-ring-inner">
                  <span class="dash-v3-ring-value">${diskUsage.toFixed(0)}<span class="dash-v3-ring-unit">%</span></span>
                  <span class="dash-v3-ring-label">使用率</span>
                </div>
              </div>
            </div>
            <div class="dash-v3-card-footer">
              <span>可用 ${systemInfo.diskUsage.available}</span>
              <span>1 分区</span>
            </div>
          </div>

          <div class="dash-v3-card">
            <div class="dash-v3-card-header">
              <span class="dash-v3-card-title">系统负载</span>
              <span class="dash-v3-card-value">${loadAvg.slice(0, 3).join(' / ')}</span>
            </div>
            <div class="dash-v3-card-body dash-v3-center">
              <div class="dash-v3-ring" style="--ring-value: ${loadPercent}; --ring-gradient: linear-gradient(135deg, #a78bfa 0%, #8b5cf6 55%, #ec4899 100%);">
                <div class="dash-v3-ring-inner">
                  <span class="dash-v3-ring-value">${loadPercent.toFixed(0)}<span class="dash-v3-ring-unit">%</span></span>
                  <span class="dash-v3-ring-label">5分钟</span>
                </div>
              </div>
            </div>
            <div class="dash-v3-card-footer">
              <span>1分钟 ${load1.toFixed(2)}</span>
              <span>15分钟 ${load15.toFixed(2)}</span>
            </div>
          </div>

          <div class="dash-v3-card dash-v3-card-network">
            <div class="dash-v3-card-header">
              <span class="dash-v3-card-title">网络状态</span>
              <span class="dash-v3-card-value">${systemInfo.networkConnections}<span class="dash-v3-card-unit"> 连接</span></span>
            </div>
            <div class="dash-v3-card-body">
              <div class="dash-v3-net-stats">
                <div class="dash-v3-net-stat">
                  <span class="dash-v3-net-label">上传速率</span>
                  <span class="dash-v3-net-val">--</span>
                </div>
                <div class="dash-v3-net-stat">
                  <span class="dash-v3-net-label">下载速率</span>
                  <span class="dash-v3-net-val">--</span>
                </div>
                <div class="dash-v3-net-stat">
                  <span class="dash-v3-net-label">响应时间</span>
                  <span class="dash-v3-net-val">--</span>
                </div>
              </div>
              <div class="dash-v3-net-chart-box">
                <div class="dash-v3-net-chart-grid"></div>
                <div class="dash-v3-net-charts">
                  <div class="dash-v3-net-chart-item">
                    <div class="dash-v3-net-mini-chart">${this.renderNetMiniChart(this.memoryHistory.slice(-20), '#22c55e')}</div>
                    <span class="dash-v3-net-chart-label">下载</span>
                  </div>
                  <div class="dash-v3-net-chart-item">
                    <div class="dash-v3-net-mini-chart">${this.renderNetMiniChart(this.diskHistory.slice(-20), '#3b82f6')}</div>
                    <span class="dash-v3-net-chart-label">上传</span>
                  </div>
                  <div class="dash-v3-net-chart-item">
                    <div class="dash-v3-net-mini-chart">${this.renderNetMiniChart(this.memoryHistory.slice(-20), '#f59e0b')}</div>
                    <span class="dash-v3-net-chart-label">响应</span>
                  </div>
                </div>
              </div>
              <div class="dash-v3-net-legend">
                <div class="dash-v3-net-chart-item">
                  <span class="dash-v3-net-legend-dot download"></span>
                  <span class="dash-v3-net-chart-label">下载</span>
                </div>
                <div class="dash-v3-net-chart-item">
                  <span class="dash-v3-net-legend-dot upload"></span>
                  <span class="dash-v3-net-chart-label">上传</span>
                </div>
                <div class="dash-v3-net-chart-item">
                  <span class="dash-v3-net-legend-dot latency"></span>
                  <span class="dash-v3-net-chart-label">响应</span>
                </div>
              </div>
            </div>
          </div>
        </div>

        <div class="dash-v3-row dash-v3-row-lines">
          <div class="dash-v3-card dash-v3-card-wide">
            <div class="dash-v3-card-header">
              <span class="dash-v3-card-title">内存使用率</span>
              <span class="dash-v3-card-value">${memUsage.toFixed(0)}<span class="dash-v3-card-unit">%</span></span>
            </div>
            <div class="dash-v3-card-body dash-v3-chart-body">
              <div class="dash-v3-line-chart-grid" id="chart-memory">
                ${this.renderLineChartWithGrid(this.memoryHistory.slice(-20), '#06b6d4')}
              </div>
              ${this.renderUsageBlocks(memUsage, '#06b6d4')}
            </div>
            <div class="dash-v3-card-footer">
              <span>已用 ${systemInfo.memoryUsage.used}</span>
              <span>总计 ${systemInfo.memoryUsage.total}</span>
            </div>
          </div>

          <div class="dash-v3-card dash-v3-card-wide">
            <div class="dash-v3-card-header">
              <span class="dash-v3-card-title">磁盘使用率</span>
              <span class="dash-v3-card-value">${diskUsage.toFixed(0)}<span class="dash-v3-card-unit">%</span></span>
            </div>
            <div class="dash-v3-card-body dash-v3-chart-body">
              <div class="dash-v3-line-chart-grid" id="chart-disk-trend">
                ${this.renderLineChartWithGrid(this.diskHistory.slice(-20), '#ef4444')}
              </div>
              ${this.renderUsageBlocks(diskUsage, '#ef4444')}
            </div>
            <div class="dash-v3-card-footer">
              <span>已用 ${systemInfo.diskUsage.used} / ${systemInfo.diskUsage.total}</span>
              <span>可用 ${systemInfo.diskUsage.available}</span>
            </div>
          </div>
        </div>
      </div>
    `;
  }

  private renderMiniBarChart(points: number[], color: string): string {
    if (!points.length) return '';
    const barWidth = 4;
    const gap = 2;
    const chartWidth = points.length * (barWidth + gap);
    const height = 20;
    const max = Math.max(...points, 1);
    const bars = points.map((p, i) => {
      const barHeight = Math.max(1, (p / max) * (height - 2));
      const x = i * (barWidth + gap);
      const opacity = 0.3 + (p / max) * 0.7;
      return `<rect x="${x}" y="${height - barHeight}" width="${barWidth}" height="${barHeight}" fill="${color}" opacity="${opacity}" rx="1"/>`;
    }).join('');
    return `<svg viewBox="0 0 ${chartWidth} ${height}" style="width:100%;height:${height}px;"><defs><linearGradient id="bar-grad-${color.replace('#','')}" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stop-color="${color}" stop-opacity="0.9"/><stop offset="100%" stop-color="${color}" stop-opacity="0.3"/></linearGradient></defs>${bars.replace(new RegExp(color, 'g'), `url(#bar-grad-${color.replace('#','')})`)}</svg>`;
  }

  private renderNetMiniChart(points: number[], color: string): string {
    if (!points.length) return '';
    const width = 80;
    const height = 24;
    const displayPoints = points.length === 1 ? [points[0], points[0]] : points;
    const min = Math.min(...displayPoints);
    const max = Math.max(...displayPoints);
    const range = Math.max(1, max - min);
    const stepX = width / Math.max(1, displayPoints.length - 1);
    const coords = displayPoints.map((p, i) => {
      const x = i * stepX;
      const y = height - ((p - min) / range) * (height - 4) - 2;
      return `${x},${y}`;
    });
    const linePath = `M${coords.join(' L')}`;
    return `<svg viewBox="0 0 ${width} ${height}" preserveAspectRatio="none" style="width:100%;height:${height}px;"><path d="${linePath}" fill="none" stroke="${color}" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg>`;
  }

  private renderLineChartWithGrid(points: number[], color: string): string {
    if (!points.length) return '';
    const width = 600;
    const height = 120;
    const padding = 10;
    const chartW = width - padding * 2;
    const chartH = height - padding * 2;

    const displayPoints = points.length === 1 ? [points[0], points[0]] : points;
    const min = 0;
    const max = 100;
    const range = max - min;
    const stepX = chartW / Math.max(1, displayPoints.length - 1);

    const coords = displayPoints.map((p, i) => {
      const x = padding + i * stepX;
      const y = padding + chartH - ((p - min) / range) * chartH;
      return `${x},${y}`;
    });

    const linePath = `M${coords.join(' L')}`;
    const areaPath = `M${coords[0].split(',')[0]},${padding + chartH} L${coords.join(' L')} L${coords[coords.length-1].split(',')[0]},${padding + chartH} Z`;

    const horizontalLines = [0, 25, 50, 75, 100].map(v => {
      const y = padding + chartH - (v / 100) * chartH;
      return `<line x1="${padding}" y1="${y}" x2="${width-padding}" y2="${y}" stroke="rgba(148,163,184,0.18)" stroke-width="1"/>`;
    }).join('');

    const verticalLines = Array.from({ length: 24 }, (_, index) => {
      const x = padding + (chartW / 23) * index;
      return `<line x1="${x}" y1="${padding}" x2="${x}" y2="${height - padding}" stroke="rgba(148,163,184,0.12)" stroke-width="1"/>`;
    }).join('');

    return `
      <svg viewBox="0 0 ${width} ${height}" style="width:100%;height:100%;">
        <defs>
          <linearGradient id="area-${color.replace('#','')}" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stop-color="${color}" stop-opacity="0.15"/>
            <stop offset="100%" stop-color="${color}" stop-opacity="0"/>
          </linearGradient>
        </defs>
        ${verticalLines}
        ${horizontalLines}
        <path d="${areaPath}" fill="url(#area-${color.replace('#','')})"/>
        <path d="${linePath}" fill="none" stroke="${color}" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>
      </svg>
    `;
  }

  private renderUsageBlocks(value: number, color: string): string {
    const clamped = Math.max(0, Math.min(100, value));
    const activeCount = Math.min(20, Math.ceil(clamped / 5));
    const blocks = Array.from({ length: 20 }, (_, index) => {
      const active = index < activeCount;
      return `<span class="dash-v3-usage-block${active ? ' active' : ''}" style="--usage-color: ${color}; --usage-index: ${index};"></span>`;
    }).join('');

    return `<div class="dash-v3-usage-strip" aria-hidden="true">${blocks}</div>`;
  }

  private renderMiniLineChart(points: number[], color: string): string {
    if (!points.length) return '';
    const width = 400;
    const chartHeight = 80;
    const indicatorHeight = 20;
    const height = chartHeight + indicatorHeight + 10;
    
    const baseline = 50;
    
    const displayPoints = points.length === 1 ? [points[0], points[0]] : points;
    
    const min = Math.min(...displayPoints);
    const max = Math.max(...displayPoints);
    
    const latestValue = displayPoints[displayPoints.length - 1];
    
    let yAxisMin: number;
    let yAxisMax: number;
    
    if (min >= baseline) {
      yAxisMin = baseline;
      yAxisMax = 100;
    } else if (max <= baseline) {
      yAxisMin = 0;
      yAxisMax = baseline;
    } else {
      yAxisMin = 0;
      yAxisMax = 100;
    }
    
    const range = yAxisMax - yAxisMin;
    const stepX = width / Math.max(1, displayPoints.length - 1);
    
    const baselineY = chartHeight - ((baseline - yAxisMin) / range) * (chartHeight - 10) - 5;
    
    const coords = displayPoints.map((p, i) => {
      const x = i * stepX;
      const y = chartHeight - ((p - yAxisMin) / range) * (chartHeight - 10) - 5;
      return `${x},${y}`;
    });
    
    const areaPath = `M0,${chartHeight} L${coords.join(' L')} L${width},${chartHeight} Z`;
    const linePath = `M${coords.join(' L')}`;
    
    const indicatorRects = Array.from({ length: 10 }, (_, i) => {
      const rectWidth = 28;
      const rectHeight = 10;
      const rectX = i * (rectWidth + 10) + 20;
      const rectY = chartHeight + 5;
      const threshold = (i + 1) * 10;
      const isActive = latestValue >= threshold;
      const fill = isActive ? color : 'rgba(255,255,255,0.1)';
      const rx = 4;
      
      return `<rect x="${rectX}" y="${rectY}" width="${rectWidth}" height="${rectHeight}" rx="${rx}" fill="${fill}" />`;
    }).join('\n');
    
    return `
      <svg viewBox="0 0 ${width} ${height}" preserveAspectRatio="none" style="width:100%;height:100%;">
        <defs>
          <linearGradient id="grad-${color.replace('#', '')}" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stop-color="${color}" stop-opacity="0.3"/>
            <stop offset="100%" stop-color="${color}" stop-opacity="0"/>
          </linearGradient>
        </defs>
        <line x1="0" y1="${baselineY}" x2="${width}" y2="${baselineY}" stroke="rgba(255,255,255,0.2)" stroke-width="1" stroke-dasharray="4,4"/>
        <path d="${areaPath}" fill="url(#grad-${color.replace('#', '')})" />
        <path d="${linePath}" fill="none" stroke="${color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
        ${indicatorRects}
      </svg>
    `;
  }

  /**
   * 渲染空仪表盘
   */
  private renderEmptyDashboard(): string {
    return `
      <div class="dashboard-empty">
        <div class="empty-state-icon">
          ${this.renderDashboardPanelIcon(48)}
        </div>
        <h3>系统监控仪表盘</h3>
        <p>请先连接到Linux服务器以查看系统监控信息。连接成功后，这里将显示详细的系统状态和性能指标。</p>
        <button class="modern-btn primary" onclick="window.showServerModal()">
          ${LinkOne({ theme: 'outline', size: '16', fill: 'currentColor' })}
          <span>连接服务器</span>
        </button>
      </div>
    `;
  }

  private renderConnectedButNoData(): string {
    return `
      <div class="dashboard-empty">
        <div class="empty-state-icon">
          ${this.renderDashboardPanelIcon(48)}
        </div>
        <h3>已连接服务器，正在加载监控数据</h3>
        <p>连接状态正常，但系统监控信息尚未返回。请点击下方按钮重试加载。</p>
        <button class="modern-btn primary" onclick="window.loadSystemDetailedInfo(true)">
          ${Refresh({ theme: 'outline', size: '16', fill: 'currentColor' })}
          <span>刷新数据</span>
        </button>
      </div>
    `;
  }

  private renderDashboardPanelIcon(size: 24 | 48): string {
    return `
      <img
        class="dashboard-panel-icon dashboard-panel-icon-${size}"
        src="/icons/dashboard-panel.png"
        alt=""
        onload="this.nextElementSibling.classList.add('hidden')"
        onerror="this.classList.add('hidden')"
      />
      <span class="dashboard-panel-icon-fallback">
        ${DashboardIcon({ theme: 'filled', size: String(size), fill: 'currentColor' })}
      </span>
    `;
  }

  /**
   * 格式化时间
   */
  private formatTime(date: Date): string {
    const input = date instanceof Date ? date : new Date(date);
    const year = input.getFullYear();
    const month = String(input.getMonth() + 1).padStart(2, '0');
    const day = String(input.getDate()).padStart(2, '0');
    const hours = String(input.getHours()).padStart(2, '0');
    const minutes = String(input.getMinutes()).padStart(2, '0');
    const seconds = String(input.getSeconds()).padStart(2, '0');
    return `${year}/${month}/${day} ${hours}:${minutes}:${seconds}`;
  }

  /**
   * 获取CPU使用率
   */
  private getCpuUsage(systemInfo: SystemInfo): string {
    const usage = systemInfo.cpuInfo.usage.replace('%', '');
    const value = Number.parseFloat(usage);
    return Number.isFinite(value) ? value.toFixed(1) : '0.0';
  }

  /**
   * 获取内存使用率
   */
  private getMemoryUsage(systemInfo: SystemInfo): string {
    const total = this.parseMemoryValue(systemInfo.memoryUsage.total);
    const used = this.parseMemoryValue(systemInfo.memoryUsage.used);
    if (total <= 0) return '0.0';
    return ((used / total) * 100).toFixed(1);
  }

  /**
   * 获取磁盘使用率
   */
  private getDiskUsage(systemInfo: SystemInfo): string {
    const value = Number.parseFloat(systemInfo.diskUsage.percentage.replace('%', ''));
    return Number.isFinite(value) ? value.toFixed(1) : '0.0';
  }

  /**
   * 解析内存值
   */
  private parseMemoryValue(memStr: string): number {
    const match = memStr.trim().match(/^(\d+(?:\.\d+)?)\s*([KMGT]?B)?$/i);
    if (!match) return 0;
    const value = Number.parseFloat(match[1]);
    const unit = (match[2] || 'MB').toUpperCase();
    if (!Number.isFinite(value)) return 0;
    if (unit === 'KB') return value / 1024;
    if (unit === 'MB') return value;
    if (unit === 'GB') return value * 1024;
    if (unit === 'TB') return value * 1024 * 1024;
    return value;
  }

  /**
   * 检测系统类型并更新概览中的 OS 字段
   */
  private async detectAndShowSystemType(): Promise<void> {
    try {
      const info = await SystemDetector.detectSystem();
      const displayName = info.type === 'unknown' && info.prettyName
        ? info.prettyName
        : SystemDetector.getSystemDisplayName(info.type);
      const systemText = info.version && info.type !== 'unknown'
        ? `${displayName} ${info.version}`
        : displayName;

      this.systemMetaCache = {
        ...(this.systemMetaCache || {
          kernel: '--',
          arch: '--',
          virtualization: '--',
          timezone: Intl.DateTimeFormat().resolvedOptions().timeZone || '--'
        }),
        os: systemText
      };
      const osEl = document.getElementById('dashboard-os-value');
      if (osEl) {
        osEl.textContent = systemText;
        osEl.setAttribute('title', systemText);
      }
    } catch {
      // ignore
    }
  }

  /**
   * 加载系统元数据
   */
  private async loadSystemMeta(): Promise<void> {
    if (this.systemMetaCache && this.systemMetaCache.kernel !== '--') {
      this.updateSystemMetaToDom(this.systemMetaCache);
      return;
    }

    const app = (window as any).app;
    if (!app?.sshManager?.executeCommand) return;

    try {
      const command = [
        'echo "__KERNEL__$(uname -r 2>/dev/null)"',
        'echo "__ARCH__$(uname -m 2>/dev/null)"',
        'echo "__TZ__$( (timedatectl show -p Timezone --value 2>/dev/null || cat /etc/timezone 2>/dev/null || date +%Z) | head -n1 )"',
        'echo "__VIRT__$(systemd-detect-virt 2>/dev/null || echo none)"'
      ].join(' && ');

      const raw = await app.sshManager.executeCommand(command);
      const lines = String(raw).split('\n').map((line: string) => line.trim());
      const meta = {
        os: this.systemMetaCache?.os || 'Linux',
        kernel: lines.find((line: string) => line.startsWith('__KERNEL__'))?.replace('__KERNEL__', '') || '--',
        arch: lines.find((line: string) => line.startsWith('__ARCH__'))?.replace('__ARCH__', '') || '--',
        timezone: lines.find((line: string) => line.startsWith('__TZ__'))?.replace('__TZ__', '') || '--',
        virtualization: lines.find((line: string) => line.startsWith('__VIRT__'))?.replace('__VIRT__', '') || '--'
      };
      this.systemMetaCache = meta;
      this.updateSystemMetaToDom(meta);
    } catch {
      // ignore
    }
  }

  /**
   * 更新系统元数据到 DOM
   */
  private updateSystemMetaToDom(meta: { os: string; kernel: string; arch: string; virtualization: string; timezone: string }): void {
    const mapping: Array<{ id: string; value: string }> = [
      { id: 'dashboard-os-value', value: meta.os },
      { id: 'dashboard-kernel-value', value: meta.kernel },
      { id: 'dashboard-arch-value', value: meta.arch },
      { id: 'dashboard-virt-value', value: meta.virtualization },
      { id: 'dashboard-timezone-value', value: meta.timezone }
    ];

    mapping.forEach(item => {
      const el = document.getElementById(item.id);
      if (!el) return;
      el.textContent = item.value;
      el.setAttribute('title', item.value);
    });
  }

  updateMetricCards(systemInfo: SystemInfo): void {
    const memUsage = parseFloat(this.getMemoryUsage(systemInfo));
    const diskUsage = parseFloat(this.getDiskUsage(systemInfo));

    this.memoryHistory.push(memUsage);
    this.diskHistory.push(diskUsage);
    while (this.memoryHistory.length > DashboardRenderer.HISTORY_MAX) this.memoryHistory.shift();
    while (this.diskHistory.length > DashboardRenderer.HISTORY_MAX) this.diskHistory.shift();

    const memEl = document.querySelector('#chart-memory');
    if (memEl) {
      memEl.innerHTML = this.renderMiniLineChart(this.memoryHistory.slice(-10), '#06b6d4');
    }

    const diskEl = document.querySelector('#chart-disk-trend');
    if (diskEl) {
      diskEl.innerHTML = this.renderMiniLineChart(this.diskHistory.slice(-10), '#f97316');
    }
  }

  initCharts(_force: boolean = false): void {
  }

}

// Declare ApexCharts global
declare var ApexCharts: any;
