// Render a dedicated 5:4 WeChat card. Never include private comments or votes.
function imageInfo(src) {
  return new Promise((resolve) => {
    if (!src) { resolve(null); return; }
    wx.getImageInfo({ src, success: resolve, fail: () => resolve(null) });
  });
}
function fitText(ctx, value, width) {
  let text = String(value || '');
  if (ctx.measureText(text).width <= width) return text;
  const chars = Array.from(text);
  while (chars.length && ctx.measureText(chars.join('') + '…').width > width) chars.pop();
  return chars.join('') + '…';
}
async function createShareCard(page, approval) {
  const photo = await imageInfo(approval.photos && approval.photos[0]);
  const ctx = wx.createCanvasContext('share-card', page);
  ctx.setFillStyle('#f5f2ea'); ctx.fillRect(0, 0, 500, 400);
  ctx.setFillStyle('#ffffff'); ctx.fillRect(20, 20, 460, 360);
  ctx.setFillStyle('#65695e'); ctx.setFontSize(16); ctx.fillText('买前问问 / 朋友帮我拿主意', 42, 55);
  ctx.setFillStyle('#fff0e5'); ctx.fillRect(42, 82, 174, 174);
  if (photo) {
    const size = Math.min(photo.width, photo.height);
    ctx.drawImage(photo.path, (photo.width - size) / 2, (photo.height - size) / 2, size, size, 42, 82, 174, 174);
  } else {
    ctx.setFillStyle('#e26738'); ctx.setFontSize(64); ctx.fillText('问', 96, 190);
  }
  ctx.setFillStyle('#272c25'); ctx.setFontSize(24);
  ctx.fillText(fitText(ctx, approval.title, 204), 236, 123);
  ctx.setFillStyle('#cf502a'); ctx.setFontSize(28);
  ctx.fillText(fitText(ctx, approval.priceText, 204), 236, 174);
  ctx.setFillStyle('#727569'); ctx.setFontSize(16);
  ctx.fillText(approval.ruleText || '朋友共同决定', 236, 213);
  ctx.setStrokeStyle('#deddd4'); ctx.setLineDash([4, 4]);
  ctx.beginPath(); ctx.moveTo(42, 279); ctx.lineTo(458, 279); ctx.stroke();
  ctx.setFillStyle('#e9683b'); ctx.fillRect(42, 300, 416, 54);
  ctx.setFillStyle('#ffffff'); ctx.setFontSize(20); ctx.setTextAlign('center');
  ctx.fillText('点开看看，说说你的理由', 250, 335);
  return new Promise((resolve, reject) => ctx.draw(false, () => {
    wx.canvasToTempFilePath({ canvasId: 'share-card', x: 0, y: 0, width: 500, height: 400,
      destWidth: 1000, destHeight: 800, fileType: 'png',
      success: ({ tempFilePath }) => resolve(tempFilePath), fail: reject }, page);
  }));
}
module.exports = { createShareCard, fitText };
