function notifyUnavailable() {
  console.warn('CronContextMenu implementation is missing; skipping context menu rendering.');
  (window as any).showNotification?.('计划任务右键菜单暂不可用', 'warning');
}

export class CronContextMenu {
  showContextMenu(..._args: any[]) {
    notifyUnavailable();
  }
}
