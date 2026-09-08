const { request } = require('../../utils/api');
const { money, dateTime } = require('../../utils/format');
const statusText = { pending: '待审批', approved: '已通过', rejected: '已拒绝', expired: '已过期', cancelled: '已撤回' };
const ruleText = { veto: '一票否决', majority: '多数决定', unanimous: '全员一致' };
Page({
  data: { scope: 'inbox', approvals: [], loading: true, error: '' },
  onShow() { if (getApp().ensureSession()) this.load(); },
  onPullDownRefresh() { this.load().finally(() => wx.stopPullDownRefresh()); },
  switchScope(event) { const scope = event.currentTarget.dataset.scope; if (scope !== this.data.scope) { this.setData({ scope }); this.load(); } },
  async load() {
    this.setData({ loading: true, error: '' });
    try { const { approvals } = await request(`/api/approvals?scope=${this.data.scope}`); this.setData({ approvals: approvals.map((approval) => ({ ...approval, priceText: money(approval.price), createdText: dateTime(approval.createdAt), statusText: statusText[approval.status] || approval.status, ruleText: ruleText[approval.rule] || approval.rule, decidedCount: approval.reviewers.filter((reviewer) => reviewer.decision).length })) }); }
    catch (error) { this.setData({ error: error.message }); }
    finally { this.setData({ loading: false }); }
  },
  openApproval(event) { wx.navigateTo({ url: `/miniprogram/pages/approval-detail/index?id=${event.currentTarget.dataset.id}` }); },
  createApproval() { wx.navigateTo({ url: '/miniprogram/pages/approval-create/index' }); },
});
