const { request, absoluteMediaUrl } = require('../../utils/api');
const { decorateItem } = require('../../utils/format');
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
  openItem(event) { wx.navigateTo({ url: `/miniprogram/pages/item-detail/index?id=${event.currentTarget.dataset.id}` }); },
  inviteFriends() { wx.navigateTo({ url: '/miniprogram/pages/friends/index' }); },
  previewPhotos(event) {
    const item = this.data.items.find((entry) => entry.id === event.currentTarget.dataset.id);
    if (item) wx.previewImage({ urls: item.photos, current: item.photos[Number(event.currentTarget.dataset.index)] });
  },
  async react(event) {
    const { id, value } = event.currentTarget.dataset;
    const item = this.data.items.find((entry) => entry.id === id);
    if (!item || item.reacting) return;
    const next = item.myReaction === Number(value) ? 0 : Number(value);
    this.setData({ items: this.data.items.map((entry) => entry.id === id ? { ...entry, reacting: true } : entry), error: '' });
    try {
      await request(`/api/items/${id}/reaction`, { method: 'POST', data: { value: next } });
      this.setData({ items: this.data.items.map((entry) => entry.id === id ? {
        ...entry, reacting: false, myReaction: next,
        likes: entry.likes + Number(next === 1) - Number(item.myReaction === 1),
        dislikes: entry.dislikes + Number(next === -1) - Number(item.myReaction === -1),
      } : entry) });
    }
    catch (error) { this.setData({ error: error.message, items: this.data.items.map((entry) => ({ ...entry, reacting: false })) }); }
  },
});
