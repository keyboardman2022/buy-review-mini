const { token, clearSession } = require('./miniprogram/utils/api');

App({
  globalData: { user: null, launchTarget: null },
  onLaunch(options) {
    const query = options && options.query ? options.query : {};
    if (query.invite) this.globalData.launchTarget = { invite: query.invite };
    if (query.approvalId) this.globalData.launchTarget = { approvalId: query.approvalId };
  },
  ensureSession(launchTarget) {
    if (token()) return true;
    if (launchTarget) this.globalData.launchTarget = launchTarget;
    clearSession();
    wx.reLaunch({ url: '/miniprogram/pages/login/index' });
    return false;
  },
  openLaunchTarget() {
    const target = this.globalData.launchTarget;
    this.globalData.launchTarget = null;
    if (target && target.invite) {
      wx.navigateTo({ url: `/miniprogram/pages/friends/index?invite=${encodeURIComponent(target.invite)}` });
      return;
    }
    if (target && target.approvalId) {
      wx.navigateTo({ url: `/miniprogram/pages/approval-detail/index?id=${encodeURIComponent(target.approvalId)}` });
    }
  },
});
