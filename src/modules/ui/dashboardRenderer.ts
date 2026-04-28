/**
 * 系统信息仪表盘渲染器
 * 负责渲染系统监控信息和统计数据
 */

import type { SystemInfo } from '../ssh/sshManager';
import { sshConnectionManager } from '../remote/sshConnectionManager';
import apexchartsScriptUrl from '../../assets/js/apexcharts.min.js?url';
import {
  Computer,
  TrendTwo,
  LinkOne,
  SettingTwo,
  Peoples,
  Dashboard as DashboardIcon,
  Refresh
} from '@icon-park/svg';

export class DashboardRenderer {
  private charts: Map<string, any> = new Map();
  private currentTheme: string = 'dark';
  private history: {
    cpu: { x: number; y: number }[];
    memory: { x: number; y: number }[];
    network: { rx: { x: number; y: number }[]; tx: { x: number; y: number }[] };
  } = {
      cpu: [],
      memory: [],
      network: { rx: [], tx: [] }
    };
  private lastNetworkData: { rx: number; tx: number; timestamp: number } | null = null;
  private currentSystemInfo?: SystemInfo;
  private isTopProcessesLoading = false;
  private topProcessesCache: Array<{ pid: string; user: string; cpu: string; memory: string; command: string }> | null = null;
  private topProcessesCacheTime: number = 0;
  private readonly TOP_PROCESSES_CACHE_TTL = 5000;
  private apexChartsLoadPromise: Promise<boolean> | null = null;

  constructor() {
    (window as any).dashboardRendererInstance = this;
    (window as any).updateDashboardTopProcesses = this.updateTopProcesses.bind(this);
  }

  /**
   * 渲染系统信息仪表盘
   */
  renderDashboard(systemInfo?: SystemInfo, theme: string = 'dark'): string {
    this.currentTheme = theme;
    const isConnected = sshConnectionManager.isConnected();

    if (!isConnected) {
      return this.renderEmptyDashboard();
    }
    if (!systemInfo) {
      return this.renderConnectedButNoData();
    }

    this.updateHistory(systemInfo);

    // 延迟初始化图表和 Top Processes（等待 DOM 插入）
    setTimeout(() => {
      this.initCharts(false);
      if ((window as any).updateDashboardTopProcesses) {
        (window as any).updateDashboardTopProcesses(false);
      }
    }, 100);

    return `
      <div class="dashboard-container">
        <div class="dashboard-header">
          <div class="header-left">
            <div class="header-icon">
              ${this.renderDashboardPanelIcon(24)}
            </div>
            <div class="header-info">
              <h2>系统监控仪表盘</h2>
              <div class="last-update">
                <span>最后更新: ${this.formatTime(systemInfo.lastUpdate)}</span>
                <span class="separator">•</span>
                <span>自动刷新: 30秒</span>
              </div>
            </div>
          </div>
          <button class="modern-btn secondary refresh-btn" onclick="window.loadSystemDetailedInfo(true)">
            ${Refresh({ theme: 'outline', size: '14', fill: 'currentColor' })}
            <span>刷新数据</span>
          </button>
        </div>

        <!-- 关键指标概览 (Top Row) -->
        <div class="metrics-overview">
          ${this.renderMetricCard('CPU使用率', this.getCpuUsage(systemInfo), '%', 'warning')}
          ${this.renderMetricCard('内存使用率', this.getMemoryUsage(systemInfo), '%', 'primary')}
          ${this.renderMetricCard('磁盘使用率', this.getDiskUsage(systemInfo), '%', 'error')}
          ${this.renderMetricCard('网络连接', systemInfo.networkConnections.toString(), '个', 'success')}
        </div>

        <!-- Bento Grid Layout -->
        <div class="dashboard-grid-bento">
          
          <!-- Row 1: Disk Space Detailed & Load -->
          <div class="dashboard-card modern-card chart-disk">
            <div class="card-header">
              <div class="card-icon purple">
                ${Computer({ theme: 'filled', size: '18', fill: 'currentColor' })}
              </div>
              <h3>磁盘空间分布</h3>
            </div>
            <div class="card-content partition-list-content">
              ${this.renderPartitionList(systemInfo)}
            </div>
          </div>

          <div class="dashboard-card modern-card chart-load">
            <div class="card-header">
              <div class="card-icon orange">
                ${SettingTwo({ theme: 'filled', size: '18', fill: 'currentColor' })}
              </div>
              <h3>系统负载</h3>
            </div>
            <div class="card-content chart-container">
              <div id="chart-load" class="load-chart"></div>
            </div>
          </div>

          <!-- Row 2: Top Processes & Overview -->
          <div class="dashboard-card modern-card top-processes-card">
             <div class="card-header">
              <div class="card-icon blue">
                ${TrendTwo({ theme: 'filled', size: '18', fill: 'currentColor' })}
              </div>
              <h3>实时 Top 进程 (CPU)</h3>
            </div>
            <div class="card-content table-container" style="overflow-x: auto;">
              ${this.renderTopProcessesTable(systemInfo)}
            </div>
          </div>

          <div class="dashboard-card modern-card system-overview-card">
             <div class="card-header">
              <div class="card-icon secondary">
                ${Peoples({ theme: 'filled', size: '18', fill: 'currentColor' })}
              </div>
              <h3>系统概览</h3>
            </div>
            <div class="card-content">
               <div class="info-list">
                <div class="info-item">
                  <span class="label">主机名</span>
                  <span class="value">${systemInfo.hostname}</span>
                </div>
                <div class="info-item">
                  <span class="label">运行时间</span>
                  <span class="value">${systemInfo.uptime}</span>
                </div>
                <div class="info-item">
                  <span class="label">CPU型号</span>
                  <span class="value" title="${systemInfo.cpuInfo.model}">
                    ${systemInfo.cpuInfo.model}
                  </span>
                </div>
                 <div class="info-item">
                  <span class="label">核心数</span>
                  <span class="value">${systemInfo.cpuInfo.cores} 核</span>
                </div>
                 <div class="info-item">
                  <span class="label">进程数</span>
                  <span class="value">${systemInfo.processCount}</span>
                </div>
              </div>
            </div>
          </div>

        </div>
      </div>
    `;
  }

