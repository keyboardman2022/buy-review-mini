const { request, clearSession } = require('/utils/api');
Page({
  data: { user: null, stats: {}, mode: '', smsProvider: '', editing: false, name: '', loading: true, switching: false, error: '' },
  onShow() { if (getApp().ensureSession()) this.load(); },
  onPullDownRefresh() { this.load().finally(() => wx.stopPullDownRefresh()); },
  async load() {
    this.setData({ loading: true, error: '' });
    try { const data = await request('/api/me'); getApp().globalData.user = data.user; this.setData({ ...data, name: data.user.name }); }
    catch (error) { this.setData({ error: error.message }); }
    finally { this.setData({ loading: false }); }
  },
  startEdit() { this.setData({ editing: true }); },
  inputName(event) { this.setData({ name: event.detail.value }); },
  async saveName() {
    if (!this.data.name.trim()) { this.setData({ error: '昵称不能为空' }); return; }
    try { const { user } = await request('/api/me', { method: 'PATCH', data: { name: this.data.name.trim() } }); this.setData({ user, editing: false }); }
    catch (error) { this.setData({ error: error.message }); }
  },
  openFriends() { wx.navigateTo({ url: '/pages/friends/index' }); },
  openMessages() { wx.navigateTo({ url: '/pages/messages/index' }); },
  async switchDemo(event) {
    if (this.data.switching) return;
    this.setData({ switching: true, error: '' });
    try { const result = await request('/api/auth/demo', { method: 'POST', data: { account: event.currentTarget.dataset.account } }); wx.setStorageSync('token', result.token); getApp().globalData.user = result.user; await this.load(); }
    catch (error) { this.setData({ error: error.message }); }
    finally { this.setData({ switching: false }); }
  },
  logout() {
    wx.showModal({ title: '退出登录？', content: '本机只会清除会话凭证。', success: async ({ confirm }) => { if (!confirm) return; try { await request('/api/auth/logout', { method: 'POST' }); } catch (_) {} clearSession(); wx.reLaunch({ url: '/pages/login/index' }); } });
  },
  onShareAppMessage() { return { title: `${this.data.user.name} 邀请你加入买前问问`, path: `/pages/login/index?invite=${encodeURIComponent(this.data.user.code)}` }; },
});
