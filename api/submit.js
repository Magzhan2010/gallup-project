// =============================================================================
// api/submit.js — Vercel Serverless Function
// =============================================================================
// Принимает результаты теста от клиента и пересылает в Telegram Bot API.
// Токены бота хранятся в Vercel env vars (TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID)
// и НЕ попадают в публичный GitHub-код.

module.exports = async (req, res) => {
  // CORS — на случай если фронтенд на другом домене
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'POST, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');

  if (req.method === 'OPTIONS') {
    return res.status(200).end();
  }

  if (req.method !== 'POST') {
    return res.status(405).json({ ok: false, error: 'Method not allowed' });
  }

  // Vercel автоматически парсит JSON в req.body
  const payload = req.body;
  if (!payload || typeof payload !== 'object') {
    return res.status(400).json({ ok: false, error: 'Invalid payload' });
  }

  const botToken = process.env.TELEGRAM_BOT_TOKEN;
  const chatId = process.env.TELEGRAM_CHAT_ID;

  if (!botToken || !chatId) {
    console.error('TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID not set');
    return res.status(500).json({
      ok: false,
      error: 'Server not configured. Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in Vercel env vars.'
    });
  }

  // Базовая валидация payload
  if (typeof payload.answers_count !== 'number' || !Array.isArray(payload.predicted_top5)) {
    return res.status(400).json({ ok: false, error: 'Malformed payload' });
  }

  const text = formatMessage(payload);

  // Если сообщение слишком длинное — разбиваем на 2
  const MAX_LEN = 4000;
  const messages = [];
  if (text.length <= MAX_LEN) {
    messages.push(text);
  } else {
    const summaryEnd = text.indexOf('📋');
    if (summaryEnd > 0) {
      messages.push(text.substring(0, summaryEnd).trim());
      messages.push(text.substring(summaryEnd).trim());
    } else {
      messages.push(text.substring(0, MAX_LEN));
      messages.push(text.substring(MAX_LEN));
    }
  }

  let allOk = true;
  let lastError = null;

  for (const msg of messages) {
    try {
      const tgRes = await fetch(`https://api.telegram.org/bot${botToken}/sendMessage`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          chat_id: chatId,
          text: msg,
          parse_mode: 'HTML',
          disable_web_page_preview: true,
        }),
      });
      const tgResult = await tgRes.json();
      if (!tgResult.ok) {
        allOk = false;
        lastError = tgResult.description || `HTTP ${tgRes.status}`;
        break;
      }
    } catch (e) {
      allOk = false;
      lastError = e.message || 'Network error';
      break;
    }
  }

  if (allOk) {
    return res.status(200).json({ ok: true });
  }
  return res.status(500).json({ ok: false, error: lastError });
};

function formatMessage(payload) {
  const escapeHtml = (s) => String(s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');

  const dt = new Date(payload.timestamp).toLocaleString('ru-RU', { timeZone: 'Asia/Almaty' });
  const lines = [];

  lines.push('🎯 <b>Gallup Copy — новый результат</b>');
  lines.push('📅 ' + dt);
  lines.push('');
  lines.push('✅ Ответов: <b>' + payload.answers_count + '/200</b>');
  lines.push('🎓 Gallup введён: <b>' + (payload.gallup_top5 && payload.gallup_top5.length > 0 ? 'да ✅' : 'НЕТ ❌') + '</b>');
  lines.push('');

  // Предсказанный топ-5
  lines.push('📊 <b>Предсказанный топ-5:</b>');
  if (Array.isArray(payload.predicted_top5)) {
    payload.predicted_top5.forEach((t, i) => {
      lines.push('  ' + (i+1) + '. ' + escapeHtml(t.theme) + ' <i>(score: ' + t.score + ')</i>');
    });
  }
  lines.push('');

  // Gallup топ-5 (если есть)
  if (payload.gallup_top5 && payload.gallup_top5.length > 0) {
    lines.push('🎓 <b>Их Gallup топ-5:</b>');
    payload.gallup_top5.forEach((t, i) => {
      lines.push('  ' + (i+1) + '. ' + escapeHtml(t.theme));
    });
    lines.push('');

    const predSet = new Set(payload.predicted_top5.slice(0, 5).map(t => t.theme));
    const gallupSet = new Set(payload.gallup_top5.map(t => t.theme));
    const match = [...predSet].filter(t => gallupSet.has(t)).length;
    const pct = (match / 5 * 100).toFixed(0);
    const emoji = match >= 4 ? '🟢' : (match >= 2 ? '🟡' : '🔴');
    lines.push(emoji + ' <b>Точность топ-5: ' + match + '/5 = ' + pct + '%</b>');
    lines.push('');
  } else {
    lines.push('⚠️ <i>Gallup не введён → нельзя посчитать точность.</i>');
    lines.push('');
  }

  // Полный ранг (только если Gallup введён)
  if (payload.gallup_top5 && payload.gallup_top5.length > 0 && Array.isArray(payload.all_ranks)) {
    lines.push('📋 <b>Сравнение полного ранга:</b>');
    lines.push('<pre>Rank  Theme                 Gallup  Δ');
    payload.all_ranks.forEach(t => {
      const gallupRank = payload.gallup_top5.find(g => g.theme === t.theme);
      const gr = gallupRank ? gallupRank.rank : null;
      const delta = gr != null ? (t.rank - gr) : null;
      const deltaStr = delta != null ? (delta > 0 ? '+' + delta : String(delta)) : ' -';
      const matchMark = gr != null && Math.abs(t.rank - gr) <= 5 ? '✓' : (gr != null ? '✗' : ' ');
      const tn = escapeHtml(t.theme).padEnd(22);
      const gn = gr != null ? String(gr).padStart(2) : ' -';
      lines.push(String(t.rank).padStart(2) + '   ' + tn + '  ' + gn + '   ' + deltaStr.padStart(3) + '  ' + matchMark);
    });
    lines.push('</pre>');
  } else if (Array.isArray(payload.all_ranks)) {
    // Без Gallup — только предсказание
    lines.push('📋 <b>Полный предсказанный ранг:</b>');
    lines.push('<pre>Rank  Theme                 Score');
    payload.all_ranks.forEach(t => {
      const tn = escapeHtml(t.theme).padEnd(22);
      lines.push(String(t.rank).padStart(2) + '   ' + tn + '  ' + String(t.score).padStart(4));
    });
    lines.push('</pre>');
  }

  return lines.join('\n');
}