  /**
   * 渲染 Top 进程表
   */
  private renderTopProcessesTable(systemInfo: SystemInfo): string {
    if (!systemInfo.detailedInfo || !systemInfo.detailedInfo.processes || systemInfo.detailedInfo.processes.length === 0) {
      return this.renderTopProcessesPlaceholder();
    }

    const processes = [...systemInfo.detailedInfo.processes]
      .sort((a, b) => parseFloat(b.cpu) - parseFloat(a.cpu))
      .slice(0, 6);

    return this.renderTopProcessesHTML(processes);
  }

  /**
   * 渲染 Top Processes 占位符（loading 状态）
   */
  private renderTopProcessesPlaceholder(): string {
    return `
      <div class="top-processes-loading" style="display: flex; align-items: center; justify-content: center; padding: 20px; color: var(--text-secondary);">
        <div style="text-align: center;">
          <div style="font-size: 20px; margin-bottom: 8px;">⏳</div>
          <div style="font-size: 13px;">正在加载进程数据...</div>
        </div>
      </div>
    `;
  }

  /**
   * 渲染 Top Processes HTML
   */
  private renderTopProcessesHTML(processes: Array<{ pid: string; user: string; cpu: string; memory: string; command: string }>): string {
    return `
      <table class="modern-table" style="width: 100%; border-collapse: collapse; font-size: 0.9em;">
        <thead>
          <tr style="border-bottom: 1px solid var(--border-color); text-align: left;">
            <th style="padding: 8px;">PID</th>
            <th style="padding: 8px;">用户</th>
            <th style="padding: 8px;">CPU</th>
            <th style="padding: 8px;">内存</th>
            <th style="padding: 8px;">命令</th>
          </tr>
        </thead>
        <tbody>
          ${processes.map(p => `
            <tr style="border-bottom: 1px solid var(--border-color-light);">
              <td style="padding: 8px;">${p.pid}</td>
              <td style="padding: 8px;">${p.user}</td>
              <td style="padding: 8px; color: var(--warning-color);">${p.cpu}%</td>
              <td style="padding: 8px;">${p.memory}%</td>
              <td style="padding: 8px;" title="${p.command}">${this.truncateText(p.command, 25)}</td>
            </tr>
          `).join('')}
        </tbody>
      </table>
    `;
  }

