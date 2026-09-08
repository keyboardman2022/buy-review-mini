const { request } = require('../../utils/api');
Page({
  data: { user: null, stats: {}, mode: '', smsProvider: '', editing: false, name: '', loading: true, error: '' },
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
  async bindPhone(event) {
    const code = event.detail && event.detail.code;
    if (!code) { this.setData({ error: '你取消了手机号授权，短信提醒暂未开启' }); return; }
    try { const { user } = await request('/api/me/phone', { method: 'POST', data: { code } }); getApp().globalData.user = user; this.setData({ user, error: '' }); wx.showToast({ title: '短信提醒已开启', icon: 'success' }); }
    catch (error) { this.setData({ error: error.message }); }
  },
  openFriends() { wx.navigateTo({ url: '/miniprogram/pages/friends/index' }); },
  openMessages() { wx.navigateTo({ url: '/miniprogram/pages/messages/index' }); },
  onShareAppMessage() { return { title: `${this.data.user.name} 邀请你加入买前问问`, path: `/miniprogram/pages/login/index?invite=${encodeURIComponent(this.data.user.code)}` }; },
});
