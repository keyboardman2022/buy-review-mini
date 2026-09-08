const { request, uploadImage, absoluteMediaUrl } = require('../../utils/api');
const { yuanToCents } = require('../../utils/format');
Page({
  data: { id: '', title: '', price: '', reason: '', category: '', link: '', visibility: 'friends', images: [], previews: [], uploading: false, submitting: false, loading: false, error: '' },
  onLoad(options) { if (!getApp().ensureSession()) return; if (options.id) { this.setData({ id: options.id }); this.loadItem(); } },
  async loadItem() {
    this.setData({ loading: true });
    try { const { item } = await request(`/api/items/${this.data.id}`); this.setData({ title: item.title, price: (item.price / 100).toFixed(2), reason: item.reason || '', category: item.category || '', link: item.link || '', visibility: item.visibility, images: item.images || [], previews: (item.imageUrls || []).map(absoluteMediaUrl) }); }
    catch (error) { this.setData({ error: error.message }); }
    finally { this.setData({ loading: false }); }
  },
  inputField(event) { this.setData({ [event.currentTarget.dataset.field]: event.detail.value, error: '' }); },
  chooseVisibility(event) { this.setData({ visibility: event.currentTarget.dataset.value }); },
  chooseImages() {
    if (this.data.uploading || this.data.images.length >= 3) return;
    wx.chooseMedia({ count: 3 - this.data.images.length, mediaType: ['image'], sourceType: ['album', 'camera'], success: async ({ tempFiles }) => {
      this.setData({ uploading: true, error: '' });
      try {
        for (const file of tempFiles) {
          if (file.size > 3 * 1024 * 1024) throw new Error('单张图片不能超过3MB');
          const media = await uploadImage(file.tempFilePath);
          this.setData({ images: [...this.data.images, media.id], previews: [...this.data.previews, absoluteMediaUrl(media.url)] });
        }
      } catch (error) { this.setData({ error: error.message }); }
      finally { this.setData({ uploading: false }); }
    } });
  },
  removeImage(event) { const index = Number(event.currentTarget.dataset.index); this.setData({ images: this.data.images.filter((_, i) => i !== index), previews: this.data.previews.filter((_, i) => i !== index) }); },
  async submit() {
    if (this.data.submitting || this.data.uploading) return;
    const price = yuanToCents(this.data.price);
    if (!this.data.title.trim()) { this.setData({ error: '请填写商品名称' }); return; }
    if (price === null) { this.setData({ error: '请输入正确价格，最多两位小数' }); return; }
    if (!this.data.reason.trim()) { this.setData({ error: '请写下为什么想买' }); return; }
    this.setData({ submitting: true, error: '' });
    const data = { title: this.data.title.trim(), price, reason: this.data.reason.trim(), category: this.data.category.trim(), link: this.data.link.trim(), visibility: this.data.visibility, images: this.data.images };
    try { await request(this.data.id ? `/api/items/${this.data.id}` : '/api/items', { method: this.data.id ? 'PATCH' : 'POST', data }); wx.showToast({ title: this.data.id ? '已保存' : '已加入购物车' }); setTimeout(() => wx.navigateBack(), 400); }
    catch (error) { this.setData({ error: error.message }); }
    finally { this.setData({ submitting: false }); }
  },
});
