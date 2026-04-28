function notifyUnavailable() {
  console.warn('UserContextMenu implementation is missing; skipping context menu rendering.');
  (window as any).showNotification?.('用户右键菜单暂不可用', 'warning');
}

export class UserContextMenu {
  showContextMenu(..._args: any[]) {
    notifyUnavailable();
  }
}
