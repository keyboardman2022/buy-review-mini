const { request, token } = require('../../utils/api');

Page({
  data: { loading: true, error: '' },
  onLoad(options) {
    if (options.invite) getApp().globalData.launchTarget = { invite: options.invite };
    if (options.approvalId) getApp().globalData.launchTarget = { approvalId: options.approvalId };
    if (token()) { this.resumeSession(); return; }
    this.wechatLogin();
  },
  async resumeSession() {
    try {
      const { user } = await request('/api/me');
      getApp().globalData.user = user;
      this.enterApp();
    } catch (_) { this.wechatLogin(); }
  },
  getWxCode() {
    return new Promise((resolve, reject) => wx.login({
      timeout: 10000,
      success: ({ code }) => code ? resolve(code) : reject(new Error('微信没有返回登录凭证')),
      fail: () => reject(new Error('无法连接微信登录，请检查网络后重试')),
    }));
  },
  async wechatLogin() {
    if (this.signingIn) return;
    this.signingIn = true;
    this.setData({ loading: true, error: '' });
    try {
      const code = await this.getWxCode();
      const result = await request('/api/auth/wechat', { method: 'POST', data: { code } });
      wx.setStorageSync('token', result.token);
      getApp().globalData.user = result.user;
      this.enterApp();
    } catch (error) {
      this.setData({ loading: false, error: error.message });
    } finally { this.signingIn = false; }
  },
  enterApp() {
    wx.switchTab({ url: '/miniprogram/pages/feed/index', success: () => setTimeout(() => getApp().openLaunchTarget(), 120) });
  },
});
