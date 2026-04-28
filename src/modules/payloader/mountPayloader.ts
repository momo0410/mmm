import { createApp, type App } from 'vue';
import PayloaderPage from './PayloaderPage.vue';
import './styles/payloader.css';

let appInstance: App | null = null;

export function mountPayloader(containerId: string = 'payloader-vue-root') {
  const container = document.getElementById(containerId);
  if (!container) {
    console.error(`Payloader: 容器 #${containerId} 未找到`);
    return null;
  }

  try {
    if (appInstance) {
      console.warn('⚠️ Payloader 已存在实例，先卸载');
      appInstance.unmount();
      appInstance = null;
    }
    
    appInstance = createApp(PayloaderPage);
    appInstance.mount(container);
    console.log('✅ Payloader 模块已挂载');
    return appInstance;
  } catch (error) {
    console.error('❌ Payloader 挂载失败:', error);
    return null;
  }
}

export function unmountPayloader() {
  if (!appInstance) {
    console.warn('⚠️ Payloader 未挂载，跳过卸载');
    return;
  }

  try {
    appInstance.unmount();
    appInstance = null;
    console.log('🧹 Payloader 模块已卸载');
  } catch (error) {
    console.error('❌ Payloader 卸载失败:', error);
  }
}
