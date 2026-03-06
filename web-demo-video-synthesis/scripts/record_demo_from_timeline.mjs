import fs from 'node:fs';
import path from 'node:path';
import { chromium } from 'playwright';

function parseArgs(argv) {
  const args = {};
  for (let i = 2; i < argv.length; i += 1) {
    const token = argv[i];
    if (!token.startsWith('--')) {
      throw new Error(`非法参数: ${token}`);
    }
    const key = token.slice(2);
    const next = argv[i + 1];
    if (!next || next.startsWith('--')) {
      args[key] = 'true';
      continue;
    }
    args[key] = next;
    i += 1;
  }
  return args;
}

function parseBool(input, keyName, defaultValue = false) {
  if (input === undefined || input === null || input === '') return defaultValue;
  const v = String(input).toLowerCase();
  if (v === 'true' || v === '1' || v === 'yes') return true;
  if (v === 'false' || v === '0' || v === 'no') return false;
  throw new Error(`${keyName} 必须是 true/false`);
}

function parseSize(input, keyName) {
  const m = /^(\d+)x(\d+)$/i.exec(input || '');
  if (!m) {
    throw new Error(`${keyName} 格式错误，应为 WIDTHxHEIGHT`);
  }
  return { width: Number(m[1]), height: Number(m[2]) };
}

