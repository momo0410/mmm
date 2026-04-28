/**
 * IconPark Icon Mapping System
 * Maps emoji characters to IconPark icon names for consistent UI replacement
 */

// IconPark icon name mappings for emojis
export const EMOJI_TO_ICONPARK_MAP: Record<string, string> = {
  // Navigation & Menu Icons
  '📊': 'ChartHistogramOne',        // Dashboard/Charts
  '🖥️': 'Computer',                // System information
  '🔧': 'Tool',                     // Remote operations/tools
  '🐳': 'Whale',                    // Docker (using whale icon)
  '🚨': 'Alarm',                    // Emergency commands
  '⚙️': 'SettingTwo',               // Settings

  // Connection & Status Icons
  '🔗': 'LinkOne',                  // Connection/linking
  '🟢': 'CheckOne',                 // Connected status (green)
  '🔴': 'CloseOne',                 // Disconnected status (red)
  '⚪': 'RadioOne',                 // Neutral status (white)
  '⚫': 'RadioOne',                 // Offline status (black)

  // File & Data Management
  '📁': 'Folder',                   // File folders
  '📂': 'FolderOpen',               // Open folders/extract
  '📦': 'Box',                      // Package/compress
  '💾': 'Save',                     // Download/save
  '📤': 'Upload',                   // Upload operations
  '📋': 'Clipboard',                // Copy operations/lists

  // System & Process Icons
  '💻': 'LaptopComputer',           // Terminal/computer
  '🐚': 'Terminal',                 // Terminal/shell
  '👥': 'Peoples',                  // Users/user management
  '🌐': 'Global',                   // Network/global connections
  '📈': 'TrendTwo',                 // Resource usage/performance
  '🚀': 'Rocket',                   // Autostart services

  // Action & Control Icons
  '🔄': 'Refresh',                  // Refresh/reload
  '➕': 'Plus',                     // Add/create
  '🗑️': 'Delete',                  // Delete operations
  '✏️': 'Edit',                     // Edit operations
  '📝': 'EditName',                 // Text/memo operations
  '🔎': 'Search',                   // Search/magnify
  '🔐': 'Lock',                     // Permissions/security
  '🏠': 'Home',                     // Home/root directory

  // Authentication & Security
  '🔑': 'KeyTwo',                   // Password authentication
  '🗝️': 'KeyOne',                  // SSH key authentication

  // Status & Information Icons
  'ℹ️': 'Info',                    // Information
  '🚧': 'Construction',             // Under development
};

// Color mappings for status icons
export const ICON_COLOR_MAP: Record<string, string> = {
  // Status colors
  '🟢': '#22c55e',  // Green for connected
  '🔴': '#ef4444',  // Red for disconnected
  '⚪': '#9ca3af',  // Gray for neutral
  '⚫': '#374151',  // Dark gray for offline
  
  // Default colors for other icons
  'default': 'currentColor',
  'primary': 'var(--primary-color)',
  'secondary': 'var(--text-secondary)',
  'success': 'var(--success-color)',
  'warning': 'var(--warning-color)',
  'error': 'var(--error-color)',
};

// Default icon sizes
export const ICON_SIZES = {
  small: 14,
  medium: 16,
  large: 20,
  xlarge: 24,
  xxlarge: 32,
  huge: 48,
} as const;

export type IconSize = keyof typeof ICON_SIZES;

/**
 * Get IconPark icon name from emoji
 */
export function getIconFromEmoji(emoji: string): string {
  return EMOJI_TO_ICONPARK_MAP[emoji] || 'help';
}

/**
 * Get appropriate color for an emoji/icon
 */
export function getIconColor(emoji: string, customColor?: string): string {
  if (customColor) return customColor;
  return ICON_COLOR_MAP[emoji] || ICON_COLOR_MAP.default;
}

/**
 * Get icon size in pixels
 */
export function getIconSize(size: IconSize | number): number {
  if (typeof size === 'number') return size;
  return ICON_SIZES[size];
}

/**
 * Generate IconPark component props from emoji
 */
export function getIconProps(
  emoji: string, 
  options: {
    size?: IconSize | number;
    color?: string;
    theme?: 'outline' | 'filled' | 'two-tone' | 'multi-color';
    strokeWidth?: number;
  } = {}
) {
  const {
    size = 'medium',
    color,
    theme = 'outline',
    strokeWidth = 2
  } = options;

  return {
    name: getIconFromEmoji(emoji),
    size: getIconSize(size),
    fill: getIconColor(emoji, color),
    theme,
    strokeWidth,
  };
}

/**
 * Create HTML string for IconPark icon (for use in template strings)
 */
export function createIconHTML(
  emoji: string,
  options: {
    size?: IconSize | number;
    color?: string;
    theme?: 'outline' | 'filled' | 'two-tone' | 'multi-color';
    strokeWidth?: number;
    className?: string;
  } = {}
): string {
  const iconName = getIconFromEmoji(emoji);
  const size = getIconSize(options.size || 'medium');
  const color = getIconColor(emoji, options.color);
  const theme = options.theme || 'outline';
  const strokeWidth = options.strokeWidth || 2;
  const className = options.className ? ` class="${options.className}"` : '';

  // Create a simple SVG icon placeholder that can be easily replaced
  return `<span${className} style="display: inline-flex; align-items: center; width: ${size}px; height: ${size}px; color: ${color};" data-icon="${iconName}" data-emoji="${emoji}" title="${emoji}">
    <svg width="${size}" height="${size}" viewBox="0 0 48 48" fill="none" xmlns="http://www.w3.org/2000/svg">
      <circle cx="24" cy="24" r="20" stroke="currentColor" stroke-width="${strokeWidth}" fill="${theme === 'filled' ? 'currentColor' : 'none'}"/>
      <text x="24" y="28" text-anchor="middle" font-size="16" fill="currentColor">${emoji}</text>
    </svg>
  </span>`;
}

/**
 * Batch replace emojis in a template string with IconPark icons
 */
export function replaceEmojisInTemplate(
  template: string,
  defaultOptions: {
    size?: IconSize | number;
    theme?: 'outline' | 'filled' | 'two-tone' | 'multi-color';
    strokeWidth?: number;
  } = {}
): string {
  let result = template;
  
  // Replace each emoji with its IconPark equivalent
  Object.keys(EMOJI_TO_ICONPARK_MAP).forEach(emoji => {
    const regex = new RegExp(emoji.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'g');
    result = result.replace(regex, createIconHTML(emoji, defaultOptions));
  });
  
  return result;
}
