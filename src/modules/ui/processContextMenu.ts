function notifyUnavailable() {
  console.warn('ProcessContextMenu implementation is missing; skipping context menu rendering.');
  (window as any).showNotification?.('进程右键菜单暂不可用', 'warning');
}

export class ProcessContextMenu {
  showContextMenu(..._args: any[]) {
    notifyUnavailable();
  }
}