  /**
   * 异步更新 Top Processes（局部更新，不重渲染整个 dashboard）
   */
  async updateTopProcesses(forceRefresh: boolean = false): Promise<void> {
    const now = Date.now();
    
    if (!forceRefresh && this.topProcessesCache && (now - this.topProcessesCacheTime) < this.TOP_PROCESSES_CACHE_TTL) {
      console.log('📋 使用 Top Processes 缓存');
      this.renderTopProcessesToDOM(this.topProcessesCache);
      return;
    }

    if (this.isTopProcessesLoading) {
      console.log('⏳ Top Processes 正在加载中...');
      return;
    }

    this.isTopProcessesLoading = true;
    console.log('🔄 开始异步加载 Top Processes...');

    try {
      const app = (window as any).app;
      if (!app || !app.sshManager) {
        console.warn('⚠️ 无法获取 SSH 管理器');
        return;
      }

      const tabData = await app.sshManager.fetchTabDetail('processes', forceRefresh);
      const processes = tabData?.processes || [];
      
      const sorted = [...processes]
        .sort((a: any, b: any) => parseFloat(b.cpu) - parseFloat(a.cpu))
        .slice(0, 6);

      this.topProcessesCache = sorted;
      this.topProcessesCacheTime = now;
      
      this.renderTopProcessesToDOM(sorted);
      console.log('✅ Top Processes 更新完成');

    } catch (error) {
      console.error('❌ 更新 Top Processes 失败:', error);
    } finally {
      this.isTopProcessesLoading = false;
    }
  }

  /**
   * 将 Top Processes 渲染到 DOM（局部更新）
   */
  private renderTopProcessesToDOM(processes: Array<{ pid: string; user: string; cpu: string; memory: string; command: string }>): void {
    const tableContainer = document.querySelector('.top-processes-card .table-container');
    if (!tableContainer) {
      console.warn('⚠️ 未找到 Top Processes 容器');
      return;
    }

    const html = this.renderTopProcessesHTML(processes);
    tableContainer.innerHTML = html;
  }

  /**
   * 局部更新指标卡片（避免整页重渲染）
   */
  public updateMetricCards(systemInfo: SystemInfo): void {
    try {
      // 更新 CPU 使用率
      const cpuCard = document.querySelector('.metric-card.warning .metric-value');
      if (cpuCard) {
        cpuCard.textContent = this.getCpuUsage(systemInfo);
      }

      // 更新内存使用率
      const memCard = document.querySelector('.metric-card.primary .metric-value');
      if (memCard) {
        memCard.textContent = this.getMemoryUsage(systemInfo);
      }

      // 更新磁盘使用率
      const diskCard = document.querySelector('.metric-card.error .metric-value');
      if (diskCard) {
        diskCard.textContent = this.getDiskUsage(systemInfo);
      }

      // 更新网络连接数
      const netCard = document.querySelector('.metric-card.success .metric-value');
      if (netCard) {
        netCard.textContent = systemInfo.networkConnections.toString();
      }

      // 更新最后更新时间
      const lastUpdateEl = document.querySelector('.last-update span:first-child');
      if (lastUpdateEl) {
        lastUpdateEl.textContent = `最后更新: ${this.formatTime(systemInfo.lastUpdate)}`;
      }

      console.log('✅ 指标卡片已局部更新');
    } catch (error) {
      console.error('❌ 更新指标卡片失败:', error);
    }
  }

