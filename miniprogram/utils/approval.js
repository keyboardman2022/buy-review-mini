const { money, dateTime } = require('./format');
const rules = { veto: '一票否决', majority: '多数决定', unanimous: '全员一致' };
const states = { pending: '等待朋友意见', approved: '朋友支持', rejected: '先缓缓', expired: '本次已到期', cancelled: '已撤回' };
function decorateApproval(approval, mediaUrl = (value) => value, now = Date.now()) {
  const reviewers = approval.reviewers || [];
  const yes = reviewers.filter((v) => v.decision === 'accept').length;
  const no = reviewers.filter((v) => v.decision === 'reject').length;
  const waiting = reviewers.length - yes - no;
  const threshold = Math.floor(reviewers.length / 2) + 1;
  const progressText = approval.status === 'pending' ?
    (approval.rule === 'majority' ? `还需要 ${Math.max(0, threshold - yes)} 票支持` :
      approval.rule === 'veto' ? `还等 ${waiting} 位朋友，任意一票反对即结束` : `还等 ${waiting} 位朋友，全部回复后判定`) :
    ({ approved: '已达到约定规则，最终是否购买由你决定', rejected: '未达到约定规则，听听朋友的理由再决定', expired: '超过截止时间，未自动通过', cancelled: '发起人已撤回，本次不再接收意见' }[approval.status] || '');
  const remaining = approval.expiresAt - now;
  const deadlineText = approval.status !== 'pending' ? '本次已结束' : remaining <= 0 ? '已到截止时间' :
    remaining < 3600000 ? '不足 1 小时截止' : `剩余 ${Math.ceil(remaining / 3600000)} 小时`;
  return {
    ...approval, yes, no, waiting, decidedCount: yes + no,
    yesWidth: reviewers.length ? yes / reviewers.length * 100 : 0,
    noWidth: reviewers.length ? no / reviewers.length * 100 : 0,
    progressText, deadlineText, urgent: approval.status === 'pending' && remaining < 3600000,
    priceText: money(approval.price), createdText: dateTime(approval.createdAt), expiresText: dateTime(approval.expiresAt),
    ruleText: rules[approval.rule], statusText: states[approval.status] || approval.status,
    photos: (approval.imageUrls || []).map(mediaUrl),
    reviewers: reviewers.map((v) => ({ ...v, decisionText: v.decision === 'accept' ? '支持购买' : v.decision === 'reject' ? '建议等等' : '还没回复', votedText: v.votedAt ? dateTime(v.votedAt) : '' })),
  };
}
module.exports = { decorateApproval };
