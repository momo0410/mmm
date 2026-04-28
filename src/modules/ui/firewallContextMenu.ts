function notifyUnavailable() {
  console.warn('FirewallContextMenu implementation is missing; skipping context menu rendering.');
  (window as any).showNotification?.('防火墙右键菜单暂不可用', 'warning');
}

export class FirewallContextMenu {
  showContextMenu(..._args: any[]) {
    notifyUnavailable();
  }
}
