const { request, absoluteMediaUrl } = require('../../utils/api');
const { decorateItem } = require('../../utils/format');
Page({
  data: { items: [], loading: true, error: '', deletingId: '' },
  onShow() { if (getApp().ensureSession()) this.load(); },
  onPullDownRefresh() { this.load().finally(() => wx.stopPullDownRefresh()); },
  async load() {
    this.setData({ loading: true, error: '' });
    try { const { items } = await request('/api/items?scope=mine'); this.setData({ items: items.map((item) => decorateItem(item, absoluteMediaUrl)) }); }
    catch (error) { this.setData({ error: error.message }); }
    finally { this.setData({ loading: false }); }
  },
  createItem() { wx.navigateTo({ url: '/miniprogram/pages/compose/index' }); },
  openItem(event) { wx.navigateTo({ url: `/miniprogram/pages/item-detail/index?id=${event.currentTarget.dataset.id}` }); },
  editItem(event) { wx.navigateTo({ url: `/miniprogram/pages/compose/index?id=${event.currentTarget.dataset.id}` }); },
  deleteItem(event) {
    const id = event.currentTarget.dataset.id;
    if (this.data.deletingId) return;
    wx.showModal({ title: '移出购物车？', content: '已有审批会保留创建时的商品快照。', confirmColor: '#D95F45', success: async ({ confirm }) => {
      if (!confirm) return;
      this.setData({ deletingId: id, error: '' });
      try { await request(`/api/items/${id}`, { method: 'DELETE' }); await this.load(); }
      catch (error) { this.setData({ error: error.message }); }
      finally { this.setData({ deletingId: '' }); }
    } });
  },
});
