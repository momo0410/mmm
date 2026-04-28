/**
 * 统一页面类型定义
 * 所有页面类型和 UI 模式类型集中定义，确保类型一致性
 */
export type UIMode = 'classic' | 'ai';
export type AppPage =
  | 'dashboard'
  | 'ai-command-center'
  | 'system-info'
  | 'ssh-terminal'
  | 'remote-operations'
  | 'emergency-commands'
  | 'log-analysis'
  | 'quick-detection'
  | 'database'
  | 'payloader';
export const APP_PAGES: AppPage[] = [
  'dashboard',
  'ai-command-center',
  'system-info',
  'ssh-terminal',
  'remote-operations',
  'emergency-commands',
  'log-analysis',
  'quick-detection',
  'database',
  'payloader'
];
export const DEFAULT_PAGE: AppPage = 'dashboard';
export const DEFAULT_UI_MODE: UIMode = 'classic';
export const PAGE_TITLES: Record<AppPage, string> = {
  'dashboard': '仪表板',
  'ai-command-center': 'AI指挥台',
  'system-info': '系统信息',
  'ssh-terminal': 'SSH终端',
  'remote-operations': 'SFTP文件',
  'emergency-commands': '命令执行',
  'log-analysis': '日志审计',
  'quick-detection': '快速检测',
  'database': '数据库',
  'payloader': '技能知识库'
};
export const PAGE_DESCRIPTIONS: Record<AppPage, string> = {
  'dashboard': '查看服务器实时状态概览',
  'ai-command-center': '统一管理 AI 对话、检索与自动化能力',
  'system-info': '查看详细系统配置信息',
  'ssh-terminal': '远程SSH终端',
  'remote-operations': '远程文件管理与传输',
  'emergency-commands': '批量执行应急响应命令',
  'log-analysis': '系统日志分析与溯源',
  'quick-detection': '一键安全检测与风险评估',
  'database': '数据库管理',
  'payloader': '安全测试Payload生成'
};
/**
 * 统一应用状态类型定义（全局唯一来源）
 */
export interface AppState {
  theme: 'light' | 'dark' | 'sakura';
  uiMode: UIMode;
  isConnected: boolean;
  currentServer?: string;
  serverInfo?: any;
  loading: boolean;
  currentPage: AppPage;
}
/**
 * 服务器信息类型定义（全局唯一来源）
 */
export interface ServerInfo {
  name: string;
  host: string;
  port: number;
  username?: string;
  detailedInfo?: any;
}
