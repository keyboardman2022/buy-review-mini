const { request } = require('../../utils/api');

Page({
  data: { invite: '', friends: [], incoming: [], outgoing: [], loading: true, submitting: false, error: '' },
  onLoad(options) { this.setData({ invite: (options.invite || '').toUpperCase() }); if (getApp().ensureSession()) this.load(); },
  onPullDownRefresh() { this.load().finally(() => wx.stopPullDownRefresh()); },
  inputInvite(event) { this.setData({ invite: event.detail.value.toUpperCase(), error: '' }); },
  async load() { this.setData({ loading: true, error: '' }); try { this.setData(await request('/api/friends')); } catch (error) { this.setData({ error: error.message }); } finally { this.setData({ loading: false }); } },
  async addFriend() { if (this.data.submitting) return; if (!this.data.invite.trim()) { this.setData({ error: '请输入好友邀请码' }); return; } this.setData({ submitting: true, error: '' }); try { await request('/api/friends/request', { method: 'POST', data: { code: this.data.invite.trim() } }); this.setData({ invite: '' }); await this.load(); wx.showToast({ title: '申请已发出', icon: 'success' }); } catch (error) { this.setData({ error: error.message }); } finally { this.setData({ submitting: false }); } },
  async respond(event) { if (this.data.submitting) return; this.setData({ submitting: true, error: '' }); try { await request(`/api/friends/${event.currentTarget.dataset.id}/respond`, { method: 'POST', data: { accept: event.currentTarget.dataset.accept === 'true' } }); await this.load(); } catch (error) { this.setData({ error: error.message }); } finally { this.setData({ submitting: false }); } },
  remove(event) { const id = event.currentTarget.dataset.id; wx.showModal({ title: '移除这位好友？', content: '移除后将看不到彼此新的购物内容，也不能继续审批。', confirmColor: '#D95F45', success: async ({ confirm }) => { if (!confirm) return; try { await request(`/api/friends/${id}`, { method: 'DELETE' }); await this.load(); } catch (error) { this.setData({ error: error.message }); } } }); },
});
