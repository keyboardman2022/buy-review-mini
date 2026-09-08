const { request } = require('/utils/api');
const { money, dateTime } = require('/utils/format');
const statusText = { pending: '待审批', approved: '已通过', rejected: '已拒绝', expired: '已过期', cancelled: '已撤回' };
Page({
  data: { scope: 'inbox', approvals: [], loading: true, error: '' },
  onShow() { if (getApp().ensureSession()) this.load(); },
  onPullDownRefresh() { this.load().finally(() => wx.stopPullDownRefresh()); },
  switchScope(event) { const scope = event.currentTarget.dataset.scope; if (scope !== this.data.scope) { this.setData({ scope }); this.load(); } },
  async load() {
    this.setData({ loading: true, error: '' });
    try { const { approvals } = await request(`/api/approvals?scope=${this.data.scope}`); this.setData({ approvals: approvals.map((approval) => ({ ...approval, priceText: money(approval.price), createdText: dateTime(approval.createdAt), statusText: statusText[approval.status] || approval.status })) }); }
    catch (error) { this.setData({ error: error.message }); }
    finally { this.setData({ loading: false }); }
  },
  openApproval(event) { wx.navigateTo({ url: `/pages/approval-detail/index?id=${event.currentTarget.dataset.id}` }); },
  createApproval() { wx.navigateTo({ url: '/pages/approval-create/index' }); },
});
