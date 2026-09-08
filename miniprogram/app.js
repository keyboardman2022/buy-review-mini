const { token, clearSession } = require('/utils/api');

App({
  globalData: { user: null, launchTarget: null },
  onLaunch(options) {
    const query = options && options.query ? options.query : {};
    if (query.invite) this.globalData.launchTarget = { invite: query.invite };
    if (query.approvalId) this.globalData.launchTarget = { approvalId: query.approvalId };
  },
  ensureSession() {
    if (token()) return true;
    clearSession();
    wx.reLaunch({ url: '/pages/login/index' });
    return false;
  },
  openLaunchTarget() {
    const target = this.globalData.launchTarget;
    this.globalData.launchTarget = null;
    if (target && target.invite) {
      wx.navigateTo({ url: `/pages/friends/index?invite=${encodeURIComponent(target.invite)}` });
      return;
    }
    if (target && target.approvalId) {
      wx.navigateTo({ url: `/pages/approval-detail/index?id=${encodeURIComponent(target.approvalId)}` });
    }
  },
});
