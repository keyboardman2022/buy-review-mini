const { request } = require('../../utils/api');
const { money } = require('../../utils/format');
Page({
  data: { items: [], friends: [], itemId: '', selectedIds: [], rule: 'veto', loading: true, submitting: false, error: '' },
  onLoad(options) { this.setData({ itemId: options.itemId || '' }); },
  onShow() { if (getApp().ensureSession()) this.load(); },
  addItem() { wx.navigateTo({ url: '/miniprogram/pages/compose/index' }); },
  inviteFriends() { wx.navigateTo({ url: '/miniprogram/pages/friends/index' }); },
  async load() { this.setData({ loading: true, error: '' }); try { const [itemsData, friendsData] = await Promise.all([request('/api/items?scope=mine'), request('/api/friends')]); this.setData({ items: itemsData.items.map((item) => ({ ...item, priceText: money(item.price) })), friends: friendsData.friends.map((friend) => ({ ...friend, selected: this.data.selectedIds.includes(friend.id) })) }); } catch (error) { this.setData({ error: error.message }); } finally { this.setData({ loading: false }); } },
  chooseItem(event) { this.setData({ itemId: event.currentTarget.dataset.id, error: '' }); },
  chooseRule(event) { this.setData({ rule: event.currentTarget.dataset.rule }); },
  toggleReviewer(event) { const id = event.currentTarget.dataset.id; const selected = this.data.selectedIds.includes(id); if (!selected && this.data.selectedIds.length >= 10) { this.setData({ error: '最多选择10位好友' }); return; } const selectedIds = selected ? this.data.selectedIds.filter((value) => value !== id) : [...this.data.selectedIds, id]; this.setData({ selectedIds, friends: (this.data.friends || []).map((friend) => ({ ...friend, selected: selectedIds.includes(friend.id) })), error: '' }); },
  async submit() { if (this.data.submitting) return; if (!this.data.itemId) { this.setData({ error: '请选择要审批的商品' }); return; } if (!this.data.selectedIds.length) { this.setData({ error: '请至少选择1位好友' }); return; } this.setData({ submitting: true, error: '' }); try { const { approval } = await request('/api/approvals', { method: 'POST', data: { itemId: this.data.itemId, reviewerIds: this.data.selectedIds, rule: this.data.rule } }); wx.redirectTo({ url: `/miniprogram/pages/approval-detail/index?id=${approval.id}` }); } catch (error) { this.setData({ error: error.message }); } finally { this.setData({ submitting: false }); } },
});