function parseNumber(input, keyName) {
  const v = Number(input);
  if (!Number.isFinite(v)) {
    throw new Error(`${keyName} 必须是数字`);
  }
  return v;
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function parseChoice(input, keyName, choices) {
  const v = String(input || '').toLowerCase();
  if (!choices.includes(v)) {
    throw new Error(`${keyName} 必须是 ${choices.join('/')} 之一`);
  }
  return v;
}

function isContextDestroyedError(err) {
  const msg = String(err?.message || err || '');
  return msg.includes('Execution context was destroyed') || msg.includes('Cannot find context');
}

async function evaluateWithRetry(page, fn, arg = undefined, retries = 4) {
  let lastErr = null;
  for (let i = 0; i < retries; i += 1) {
    try {
      if (arg === undefined) {
        return await page.evaluate(fn);
      }
      return await page.evaluate(fn, arg);
    } catch (err) {
      lastErr = err;
      if (!isContextDestroyedError(err) || i === retries - 1) {
        throw err;
      }
      await sleep(300);
      await page.waitForLoadState('domcontentloaded').catch(() => {});
    }
  }
  throw lastErr;
}

async function ensureCaptionOverlay(page) {
  await evaluateWithRetry(page, () => {
    const old = document.getElementById('__timeline_caption_overlay__');
    if (old) old.remove();

    const wrap = document.createElement('div');
    wrap.id = '__timeline_caption_overlay__';
    wrap.style.position = 'fixed';
    wrap.style.left = '50%';
    wrap.style.bottom = '92px';
    wrap.style.transform = 'translateX(-50%)';
    wrap.style.zIndex = '999999';
    wrap.style.width = 'min(54vw, 1000px)';
    wrap.style.maxWidth = '1000px';
    wrap.style.minWidth = '560px';
    wrap.style.padding = '14px 18px';
    wrap.style.borderRadius = '12px';
    wrap.style.background = 'rgba(0,0,0,0.70)';
    wrap.style.border = '1px solid rgba(255,255,255,0.22)';
    wrap.style.boxShadow = '0 10px 30px rgba(0,0,0,0.40)';
    wrap.style.backdropFilter = 'blur(4px)';
    wrap.style.pointerEvents = 'none';

    const text = document.createElement('div');
    text.id = '__timeline_caption_text__';
    text.style.color = '#fff';
    text.style.fontSize = '26px';
    text.style.fontWeight = '600';
    text.style.lineHeight = '1.35';
    text.style.whiteSpace = 'pre-wrap';
    text.style.wordBreak = 'break-word';
    text.style.textAlign = 'left';

    wrap.appendChild(text);
    document.body.appendChild(wrap);
  });
}

async function setCaption(page, text) {
  await ensureCaptionOverlay(page);
  await evaluateWithRetry(page, (nextText) => {
    const el = document.getElementById('__timeline_caption_text__');
    if (!el) return;
    el.textContent = nextText || '';
  }, text);
}

async function ensureLang(page, lang) {
  // 录屏稳定性：如果页面存在语言切换按钮，建议在这里强制设置成一致状态。
  // 默认仅做最小逻辑：lang=en 时尽量点一次 EN 按钮。
  if (lang !== 'en') return;
  const enBtn = page.getByRole('button', { name: 'EN' }).first();
  if (await enBtn.count()) {
    // 如果已是 EN，点击通常无副作用；如有副作用，请在 demo 页层面做幂等处理。
    await enBtn.click();
    await sleep(260);
  }
}

async function scrollToCue(page, cueId) {
  if (!cueId) return;
  await evaluateWithRetry(page, (arg) => {
    const { id, behavior } = arg || {};
    const el = document.getElementById(id);
    if (!el) return;
    el.scrollIntoView({ behavior: behavior || 'auto', block: 'start' });
  }, { id: cueId, behavior: page.__scrollBehavior || 'auto' });

  // 等待“就位”：避免 smooth 滚动导致下一段语音已开始但页面还在移动。
  const settleMs = Number(page.__scrollSettleMs || 420);
  await page
    .waitForFunction(
      (id) => {
        const el = document.getElementById(id);
        if (!el) return true;
        const r = el.getBoundingClientRect();
        return Math.abs(r.top) < 8;
      },
      cueId,
      { timeout: Math.max(800, settleMs * 4) },
    )
    .catch(() => {});

  await sleep(settleMs);
}

async function getPageTextPreview(page, maxChars = 240) {
  const text = await evaluateWithRetry(page, () => {
    const t = document?.body?.innerText || '';
    return String(t).replace(/\s+/g, ' ').trim();
  }).catch(() => '');
  if (!text) return '';
  return text.length > maxChars ? `${text.slice(0, maxChars)}…` : text;
}

async function assertResponseLooksLikeHtml({ url, response, failOnJson = true }) {
  // Playwright 在部分 scheme（如 file://、data:）下可能拿不到 response；此时不做 content-type 判断。
  if (!response) return;
  const status = response.status();
  const headers = response.headers() || {};
  const contentType = String(headers['content-type'] || '');

  if (status >= 400) {
    throw new Error(
      `record_url 返回 HTTP ${status}（很可能服务未启动/端口被占用/路径错误）。url=${url}`,
    );
  }

  if (failOnJson && contentType.toLowerCase().includes('application/json')) {
    throw new Error(
      `record_url 返回 application/json（很可能录到了 API 或 404 JSON，而不是网页）。url=${url}`,
    );
  }
}

async function assertPageExpectation({ page, expectSelector, expectTitleIncludes, expectTimeoutMs }) {
  const timeoutMs = Math.max(500, Number(expectTimeoutMs || 12000));
  if (expectTitleIncludes) {
    const title = await page.title().catch(() => '');
    if (!String(title).includes(String(expectTitleIncludes))) {
      const preview = await getPageTextPreview(page);
      throw new Error(
        `页面 title 不满足预期：title 应包含 "${expectTitleIncludes}"，实际为 "${title}". ` +
          (preview ? `页面文本预览: ${preview}` : ''),
      );
    }
  }

  if (expectSelector) {
    const selector = String(expectSelector);
    const ok = await page
      .locator(selector)
      .first()
      .waitFor({ state: 'attached', timeout: timeoutMs })
      .then(() => true)
      .catch(() => false);
    if (!ok) {
      const title = await page.title().catch(() => '');
      const preview = await getPageTextPreview(page);
      throw new Error(
        `页面缺少预期元素：expect_selector="${selector}"（timeout=${timeoutMs}ms）。title="${title}". ` +
          (preview ? `页面文本预览: ${preview}` : ''),
      );
    }
  }
}

async function main() {
  const args = parseArgs(process.argv);
  if (!args.url) throw new Error('缺少 --url');
  if (!args['timeline-json']) throw new Error('缺少 --timeline-json');
  if (!args.out) throw new Error('缺少 --out');

  const timelinePath = path.resolve(args['timeline-json']);
  if (!fs.existsSync(timelinePath)) {
    throw new Error(`timeline 文件不存在: ${timelinePath}`);
  }

  const timeline = JSON.parse(fs.readFileSync(timelinePath, 'utf8'));
  const segments = Array.isArray(timeline.segments) ? timeline.segments : [];
  const scrollEvents = Array.isArray(timeline.scroll_events) ? timeline.scroll_events : [];
  if (!segments.length) {
    throw new Error('timeline.segments 为空');
  }

  const viewport = parseSize(args.viewport || '1920x1080', '--viewport');
  const recordSize = parseSize(args['record-size'] || '3840x2160', '--record-size');
  const dsf = parseNumber(args['device-scale-factor'] || '2', '--device-scale-factor');
  const tailSec = parseNumber(args['tail-sec'] || '1', '--tail-sec');
  const lang = String(args.lang || 'en').toLowerCase();
  const noCaptions = String(args['no-captions'] || '').toLowerCase() === 'true';
  const waitUntil = parseChoice(args['wait-until'] || 'networkidle', '--wait-until', [
    'networkidle',
    'domcontentloaded',
    'load',
    'commit',
  ]);
  const failOnJson = parseBool(args['fail-on-json'], '--fail-on-json', true);
  const expectSelector = args['expect-selector'] ? String(args['expect-selector']) : '';
  const expectTitleIncludes = args['expect-title-includes']
    ? String(args['expect-title-includes'])
    : '';
  const expectTimeoutMs = parseNumber(args['expect-timeout-ms'] || '12000', '--expect-timeout-ms');
  const scrollBehavior = parseChoice(args['scroll-behavior'] || 'auto', '--scroll-behavior', [
    'auto',
    'smooth',
  ]);
  const scrollSettleMs = parseNumber(args['scroll-settle-ms'] || '420', '--scroll-settle-ms');

  const outPath = path.resolve(args.out);
  const outDir = path.dirname(outPath);
  fs.mkdirSync(outDir, { recursive: true });
  const rawDir = path.join(outDir, '_raw_record');
  fs.mkdirSync(rawDir, { recursive: true });

  const browser = await chromium.launch({
    headless: true,
    args: [`--force-device-scale-factor=${dsf}`],
  });

  const context = await browser.newContext({
    viewport,
    deviceScaleFactor: dsf,
    recordVideo: {
      dir: rawDir,
      size: recordSize,
    },
  });

  const page = await context.newPage();
  const video = page.video();
  // 在 helper 里读取（避免反复穿参）
  page.__scrollBehavior = scrollBehavior;
  page.__scrollSettleMs = scrollSettleMs;

  const resp = await page.goto(args.url, { waitUntil, timeout: 45000 });
  await assertResponseLooksLikeHtml({ url: args.url, response: resp, failOnJson });
  await sleep(1200);
  await ensureLang(page, lang);
  await assertPageExpectation({
    page,
    expectSelector,
    expectTitleIncludes,
    expectTimeoutMs,
  });

  // 定位到第一段章节
  await scrollToCue(page, segments[0]?.cue_id || null);
  if (!noCaptions) {
    await ensureCaptionOverlay(page);
    await setCaption(page, '');
  }

  const t0 = Date.now();

  const timelineEvents = [];
  if (!noCaptions) {
    for (let i = 0; i < segments.length; i += 1) {
      const segStart = Number(segments[i]?.start_sec || 0);
      const segEnd = Number(segments[i]?.end_sec || 0);
      timelineEvents.push({ type: 'caption_start', t: segStart, priority: 3, segIndex: i });
      timelineEvents.push({ type: 'caption_end', t: segEnd, priority: 1, segIndex: i });
      // 每秒做一次字幕同步，防止页面重绘导致 overlay 丢失。
      for (let t = Math.floor(segStart) + 1; t < segEnd; t += 1) {
        timelineEvents.push({ type: 'caption_sync', t, priority: 4, segIndex: i });
      }
    }
  }
  for (const event of scrollEvents) {
    timelineEvents.push({
      type: 'scroll',
      t: Number(event.scroll_action_at_sec || 0),
      priority: 2,
      toIndex: Number(event.to_seg_index || 0),
    });
  }

  timelineEvents.sort((a, b) => {
    if (a.t !== b.t) return a.t - b.t;
    return a.priority - b.priority;
  });

  let activeSegIndex = -1;
  for (const event of timelineEvents) {
    const targetMs = Math.max(0, Math.round(event.t * 1000));
    const elapsed = Date.now() - t0;
    const waitMs = targetMs - elapsed;
    if (waitMs > 0) await sleep(waitMs);

    await ensureLang(page, lang);

    if (event.type === 'scroll') {
      const targetCue = segments[event.toIndex]?.cue_id || null;
      await scrollToCue(page, targetCue);
      continue;
    }
    if (event.type === 'caption_start') {
      activeSegIndex = event.segIndex;
      const text = String(segments[event.segIndex]?.text || '');
      await setCaption(page, text);
      continue;
    }
    if (event.type === 'caption_sync') {
      if (activeSegIndex === event.segIndex) {
        const text = String(segments[event.segIndex]?.text || '');
        await setCaption(page, text);
      }
      continue;
    }
    if (event.type === 'caption_end') {
      if (activeSegIndex === event.segIndex) {
        activeSegIndex = -1;
        await setCaption(page, '');
      }
    }
  }

  const totalSec = Number(timeline.timeline_total_sec || 0);
  const endTargetMs = Math.max(0, Math.round((totalSec + tailSec) * 1000));
  const elapsed = Date.now() - t0;
  if (endTargetMs > elapsed) {
    await sleep(endTargetMs - elapsed);
  }

  await context.close();
  await browser.close();

  if (!video) throw new Error('录屏对象为空');

  const rawPath = await video.path();
  if (path.resolve(rawPath) !== outPath) {
    fs.copyFileSync(rawPath, outPath);
  }
  // 清理随机命名的 raw 录屏文件，避免输出目录出现重复副本。
  if (fs.existsSync(rawPath)) fs.unlinkSync(rawPath);
  if (fs.existsSync(rawDir)) fs.rmSync(rawDir, { recursive: true, force: true });

  const summary = {
    out: outPath,
    url: args.url,
    viewport,
    recordSize,
    deviceScaleFactor: dsf,
    segments: segments.length,
    scrollEvents: scrollEvents.length,
    timelineTotalSec: totalSec,
    tailSec,
    noCaptions,
    waitUntil,
    failOnJson,
    expectSelector,
    expectTitleIncludes,
    expectTimeoutMs,
    scrollBehavior,
    scrollSettleMs,
  };
  console.log(JSON.stringify(summary, null, 2));
}

main().catch((err) => {
  console.error(`[record_demo_from_timeline] ${err.message}`);
  process.exit(1);
});
