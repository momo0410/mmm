function notifyUnavailable() {
  console.warn('NetworkContextMenu implementation is missing; skipping context menu rendering.');
  (window as any).showNotification?.('网络连接右键菜单暂不可用', 'warning');
}

export class NetworkContextMenu {
  showContextMenu(..._args: any[]) {
    notifyUnavailable();
  }
}
