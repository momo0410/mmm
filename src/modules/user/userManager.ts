/**
 * 用户管理器
 * 负责用户认证、状态管理和用户信息存储
 */

import { apiService, ApiUser } from '../api/apiService';
import { EventEmitter } from '../utils/EventEmitter';

export interface UserInfo {
  id: string;
  username: string;
  nickname?: string;
  email: string;
  qq_id?: string;
  isVip: boolean;
  vipDays: number;
  vipExpireDate?: string; // VIP 过期日期，用于重新计算剩余天数
  avatar?: string;
  maxDevices: number;
  deviceRebindCount: number;
  maxRebindCount: number;
}

export class UserManager extends EventEmitter<UserInfo | null> {
  private static instance: UserManager;
  private currentUser: UserInfo | null = null;

  private constructor() {
    super();
    this.loadUserFromStorage();
  }

  /**
   * 获取单例实例
   */
  public static getInstance(): UserManager {
    if (!UserManager.instance) {
      UserManager.instance = new UserManager();
    }
    return UserManager.instance;
  }

  /**
   * 从本地存储加载用户信息
   */
  private loadUserFromStorage(): void {
    try {
      const savedUser = localStorage.getItem('LERT-user-info');
      if (savedUser) {
        this.currentUser = JSON.parse(savedUser);
        console.log('✅ 用户信息加载成功:', this.currentUser?.username);

        // 如果是旧数据（没有 vipDays 或 vipDays 为 0），尝试计算
        if (this.currentUser && this.currentUser.isVip && this.currentUser.vipExpireDate) {
          if (!this.currentUser.vipDays || this.currentUser.vipDays === 0) {
            const expireDate = new Date(this.currentUser.vipExpireDate);
            const now = new Date();
            const diffTime = expireDate.getTime() - now.getTime();
            const calculatedDays = Math.max(0, Math.ceil(diffTime / (1000 * 60 * 60 * 24)));

            if (calculatedDays > 0) {
              console.log(`📅 重新计算 VIP 剩余天数: ${calculatedDays} 天`);
              this.currentUser.vipDays = calculatedDays;
              this.saveUserToStorage();
            }
          }
        }

        // 如果有 Token，立即从服务器获取最新用户信息
        if (apiService.hasToken()) {
          this.refreshUserInfo().catch(err => {
            console.warn('⚠️ 刷新用户信息失败:', err);
          });
        }

        // 启动定期刷新（每5分钟刷新一次）
        this.startAutoRefresh();
      }
    } catch (error) {
      console.error('❌ 加载用户信息失败:', error);
      this.currentUser = null;
    }
  }

  /**
   * 从服务器刷新用户信息
   */
  private async refreshUserInfo(): Promise<void> {
    try {
      const apiUser = await apiService.getCurrentUser();
      this.currentUser = this.convertApiUserToUserInfo(apiUser);
      this.saveUserToStorage();
      this.notifyListeners();
    } catch (error) {
      console.error('❌ 刷新用户信息失败:', error);
      
      // 检查是否为认证错误
      const errorMessage = error instanceof Error ? error.message : String(error);
      if (errorMessage.includes('认证令牌无效') || 
          errorMessage.includes('401') || 
          errorMessage.includes('Unauthorized') ||
          errorMessage.includes('Token 刷新失败')) {
        console.warn('⚠️ 认证失效，自动登出...');
        this.logout();
      }
      
      throw error;
    }
  }

  /**
   * 将 API 用户信息转换为本地用户信息
   */
  private convertApiUserToUserInfo(apiUser: ApiUser): UserInfo {
    // 优先使用服务端计算的 VIP 剩余天数
    let vipDays = apiUser.vip_days || 0;

    // 如果服务端没有返回 vip_days（旧版本 API），在前端计算作为后备
    if (!apiUser.vip_days && apiUser.is_vip && apiUser.vip_expire_date) {
      const expireDate = new Date(apiUser.vip_expire_date);
      const now = new Date();
      const diffTime = expireDate.getTime() - now.getTime();
      vipDays = Math.max(0, Math.ceil(diffTime / (1000 * 60 * 60 * 24)));
      console.warn('⚠️ 服务端未返回 vip_days，使用前端计算（建议重启后端服务器）');
    }

    // 生成头像 URL
    let avatar: string | undefined;
    if (apiUser.qq_id) {
      avatar = apiService.getQQAvatarUrl(apiUser.qq_id, 100);
    }

    return {
      id: apiUser.id,
      username: apiUser.username,
      nickname: apiUser.nickname,
      email: apiUser.email,
      qq_id: apiUser.qq_id,
      isVip: apiUser.is_vip,
      vipDays,
      vipExpireDate: apiUser.vip_expire_date, // 保存过期日期以便显示
      avatar,
      maxDevices: apiUser.max_devices,
      deviceRebindCount: apiUser.device_rebind_count,
      maxRebindCount: apiUser.max_rebind_count,
    };
  }

