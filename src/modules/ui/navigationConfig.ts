/**
 * 导航配置模块
 * 定义所有导航项的结构、模式可见性和排序
 */

import type { AppPage, UIMode } from './pageTypes';

export type IconKey =
  | 'Dashboard'
  | 'ApplicationMenu'
  | 'FolderOpen'
  | 'Code'
  | 'Rocket'
  | 'Data'
  | 'Log'
  | 'Calendar'
  | 'SettingTwo'
  | 'User'
  | 'Lock'
  | 'Shield'
  | 'Analysis'
  | 'Fire'
  | 'FileText'
  | 'Config'
  | 'NetworkTree'
  | 'System'
  | 'Time'
  | 'SettingConfig'
  | 'Cpu'
  | 'Memory'
  | 'Speed'
  | 'LinkCloud'
  | 'BookOpen'
  | 'Message'
  | 'CheckOne'
  | 'CloseOne'
  | 'Refresh'
  | 'Copy'
  | 'Loading'
  | 'Send';

export interface NavigationItem {
  id: AppPage;
  title: string;
  description: string;
  iconKey: IconKey;
  visibleInModes: UIMode[];
}

const ALL_NAV_ITEMS: NavigationItem[] = [
  {
    id: 'dashboard',
    title: '仪表板',
    description: '查看服务器实时状态概览',
    iconKey: 'Dashboard',
    visibleInModes: ['classic']
  },
  {
    id: 'system-info',
    title: '系统信息',
    description: '查看详细系统配置信息',
    iconKey: 'ApplicationMenu',
    visibleInModes: ['classic']
  },
  {
    id: 'remote-operations',
    title: 'SFTP文件',
    description: '远程文件管理与传输',
    iconKey: 'FolderOpen',
    visibleInModes: ['classic']
  },
  {
    id: 'emergency-commands',
    title: '命令执行',
    description: '批量执行应急响应命令',
    iconKey: 'Code',
    visibleInModes: ['classic']
  },
  {
    id: 'quick-detection',
    title: '快速检测',
    description: '一键安全检测与风险评估',
    iconKey: 'Rocket',
    visibleInModes: ['classic']
  },
  {
    id: 'log-analysis',
    title: '日志审计',
    description: '系统日志分析与溯源',
    iconKey: 'Log',
    visibleInModes: ['classic']
  },
  {
    id: 'payloader',
    title: '技能知识库',
    description: '安全测试Payload生成',
    iconKey: 'Code',
    visibleInModes: ['classic']
  },

];

const NAV_ORDER: Record<UIMode, AppPage[]> = {
  'classic': [
    'dashboard',
    'system-info',
    'remote-operations',
    'emergency-commands',
    'quick-detection',
    'log-analysis',
    'payloader',
    'ssh-terminal'
  ],
  'ai': [
    'ai-command-center',
    'dashboard',
    'system-info',
    'remote-operations',
    'emergency-commands',
    'quick-detection',
    'log-analysis',
    'payloader',
    'ssh-terminal'
  ]
};

export const NAVIGATION_ITEMS: NavigationItem[] = ALL_NAV_ITEMS;

export function getNavigationItemsForMode(mode: UIMode): NavigationItem[] {
  const order = NAV_ORDER[mode];
  const visibleItems = NAVIGATION_ITEMS.filter(
    item => item.visibleInModes.includes(mode)
  );

  return order
    .map(id => visibleItems.find(item => item.id === id))
    .filter((item): item is NavigationItem => item !== undefined);
}

export function getNavigationItemById(id: AppPage): NavigationItem | undefined {
  return NAVIGATION_ITEMS.find(item => item.id === id);
}
