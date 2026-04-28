function notifyUnavailable() {
  console.warn('ServiceContextMenu implementation is missing; skipping context menu rendering.');
  (window as any).showNotification?.('服务右键菜单暂不可用', 'warning');
}

export class ServiceContextMenu {
  showContextMenu(..._args: any[]) {
    notifyUnavailable();
  }
}