  /**
   * 自动刷新定时器
   */
  private autoRefreshTimer: number | null = null;

  /**
   * 启动自动刷新（每5分钟刷新一次）
   */
  private startAutoRefresh(): void {
    // 清除已有的定时器
    if (this.autoRefreshTimer !== null) {
      clearInterval(this.autoRefreshTimer);
    }

    // 每5分钟从服务器刷新一次用户信息
    this.autoRefreshTimer = window.setInterval(() => {
      if (apiService.hasToken()) {
        this.refreshUserInfo().catch(err => {
          console.warn('⚠️ 自动刷新用户信息失败:', err);
        });
      }
    }, 5 * 60 * 1000); // 5分钟
  }

  /**
   * 停止自动刷新
   */
  private stopAutoRefresh(): void {
    if (this.autoRefreshTimer !== null) {
      clearInterval(this.autoRefreshTimer);
      this.autoRefreshTimer = null;
    }
  }

  /**
   * 保存用户信息到本地存储
   */
  private saveUserToStorage(): void {
    try {
      if (this.currentUser) {
        localStorage.setItem('LERT-user-info', JSON.stringify(this.currentUser));
      } else {
        localStorage.removeItem('LERT-user-info');
      }
    } catch (error) {
      console.error('❌ 保存用户信息失败:', error);
    }
  }

  /**
   * 检查是否已登录
   */
  public isLoggedIn(): boolean {
    return this.currentUser !== null;
  }

  /**
   * 获取当前用户信息
   */
  public getCurrentUser(): UserInfo | null {
    // 直接返回当前用户信息，不在前端重新计算
    // VIP 天数由服务端计算，通过定期刷新保持最新
    return this.currentUser ? { ...this.currentUser } : null;
  }

  /**
   * 登录
   * @param username 用户名或邮箱
   * @param password 密码
   * @returns 登录是否成功
   */
  public async login(username: string, password: string): Promise<{ success: boolean; message: string }> {
    try {
      console.log('🔐 尝试登录:', username);

      // 调用后端 API 登录
      const response = await apiService.login({
        username,
        password,
      });

      // 转换并保存用户信息
      this.currentUser = this.convertApiUserToUserInfo(response.user);
      this.saveUserToStorage();

      // 通知监听器
      this.notifyListeners();

      // 启动自动刷新
      this.startAutoRefresh();

      console.log('✅ 登录成功:', this.currentUser.username);

      return {
        success: true,
        message: '登录成功'
      };
    } catch (error) {
      console.error('❌ 登录失败:', error);
      return {
        success: false,
        message: error instanceof Error ? error.message : '登录失败'
      };
    }
  }

  /**
   * 注册
   * @param username 用户名
   * @param email 邮箱
   * @param password 密码
   * @param nickname 昵称（可选）
   * @param qqId QQ号（可选）
   * @returns 注册是否成功
   */
  public async register(
    username: string,
    email: string,
    password: string,
    nickname?: string,
    qqId?: string
  ): Promise<{ success: boolean; message: string }> {
    try {
      console.log('📝 尝试注册:', username, email);

      // 调用后端 API 注册
      const response = await apiService.register({
        username,
        email,
        password,
        nickname,
        qq_id: qqId,
      });

      // 转换并保存用户信息
      this.currentUser = this.convertApiUserToUserInfo(response.user);
      this.saveUserToStorage();

      // 通知监听器
      this.notifyListeners();

      // 启动自动刷新
      this.startAutoRefresh();

      console.log('✅ 注册成功:', this.currentUser.username);

      return {
        success: true,
        message: '注册成功'
      };
    } catch (error) {
      console.error('❌ 注册失败:', error);
      return {
        success: false,
        message: error instanceof Error ? error.message : '注册失败'
      };
    }
  }

  /**
   * 登出
   */
  public async logout(): Promise<{ success: boolean; message: string }> {
    console.log('👋 用户登出:', this.currentUser?.username);

    // 停止自动刷新
    this.stopAutoRefresh();

    // 调用后端 API 登出
    try {
      await apiService.logout();
    } catch (error) {
      console.error('❌ 登出 API 调用失败:', error);
      // 即使 API 调用失败，也继续清除本地信息
    }

    // 清除本地用户信息
    this.currentUser = null;
    this.saveUserToStorage();
    this.notifyListeners();

    return { success: true, message: '登出成功' };
  }

  /**
   * 更新用户信息
   */
  public updateUserInfo(updates: Partial<UserInfo>): void {
    if (this.currentUser) {
      this.currentUser = { ...this.currentUser, ...updates };
      this.saveUserToStorage();
      this.notifyListeners();
    }
  }

  private notifyListeners(): void {
    this.emit(this.getCurrentUser());
  }
}

// 导出单例实例
export const userManager = UserManager.getInstance();

