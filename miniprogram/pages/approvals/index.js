const { request, absoluteMediaUrl } = require('../../utils/api');
const { decorateApproval } = require('../../utils/approval');
Page({
  data: { scope: 'pending', approvals: [], pendingCount: 0, loading: true, error: '' },
  onShow() { if (getApp().ensureSession()) this.load(); },
  onPullDownRefresh() { return this.load().finally(() => wx.stopPullDownRefresh()); },
  switchScope(event) { const scope = event.currentTarget.dataset.scope; if (scope !== this.data.scope) { this.setData({ scope }); this.load(); } },
  async load() {
    const version = this.loadVersion = (this.loadVersion || 0) + 1;
    this.setData({ loading: true, error: '', approvals: [] });
    try {
      const data = await request(`/api/approvals?scope=${this.data.scope}`);
      if (version !== this.loadVersion) return;
      this.setData({ approvals: data.approvals.map((entry) => decorateApproval(entry, absoluteMediaUrl)), pendingCount: data.pendingCount || 0 });
      if (this.data.pendingCount) wx.setTabBarBadge({ index: 2, text: this.data.pendingCount > 99 ? '99+' : String(this.data.pendingCount) });
      else wx.removeTabBarBadge({ index: 2 });
    } catch (error) { if (version === this.loadVersion) this.setData({ error: error.message }); }
    finally { if (version === this.loadVersion) this.setData({ loading: false }); }
  },
  openApproval(event) { wx.navigateTo({ url: `/miniprogram/pages/approval-detail/index?id=${encodeURIComponent(event.currentTarget.dataset.id)}` }); },
  createApproval() { wx.navigateTo({ url: '/miniprogram/pages/approval-create/index' }); },
});
