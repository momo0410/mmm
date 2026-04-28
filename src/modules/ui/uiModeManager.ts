/**
 * UI 模式管理器
 * 负责管理 classic 和 ai 两种 UI 模式的切换和默认值
 */

import type { AppPage, UIMode } from './pageTypes';
import { DEFAULT_PAGE } from './pageTypes';

export const MODE_DEFAULT_PAGES: Record<UIMode, AppPage> = {
  'classic': 'dashboard',
  'ai': 'ai-command-center'
};

/**
 * 根据UI模式获取对应的默认页面
 *
 * @param mode - UI模式，支持 'classic' 或 'ai'
 * @returns 对应模式的默认页面，如果模式不存在则返回DEFAULT_PAGE
 */
export function getDefaultPageForMode(mode: UIMode): AppPage {
  return MODE_DEFAULT_PAGES[mode] || DEFAULT_PAGE;
}

/**
 * 验证给定的模式字符串是否为有效的 UI 模式
 *
 * @param mode - 待验证的模式字符串
 * @returns 如果模式是 'classic' 或 'ai' 则返回 true，否则返回 false
 */
export function isValidUIMode(mode: string): mode is UIMode {
  return mode === 'classic' || mode === 'ai';
}

export function getUIModeFromString(mode: string): UIMode {
  return isValidUIMode(mode) ? mode : 'classic';
}