  /**
   * Initialize ApexCharts（仅在必要时创建/重建）
   */
  public initCharts(forceRecreate: boolean = false) {
    console.log('🔍 initCharts 被调用，forceRecreate:', forceRecreate);

    const systemInfo = this.currentSystemInfo;
    if (!systemInfo) {
      console.log('⏳ initCharts: 等待系统信息加载...');
      return;
    }

    const apex = this.getApexChartsCtor();
    if (!apex) {
      console.warn('⚠️ initCharts: ApexCharts 未加载，开始动态加载');
      this.ensureApexChartsLoaded().then((loaded) => {
        if (loaded) this.initCharts(forceRecreate);
      });
      return;
    }

    console.log('📊 initCharts: systemInfo 已就绪，loadAverage:', systemInfo.loadAverage);

    if (forceRecreate) {
      this.destroyAllCharts();
    }

    const existingChart = this.charts.get('load');
    const chartEl = document.querySelector("#chart-load") as HTMLElement | null;
    const chartRoot = existingChart ? ((existingChart as any).el as HTMLElement | undefined) : undefined;
    const isMountedToCurrentContainer = !!(existingChart && chartEl && chartRoot && chartEl.contains(chartRoot) && document.body.contains(chartRoot));

    if (existingChart && isMountedToCurrentContainer) {
      console.log('🔄 initCharts: 更新现有图表');
      this.updateLoadChart(systemInfo);
      return;
    }

    if (existingChart && !isMountedToCurrentContainer) {
      console.log('🧹 initCharts: 检测到旧图表实例，先销毁后重建');
      this.destroyAllCharts();
    }

    console.log('🆕 initCharts: 创建新图表');
    this.initLoadChart();
  }

  /**
   * 刷新仪表盘摘要数据（不触发整页重渲染）
   */
  public refreshSummaryData(systemInfo: SystemInfo): void {
    this.currentTheme = (window as any).app?.stateManager?.getState?.()?.theme || this.currentTheme;
    this.updateHistory(systemInfo);
    this.updateMetricCards(systemInfo);
    this.initCharts(false);
  }

  /**
   * 销毁所有图表
   */
  private destroyAllCharts(): void {
    this.charts.forEach(chart => {
      try {
        chart.destroy();
      } catch (e) {
        console.warn('Failed to destroy chart:', e);
      }
    });
    this.charts.clear();
  }

  private getThemeOptions() {
    const isDark = this.currentTheme === 'dark';
    return {
      mode: isDark ? 'dark' : 'light',
      textColor: isDark ? '#94a3b8' : '#475569',
      gridColor: isDark ? 'rgba(255,255,255,0.05)' : 'rgba(0,0,0,0.05)',
      dataLabelColor: isDark ? '#fff' : '#1e293b'
    };
  }

  private initLoadChart() {
    const systemInfo = this.currentSystemInfo;
    if (!systemInfo) {
      console.warn('⚠️ initLoadChart: systemInfo 为空');
      return;
    }

    const chartEl = document.querySelector("#chart-load");
    if (!chartEl) {
      console.warn('⚠️ initLoadChart: #chart-load 元素不存在');
      return;
    }

    const ApexCtor = this.getApexChartsCtor();
    if (!ApexCtor) {
      console.warn('⚠️ initLoadChart: ApexCharts 未加载');
      return;
    }

    const themeOpts = this.getThemeOptions();
    const load = this.getLoadPercentages(systemInfo);
    
    console.log('📊 初始化负载图表，数据:', load);

    const options = {
      series: [{ name: '负载', data: load }],
      chart: { type: 'bar', height: '100%', fontFamily: 'inherit', background: 'transparent', toolbar: { show: false } },
      colors: ['#8B5CF6'],
      plotOptions: { bar: { borderRadius: 4, horizontal: false, columnWidth: '40%', distributed: true } },
      xaxis: {
        categories: ['1 分钟', '5 分钟', '15 分钟'],
        axisBorder: { show: false },
        axisTicks: { show: false },
        labels: { style: { colors: themeOpts.textColor } }
      },
      yaxis: { show: false, min: 0, max: 100 },
      grid: { show: false },
      dataLabels: {
        enabled: true,
        style: { colors: [themeOpts.dataLabelColor] },
        offsetY: -20,
        formatter: (value: number) => `${value.toFixed(1)}%`
      },
      tooltip: {
        y: {
          formatter: (value: number) => `${value.toFixed(1)}%`
        }
      },
      theme: { mode: themeOpts.mode },
      legend: { show: false }
    };
    
    try {
      const chart = new ApexCtor(chartEl, options);
      chart.render();
      this.charts.set('load', chart);
      console.log('✅ 负载图表初始化成功');
    } catch (error) {
      console.error('❌ 初始化负载图表失败:', error);
    }
  }

