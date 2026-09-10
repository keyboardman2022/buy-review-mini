const { request, absoluteMediaUrl } = require('../../utils/api');
const { decorateItem, dateTime } = require('../../utils/format');
Page({
  data: { id: '', item: null, comments: [], comment: '', loading: true, submitting: false, reacting: false, error: '', isOwner: false },
  onLoad(options) { this.setData({ id: options.id || '' }); if (getApp().ensureSession()) this.load(); },
  onPullDownRefresh() { this.load().finally(() => wx.stopPullDownRefresh()); },
  async load() { this.setData({ loading: true, error: '' }); try { const { item, comments } = await request(`/api/items/${this.data.id}`); const user = getApp().globalData.user; const isOwner = Boolean(user && user.id === item.ownerId); this.setData({ item: decorateItem(item, absoluteMediaUrl), comments: comments.map((entry) => ({ ...entry, createdText: dateTime(entry.createdAt), canDelete: isOwner || Boolean(user && user.id === entry.user.id) })), isOwner }); } catch (error) { this.setData({ error: error.message }); } finally { this.setData({ loading: false }); } },
  inputComment(event) { this.setData({ comment: event.detail.value, error: '' }); },
  previewPhotos(event) { wx.previewImage({ urls: this.data.item.photos, current: this.data.item.photos[Number(event.currentTarget.dataset.index)] }); },
  copyLink() { wx.setClipboardData({ data: this.data.item.link }); },
  async submitComment() { if (this.data.submitting) return; const text = this.data.comment.trim(); if (!text) { this.setData({ error: '请输入评论内容' }); return; } this.setData({ submitting: true }); try { await request(`/api/items/${this.data.id}/comments`, { method: 'POST', data: { text } }); this.setData({ comment: '' }); await this.load(); } catch (error) { this.setData({ error: error.message }); } finally { this.setData({ submitting: false }); } },
  deleteComment(event) { const id = event.currentTarget.dataset.id; wx.showModal({ title: '删除这条评论？', success: async ({ confirm }) => { if (!confirm) return; try { await request(`/api/comments/${id}`, { method: 'DELETE' }); await this.load(); } catch (error) { this.setData({ error: error.message }); } } }); },
  async react(event) {
    if (this.data.reacting) return;
    const item = this.data.item;
    const value = Number(event.currentTarget.dataset.value);
    const next = item.myReaction === value ? 0 : value;
    this.setData({ reacting: true, error: '' });
    try {
      await request(`/api/items/${this.data.id}/reaction`, { method: 'POST', data: { value: next } });
      this.setData({ item: { ...this.data.item, myReaction: next,
        likes: item.likes + Number(next === 1) - Number(item.myReaction === 1),
        dislikes: item.dislikes + Number(next === -1) - Number(item.myReaction === -1) } });
    } catch (error) { this.setData({ error: error.message }); }
    finally { this.setData({ reacting: false }); }
  },
  editItem() { wx.navigateTo({ url: `/miniprogram/pages/compose/index?id=${this.data.id}` }); },
  createApproval() { wx.navigateTo({ url: `/miniprogram/pages/approval-create/index?itemId=${this.data.id}` }); },
  deleteItem() { wx.showModal({ title: '移出购物车？', content: '此操作不会删除已有审批快照。', confirmColor: '#D95F45', success: async ({ confirm }) => { if (!confirm) return; try { await request(`/api/items/${this.data.id}`, { method: 'DELETE' }); wx.switchTab({ url: '/miniprogram/pages/cart/index' }); } catch (error) { this.setData({ error: error.message }); } } }); },
});
