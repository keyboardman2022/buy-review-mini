const { request, absoluteMediaUrl } = require('../../utils/api');
const { decorateApproval } = require('../../utils/approval');
const { createShareCard } = require('../../utils/share-card');

Page({
  data: { id: '', approval: null, comment: '', loading: true, submitting: false, error: '', isOwner: false, canVote: false, shareImage: '' },
  onLoad(options) {
    const id = options.id || '';
    this.setData({ id });
    if (!id) { this.setData({ loading: false, error: '审批链接无效' }); return; }
    if (getApp().ensureSession({ approvalId: id })) this.load();
  },
  onPullDownRefresh() { this.load().finally(() => wx.stopPullDownRefresh()); },
  async load() {
    if (!this.data.id) { this.setData({ loading: false, error: '审批链接无效' }); return; }
    this.setData({ loading: true, error: '' });
    try {
      const app = getApp();
      let user = app.globalData.user;
      const [{ approval }, profile] = await Promise.all([
        request(`/api/approvals/${this.data.id}`),
        user ? Promise.resolve(null) : request('/api/me'),
      ]);
      if (profile) { user = profile.user; app.globalData.user = user; }
      const mine = user && approval.reviewers.find((entry) => entry.user.id === user.id);
      this.setData({
        approval: decorateApproval(approval, absoluteMediaUrl),
        isOwner: Boolean(user && user.id === approval.ownerId),
        canVote: Boolean(mine && !mine.decision && approval.status === 'pending'),
      });
      this.prepareShareCard();
    } catch (error) {
      if (error.statusCode === 401) { getApp().ensureSession({ approvalId: this.data.id }); return; }
      this.setData({ error: error.message });
    }
    finally { this.setData({ loading: false }); }
  },
  inputComment(event) { this.setData({ comment: event.detail.value, error: '' }); },
  previewPhotos(event) { const urls = this.data.approval.photos; wx.previewImage({ urls, current: urls[Number(event.currentTarget.dataset.index)] }); },
  focusVote() { wx.pageScrollTo({ selector: '#vote-form', duration: 200 }); },
  prepareShareCard() {
    const version = this.shareVersion = (this.shareVersion || 0) + 1;
    this.setData({ shareImage: '' });
    createShareCard(this, this.data.approval).then((shareImage) => {
      if (version === this.shareVersion) this.setData({ shareImage });
    }).catch(() => {});
  },
  onUnload() { this.shareVersion = (this.shareVersion || 0) + 1; },
  async submitVote(event) {
    if (this.data.submitting) return;
    const comment = (this.data.comment || '').trim();
    if (!comment) { this.setData({ error: '请填写审批意见' }); return; }
    const decision = event.currentTarget.dataset.decision;
    this.setData({ submitting: true, error: '' });
    try {
      await request(`/api/approvals/${this.data.id}/vote`, { method: 'POST', data: { decision, comment } });
      this.setData({ comment: '' });
      await this.load();
      wx.showToast({ title: '意见已提交', icon: 'success' });
    } catch (error) { this.setData({ error: error.message }); }
    finally { this.setData({ submitting: false }); }
  },
  cancel() {
    wx.showModal({ title: '撤回审批？', content: '好友将不能再提交意见。', confirmColor: '#D95F45', success: async ({ confirm }) => {
      if (!confirm || this.data.submitting) return;
      this.setData({ submitting: true, error: '' });
      try { await request(`/api/approvals/${this.data.id}/cancel`, { method: 'POST' }); await this.load(); }
      catch (error) { this.setData({ error: error.message }); }
      finally { this.setData({ submitting: false }); }
    } });
  },
  onShareAppMessage() {
    const approval = this.data.approval;
    return { title: approval ? `帮我拿个主意：${approval.title} ${approval.priceText || ''}`.trim() : '帮我拿个主意',
      path: `/miniprogram/pages/approval-detail/index?id=${encodeURIComponent(this.data.id)}`,
      imageUrl: this.data.shareImage || '/miniprogram/assets/share-fallback.png' };
  },
});