  /**
   * 更新负载图表（复用实例，不 destroy/recreate）
   */
  private updateLoadChart(systemInfo: SystemInfo): void {
    const chart = this.charts.get('load');
    if (!chart) {
      console.warn('⚠️ 负载图表不存在，跳过更新');
      return;
    }

    try {
      const load = this.getLoadPercentages(systemInfo);
      // 刷新时关闭动画，仅首次初始化时保留动画
      chart.updateSeries([{ data: load }], false);
    } catch (error) {
      console.error('❌ 更新负载图表失败:', error);
    }
  }

  private getApexChartsCtor(): any | null {
    return (window as any).ApexCharts || null;
  }

  private ensureApexChartsLoaded(): Promise<boolean> {
    const existingCtor = this.getApexChartsCtor();
    if (existingCtor) return Promise.resolve(true);
    if (this.apexChartsLoadPromise) return this.apexChartsLoadPromise;

    this.apexChartsLoadPromise = new Promise<boolean>((resolve) => {
      const existingScript = document.querySelector('script[data-lert-apexcharts="1"]') as HTMLScriptElement | null;
      if (existingScript) {
        if (this.getApexChartsCtor()) {
          resolve(true);
          return;
        }
        existingScript.addEventListener('load', () => resolve(!!this.getApexChartsCtor()), { once: true });
        existingScript.addEventListener('error', () => resolve(false), { once: true });
        return;
      }

      const script = document.createElement('script');
      script.src = apexchartsScriptUrl;
      script.async = true;
      script.defer = true;
      script.setAttribute('data-lert-apexcharts', '1');
      script.onload = () => resolve(!!this.getApexChartsCtor());
      script.onerror = () => {
        console.error('❌ ApexCharts 脚本加载失败:', apexchartsScriptUrl);
        resolve(false);
      };
      document.head.appendChild(script);
    });

    return this.apexChartsLoadPromise;
  }

  private getLoadPercentages(systemInfo: SystemInfo): number[] {
    const cores = Math.max(1, Number(systemInfo.cpuInfo?.cores) || 1);
    return systemInfo.loadAverage.map((v: string) => {
      const loadValue = Number.parseFloat(v);
      if (!Number.isFinite(loadValue)) return 0;
      return Math.max(0, Math.min(100, (loadValue / cores) * 100));
    });
  }

