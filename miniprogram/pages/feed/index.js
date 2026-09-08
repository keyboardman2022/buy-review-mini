const { request, absoluteMediaUrl } = require('/utils/api');
const { decorateItem } = require('/utils/format');
Page({
  data: { items: [], loading: true, error: '' },
  onShow() { if (getApp().ensureSession()) this.load(); },
  onPullDownRefresh() { this.load().finally(() => wx.stopPullDownRefresh()); },
  async load() {
    this.setData({ loading: true, error: '' });
    try {
      const { items } = await request('/api/items?scope=feed');
      this.setData({ items: items.map((item) => decorateItem(item, absoluteMediaUrl)) });
    } catch (error) { this.setData({ error: error.message }); }
    finally { this.setData({ loading: false }); }
  },
  openItem(event) { wx.navigateTo({ url: `/pages/item-detail/index?id=${event.currentTarget.dataset.id}` }); },
  async react(event) {
    const { id, value } = event.currentTarget.dataset;
    const item = this.data.items.find((entry) => entry.id === id);
    if (!item || item.reacting) return;
    const next = item.myReaction === Number(value) ? 0 : Number(value);
    this.setData({ items: this.data.items.map((entry) => entry.id === id ? { ...entry, reacting: true } : entry), error: '' });
    try { await request(`/api/items/${id}/reaction`, { method: 'POST', data: { value: next } }); await this.load(); }
    catch (error) { this.setData({ error: error.message, items: this.data.items.map((entry) => ({ ...entry, reacting: false })) }); }
  },
});
