function notifyUnavailable() {
  console.warn('StartupContextMenu implementation is missing; skipping context menu rendering.');
  (window as any).showNotification?.('启动项右键菜单暂不可用', 'warning');
}

export class StartupContextMenu {
  showContextMenu(..._args: any[]) {
    notifyUnavailable();
  }
}