  private updateHistory(systemInfo: SystemInfo) {
    const now = new Date().getTime();

    // CPU
    const cpuUsage = parseFloat(this.getCpuUsage(systemInfo));
    this.history.cpu.push({ x: now, y: cpuUsage });
    if (this.history.cpu.length > 60) this.history.cpu.shift();

    // Memory
    const memUsage = parseFloat(this.getMemoryUsage(systemInfo));
    this.history.memory.push({ x: now, y: memUsage });
    if (this.history.memory.length > 60) this.history.memory.shift();

    // Network Speed Calculation
    let rxSpeed = 0;
    let txSpeed = 0;

    if (this.lastNetworkData && systemInfo.networkInfo) {
      const timeDiff = (now - this.lastNetworkData.timestamp) / 1000;
      if (timeDiff > 0) {
        const rxDiff = systemInfo.networkInfo.rxBytes - this.lastNetworkData.rx;
        const txDiff = systemInfo.networkInfo.txBytes - this.lastNetworkData.tx;
        rxSpeed = Math.max(0, rxDiff / 1024 / timeDiff);
        txSpeed = Math.max(0, txDiff / 1024 / timeDiff);
      }
    }

    if (systemInfo.networkInfo) {
      this.lastNetworkData = {
        rx: systemInfo.networkInfo.rxBytes,
        tx: systemInfo.networkInfo.txBytes,
        timestamp: now
      };
    }

    this.history.network.rx.push({ x: now, y: rxSpeed });
    this.history.network.tx.push({ x: now, y: txSpeed });
    if (this.history.network.rx.length > 60) this.history.network.rx.shift();
    if (this.history.network.tx.length > 60) this.history.network.tx.shift();

    this.currentSystemInfo = systemInfo;

    if (this.charts.size > 0) {
      this.updateCharts(systemInfo);
    }
  }

  /**
   * 更新所有图表（复用实例）
   */
  private updateCharts(systemInfo: SystemInfo): void {
    this.updateLoadChart(systemInfo);
  }

  /*
  private updateCharts() {
    if (this.charts.has('cpu-memory')) {
      this.charts.get('cpu-memory').updateSeries([{
        data: this.history.cpu
      }, {
        data: this.history.memory
      }]);
    }
    if (this.charts.has('network')) {
      this.charts.get('network').updateSeries([{
        data: this.history.network.rx
      }, {
        data: this.history.network.tx
      }]);
    }

    const systemInfo = (this as any).currentSystemInfo;
    if (systemInfo) {
      // Disk Chart - Update if exists
      if (this.charts.has('disk')) {
        const diskUsed = parseFloat(systemInfo.diskUsage.percentage.replace('%', ''));
        const diskFree = 100 - diskUsed;
        this.charts.get('disk').updateSeries([diskUsed, diskFree]);
      } else {
        // Initialize if not exists (should be handled by initCharts but just in case)
        this.initDiskChart();
      }

      // Load Chart - Update if exists
      if (this.charts.has('load')) {
        const load = systemInfo.loadAverage.map((v: string) => parseFloat(v));
        this.charts.get('load').updateSeries([{ data: load }]);
      } else {
        this.initLoadChart();
      }
    }
  }
  */

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

