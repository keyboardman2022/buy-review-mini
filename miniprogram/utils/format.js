function yuanToCents(value) {
  const text = String(value == null ? '' : value).trim();
  if (!/^(0|[1-9]\d*)(\.\d{1,2})?$/.test(text)) return null;
  const [yuan, decimal = ''] = text.split('.');
  const cents = Number(yuan) * 100 + Number((decimal + '00').slice(0, 2));
  return Number.isSafeInteger(cents) ? cents : null;
}
function money(cents) { return `¥${(Number(cents || 0) / 100).toFixed(2)}`; }
function dateTime(value) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '';
  const pad = (number) => String(number).padStart(2, '0');
  return `${date.getMonth() + 1}月${date.getDate()}日 ${pad(date.getHours())}:${pad(date.getMinutes())}`;
}
function decorateItem(item, absoluteMediaUrl) {
  return { ...item, priceText: money(item.price), photos: (item.imageUrls || []).map(absoluteMediaUrl), timeText: dateTime(item.createdAt) };
}
module.exports = { yuanToCents, money, dateTime, decorateItem };