  /**
   * 截断文本
   */
  private truncateText(text: string, maxLength: number): string {
    if (text.length <= maxLength) return text;
    return text.substring(0, maxLength - 3) + '...';
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
    return date.toLocaleString('zh-CN', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit'
    });
  }

  /**
   * 渲染指标卡片
   */
  private renderMetricCard(title: string, value: string, unit: string, type: string): string {
    return `
      <div class="metric-card ${type}">
        <div class="metric-header">
          <span class="metric-title">${title}</span>
        </div>
        <div class="metric-content">
          <span class="metric-value">${value}</span>
          <span class="metric-unit">${unit}</span>
        </div>
      </div>
    `;
  }

  /**
   * 获取CPU使用率
   */
  private getCpuUsage(systemInfo: SystemInfo): string {
    // 从cpuInfo.usage中提取数字
    const usage = systemInfo.cpuInfo.usage.replace('%', '');
    return parseFloat(usage).toFixed(1);
  }

  /**
   * 获取内存使用率
   */
  private getMemoryUsage(systemInfo: SystemInfo): string {
    const total = this.parseMemoryValue(systemInfo.memoryUsage.total);
    const used = this.parseMemoryValue(systemInfo.memoryUsage.used);
    return ((used / total) * 100).toFixed(1);
  }

  /**
   * 获取磁盘使用率
   */
  private getDiskUsage(systemInfo: SystemInfo): string {
    return systemInfo.diskUsage.percentage.replace('%', '');
  }

  /**
   * 解析内存值
   */
  private parseMemoryValue(memStr: string): number {
    const value = parseFloat(memStr.replace(/[^\d.]/g, ''));
    if (memStr.includes('GB')) return value * 1024;
    return value;
  }

  /**
   * 渲染分区列表
   */
  private renderPartitionList(systemInfo: SystemInfo): string {
    if (!systemInfo.partitions || systemInfo.partitions.length === 0) {
      // Fallback if no partitions data (old backend or error)
      return this.renderLegacyDiskInfo(systemInfo);
    }

    return systemInfo.partitions.map(part => {
      const percentage = parseFloat(part.percentage.replace('%', ''));
      
      // Calculate color code for inline style if needed, or use CSS variables
      const colorVar = percentage > 90 ? 'var(--error-color)' : (percentage > 75 ? 'var(--warning-color)' : 'var(--primary-color)');

      return `
        <div class="partition-item" style="display: flex; flex-direction: column; gap: 6px;">
          <div class="partition-header" style="display: flex; justify-content: space-between; align-items: center; font-size: 13px;">
            <div class="partition-info" style="display: flex; align-items: center; gap: 8px;">
              <span class="partition-mount" style="font-weight: 600; color: var(--text-primary);">${part.mountpoint}</span>
              <span class="partition-fs" style="font-size: 11px; color: var(--text-secondary); background: var(--bg-tertiary); padding: 2px 6px; border-radius: 4px;">${part.filesystem}</span>
            </div>
            <div class="partition-stats" style="color: var(--text-secondary);">
              <span style="color: var(--text-primary); font-weight: 500;">${part.used}</span> / ${part.size}
            </div>
          </div>
          <div class="partition-bar-bg" style="width: 100%; height: 8px; background: var(--bg-tertiary); border-radius: 4px; overflow: hidden;">
            <div class="partition-bar-fill" style="width: ${part.percentage}; height: 100%; background: ${colorVar}; border-radius: 4px; transition: width 0.5s ease;"></div>
          </div>
          <div class="partition-footer" style="display: flex; justify-content: flex-end; font-size: 11px; color: var(--text-secondary);">
            <span>可用: <span style="color: var(--success-color);">${part.available}</span></span>
            <span style="margin: 0 4px;">•</span>
            <span>使用率: <span style="color: ${colorVar}; font-weight: 600;">${part.percentage}</span></span>
          </div>
        </div>
      `;
    }).join('');
  }

  private renderLegacyDiskInfo(systemInfo: SystemInfo): string {
    return `
      <div class="disk-detail-item" style="display: flex; justify-content: space-between; margin-bottom: 8px; border-bottom: 1px solid var(--border-color); padding-bottom: 4px;">
        <span class="label" style="color: var(--text-secondary);">总空间</span>
        <span class="value" style="font-weight: 600;">${systemInfo.diskUsage.total}</span>
      </div>
      <div class="disk-detail-item" style="display: flex; justify-content: space-between; margin-bottom: 8px; border-bottom: 1px solid var(--border-color); padding-bottom: 4px;">
        <span class="label" style="color: var(--text-secondary);">已使用</span>
        <span class="value" style="font-weight: 600; color: var(--error-color);">${systemInfo.diskUsage.used}</span>
      </div>
      <div class="disk-detail-item" style="display: flex; justify-content: space-between; margin-bottom: 8px; border-bottom: 1px solid var(--border-color); padding-bottom: 4px;">
        <span class="label" style="color: var(--text-secondary);">可用空间</span>
        <span class="value" style="font-weight: 600; color: var(--success-color);">${systemInfo.diskUsage.available}</span>
      </div>
      <div class="disk-detail-item" style="display: flex; justify-content: space-between;">
        <span class="label" style="color: var(--text-secondary);">使用率</span>
        <span class="value highlight" style="font-weight: bold; color: var(--primary-color);">${systemInfo.diskUsage.percentage}</span>
      </div>
    `;
  }
}

// Declare ApexCharts global
declare var ApexCharts: any;
