/* ── Interview System — Frontend Logic ── */

const API_BASE = '/api';

// ── Tab Switching ────────────────────────────────────────
document.querySelectorAll('.tab-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
    btn.classList.add('active');
    document.getElementById(btn.dataset.tab).classList.add('active');
  });
});

// ── File Drag & Drop ──────────────────────────────────────
function setupDropZone(dropEl, fileInput, infoEl) {
  dropEl.addEventListener('dragover', e => { e.preventDefault(); dropEl.classList.add('dragover'); });
  dropEl.addEventListener('dragleave', () => dropEl.classList.remove('dragover'));
  dropEl.addEventListener('drop', e => {
    e.preventDefault();
    dropEl.classList.remove('dragover');
    const file = e.dataTransfer.files[0];
    if (file) { fileInput.files = e.dataTransfer.files; updateFileInfo(file, infoEl); }
  });
  fileInput.addEventListener('change', () => {
    if (fileInput.files[0]) updateFileInfo(fileInput.files[0], infoEl);
  });
}

function updateFileInfo(file, el) {
  const name = file.name.length > 40 ? file.name.slice(0, 37) + '...' : file.name;
  const size = file.size < 1024 ? file.size + 'B' : file.size < 1048576 ? (file.size / 1024).toFixed(1) + 'KB' : (file.size / 1048576).toFixed(1) + 'MB';
  el.textContent = `📄 ${name} (${size})`;
}

setupDropZone(document.getElementById('jd-drop'), document.getElementById('jd-file'), document.getElementById('jd-file-info'));
setupDropZone(document.getElementById('resume-drop'), document.getElementById('resume-file'), document.getElementById('resume-file-info'));

// ── Helpers ────────────────────────────────────────────────
function $(id) { return document.getElementById(id); }
function show(el) { el.classList.remove('hidden'); }
function hide(el) { el.classList.add('hidden'); }
function err(msg) { const e = $('prep-error'); e.textContent = msg; show(e); }
function clearErr() { hide($('prep-error')); }

// ── 1. 面试前准备 ─────────────────────────────────────────

let cachedAnalysis = null;  // 保存分析结果，供模拟面试用

async function runAnalysis() {
  clearErr();
  const jdFile = $('jd-file').files[0];
  const resFile = $('resume-file').files[0];
  const jdText = $('jd-text').value.trim();
  const resText = $('resume-text').value.trim();
  const jobTitle = $('job-title').value.trim();

  if (!jdFile && !jdText) { err('请上传JD文件或粘贴JD文本'); return; }
  if (!resFile && !resText) { err('请上传简历文件或粘贴简历文本'); return; }

  show($('prep-loading'));
  hide($('prep-result'));
  hide($('to-interview-btn'));

  const formData = new FormData();
  if (jdFile) formData.append('jd_file', jdFile);
  else formData.append('jd_text', jdText);
  if (resFile) formData.append('resume_file', resFile);
  else formData.append('resume_text', resText);

  try {
    const resp = await fetch(`${API_BASE}/preparation/analyze`, {
      method: 'POST',
      body: formData,
    });
    const data = await resp.json();
    if (data.error) { err(data.error); return; }
    cachedAnalysis = { jd_text: jdFile ? null : jdText || (jdText || ''), resume_text: resFile ? null : resText, job_title: jobTitle };
    renderPrepResult(data);
  } catch(e) {
    err('网络请求失败: ' + e.message);
  } finally {
    hide($('prep-loading'));
  }
}

function renderPrepResult(data) {
  show($('prep-result'));
  show($('to-interview-btn'));

  // 总分
  $('overall-score').textContent = data.overall_score ?? '--';

  // 分项评分条
  const bars = $('score-bars');
  bars.innerHTML = '';
  const breakdown = data.score_breakdown || {};
  const labels = { '技能匹配': 'skill', '经验匹配': 'exp', '教育匹配': 'edu', '潜力空间': 'potential' };
  for (const [label, key] of Object.entries(labels)) {
    const val = breakdown[label] ?? 0;
    const row = document.createElement('div');
    row.className = 'score-bar-row';
    row.innerHTML = `
      <span class="score-bar-label">${label}</span>
      <div class="score-bar-track"><div class="score-bar-fill" style="width:${val}%"></div></div>
      <span class="score-bar-val">${val}</span>`;
    bars.appendChild(row);
  }

  // 匹配项
  const matched = $('matched-items');
  matched.innerHTML = '';
  (data.matched_items || []).forEach(item => {
    const div = document.createElement('div');
    div.className = 'item-card';
    div.innerHTML = `
      <div class="item-aspect">${item.aspect || ''}</div>
      <div class="item-content"><strong>JD:</strong> ${item.jd_requirement || ''}</div>
      <div class="item-content"><strong>简历:</strong> ${item.resume_evidence || ''}</div>
      <div class="item-analysis">${item.analysis || ''}</div>`;
    matched.appendChild(div);
  });

  // 缺口项
  const gaps = $('gap-items');
  gaps.innerHTML = '';
  const severityClass = { high: 'gap-high', medium: 'gap-medium', low: 'gap-low' };
  (data.gap_items || []).forEach(item => {
    const div = document.createElement('div');
    div.className = `item-card ${severityClass[item.severity] || 'gap-low'}`;
    div.innerHTML = `
      <div class="item-aspect">${item.aspect || ''} <span style="color:var(--warning)">[${item.severity || 'low'}]</span></div>
      <div class="item-content"><strong>JD要求:</strong> ${item.jd_requirement || ''}</div>
      <div class="item-analysis">💡 ${item.suggestion || ''}</div>`;
    gaps.appendChild(div);
  });

  // 知识领域
  const knowledge = $('knowledge-areas');
  knowledge.innerHTML = '';
  const priorityClass = { '必考': 'priority-must', '高频': 'priority-freq', '加分': 'priority-bonus' };
  const grid = document.createElement('div');
  grid.className = 'knowledge-grid';
  (data.knowledge_areas || []).forEach(area => {
    const card = document.createElement('div');
    card.className = 'knowledge-card';
    card.innerHTML = `
      <div class="k-category">${area.category || ''}</div>
      <span class="k-priority ${priorityClass[area.priority] || 'priority-freq'}">${area.priority || '高频'}</span>
      <div class="k-topics">${(area.topics || []).map(t => '• ' + t).join('<br>')}</div>`;
    grid.appendChild(card);
  });
  knowledge.appendChild(grid);

  // 学习大纲
  const study = $('study-plan');
  study.innerHTML = '';
  (data.detailed_study_plan || []).forEach(area => {
    const div = document.createElement('div');
    div.className = 'study-area';
    div.innerHTML = `<div class="study-area-title">📚 ${area.area || ''}</div>`;
    (area.sub_areas || []).forEach(sub => {
      const imp = { high: 'imp-high', medium: 'imp-med', low: 'imp-low' }[sub.importance] || 'imp-med';
      const subDiv = document.createElement('div');
      subDiv.className = 'study-sub';
      subDiv.innerHTML = `
        <div class="study-sub-name">${sub.name || ''}</div>
        <span class="study-sub-imp ${imp}">${sub.importance || 'medium'}</span>
        <div class="study-kps"><strong>关键点:</strong> ${(sub.key_points || []).join('、')}</div>
        <div class="study-resource">📖 ${sub.study_resources || ''}</div>`;
      div.appendChild(subDiv);
    });
    study.appendChild(div);
  });

  // 重点 & 建议
  const tips = $('tips-section');
  tips.innerHTML = '';
  if (data.interview_focus) {
    const focus = document.createElement('p');
    focus.innerHTML = '<strong>🎯 面试重点:</strong> ' + data.interview_focus.join('、');
    tips.appendChild(focus);
  }
  const ul = document.createElement('ul');
  ul.className = 'tips-list';
  (data.tips || []).forEach(tip => { const li = document.createElement('li'); li.textContent = tip; ul.appendChild(li); });
  tips.appendChild(ul);
}

function switchToInterview() {
  document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
  document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
  document.querySelector('[data-tab="interview"]').classList.add('active');
  document.getElementById('interview').classList.add('active');
  // 保存 JD/简历信息到 interview tab
  if (cachedAnalysis) {
    $('interview-start').querySelector('p').textContent =
      `职位: ${cachedAnalysis.job_title || '未知职位'}，准备好开始模拟面试了吗？`;
  }
}

// ── 2. 模拟面试 ───────────────────────────────────────────

let interviewSession = null;

async function startInterview() {
  if (!cachedAnalysis) {
    alert('请先完成面试前准备（分析JD和简历）');
    return;
  }
  hide($('interview-start'));
  show($('interview-loading'));

  try {
    const resp = await fetch(`${API_BASE}/interview/start`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        jd_text: cachedAnalysis.jd_text || '',
        resume_text: cachedAnalysis.resume_text || '',
        job_title: cachedAnalysis.job_title || '未知职位',
      }),
    });
    const data = await resp.json();
    if (data.error) { alert('启动面试失败: ' + data.error); hide($('interview-loading')); show($('interview-start')); return; }
    interviewSession = { id: data.session_id };

    hide($('interview-loading'));
    show($('interview-active'));
    renderQuestion(data);
  } catch(e) {
    hide($('interview-loading'));
    show($('interview-start'));
    alert('启动面试失败: ' + e.message);
  }
}

function renderQuestion(data) {
  $('q-text').textContent = data.question || '...';
  $('progress-text').textContent = `已回答 ${data.question_count ? data.question_count - 1 : 0} 题`;
  $('answer-input').value = '';
  $('answer-input').focus();
}

async function submitAnswer() {
  const answer = $('answer-input').value.trim();
  if (!answer) { alert('请输入回答'); return; }
  if (!interviewSession) { alert('会话已过期，请重新开始'); return; }

  show($('interview-loading'));
  hide($('interview-active'));

  try {
    const resp = await fetch(`${API_BASE}/interview/answer`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ session_id: interviewSession.id, answer }),
    });
    const data = await resp.json();

    hide($('interview-loading'));

    if (data.action === 'followup') {
      show($('interview-active'));
      $('q-text').textContent = data.question;
      $('progress-text').textContent = `已回答 ${data.question_count ? data.question_count - 1 : 0} 题`;
      $('answer-input').value = '';
      $('answer-input').focus();
    } else if (data.action === 'next') {
      show($('interview-active'));
      renderQuestion(data);
    } else if (data.action === 'end') {
      hide($('interview-active'));
      show($('interview-end'));
    }
  } catch(e) {
    hide($('interview-loading'));
    show($('interview-active'));
    alert('提交失败: ' + e.message);
  }
}

async function endInterview() {
  if (!interviewSession) return;
  if (!confirm('确定要结束面试吗？')) return;

  try {
    await fetch(`${API_BASE}/interview/end?session_id=${interviewSession.id}`, { method: 'POST' });
  } catch(e) {}

  interviewSession = null;
  hide($('interview-active'));
  show($('interview-end'));
}

function switchToReview() {
  document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
  document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
  document.querySelector('[data-tab="review"]').classList.add('active');
  document.getElementById('review').classList.add('active');
}

// ── 3. 面试复盘 ───────────────────────────────────────────

async function runReview() {
  const qaText = $('review-qa').value.trim();
  if (!qaText) { alert('请粘贴面试问答记录'); return; }

  hide($('review-result'));
  show($('review-loading'));
  hide($('review-error'));

  try {
    const resp = await fetch(`${API_BASE}/review/analyze`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        raw_text: qaText,
        job_title: $('review-job-title').value.trim() || '未知职位',
      }),
    });
    const data = await resp.json();
    if (data.error) { const e = $('review-error'); e.textContent = data.error; show(e); return; }
    renderReviewResult(data);
  } catch(e) {
    const err_el = $('review-error'); err_el.textContent = '网络请求失败: ' + e.message; show(err_el);
  } finally {
    hide($('review-loading'));
  }
}

function renderReviewResult(data) {
  show($('review-result'));

  $('review-score').textContent = (data.overall_score ?? '--') + '分';
  $('review-summary').textContent = data.overall_summary || '';

  // 亮点
  const strengthsEl = $('review-strengths');
  strengthsEl.innerHTML = '';
  (data.strengths || []).forEach(s => { const li = document.createElement('li'); li.textContent = '✨ ' + s; li.style.cssText = 'padding:4px 0;border-bottom:1px solid var(--border)'; strengthsEl.appendChild(li); });

  // 不足
  const weakEl = $('review-weaknesses');
  weakEl.innerHTML = '';
  (data.weaknesses || []).forEach(w => { const li = document.createElement('li'); li.textContent = '📌 ' + w; li.style.cssText = 'padding:4px 0;border-bottom:1px solid var(--border)'; weakEl.appendChild(li); });

  // 改进计划
  const impEl = $('review-improvement');
  impEl.innerHTML = '';
  (data.improvement_plan || []).forEach(p => { const li = document.createElement('li'); li.textContent = '📎 ' + p; li.style.cssText = 'padding:4px 0;border-bottom:1px solid var(--border)'; impEl.appendChild(li); });

  // 问题回顾
  const qaEl = $('review-questions');
  qaEl.innerHTML = '';
  const qaPairs = data.qa_pairs || [];
  (data.question_reviews || []).forEach((rev, i) => {
    const pair = qaPairs[i] || {};
    const div = document.createElement('div');
    div.className = 'qa-item';
    div.innerHTML = `
      <span class="qa-type-tag">${rev.category_hint || ''}</span>
      <div class="qa-q">❓ ${pair.question || rev.question || ''}</div>
      <div class="qa-a"><strong>你的回答:</strong> ${pair.answer || ''}</div>
      <div class="qa-score">⭐ 得分: ${rev.user_score ?? '?'}/10 — ${rev.user_answer_analysis || ''}</div>
      <div class="qa-ideal-label">💡 最佳参考答案:</div>
      <div class="qa-ideal">${rev.ideal_answer || ''}</div>
      ${rev.improvement_tips ? `<div class="qa-tip">改进: ${rev.improvement_tips}</div>` : ''}`;
    qaEl.appendChild(div);
  });

  // 分类汇总
  const catEl = $('review-category-summary');
  catEl.innerHTML = '';
  const catGrid = document.createElement('div');
  catGrid.className = 'cat-grid';
  const catSummary = data.category_summary || {};
  for (const [cat, info] of Object.entries(catSummary)) {
    const card = document.createElement('div');
    card.className = 'cat-card';
    card.innerHTML = `
      <div class="cat-name">${cat}</div>
      <div class="cat-score">${info.avg_score ?? 0}</div>
      <div class="cat-note">${info.note || ''}</div>`;
    catGrid.appendChild(card);
  }
  catEl.appendChild(catGrid);
}

// ── Voice Input (Web Speech API) ──────────────────────────
let recognition = null;
let isRecording = false;

function toggleVoiceInput() {
  const micBtn = $('mic-btn');
  const answerInput = $('answer-input');

  if (!('webkitSpeechRecognition' in window) && !('SpeechRecognition' in window)) {
    alert('当前浏览器不支持语音识别，请使用 Chrome 或 Edge 浏览器');
    return;
  }

  if (isRecording) {
    stopVoiceInput();
    return;
  }

  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  recognition = new SpeechRecognition();
  recognition.lang = 'zh-CN';
  recognition.continuous = true;
  recognition.interimResults = true;

  recognition.onresult = (event) => {
    let transcript = '';
    for (let i = 0; i < event.results.length; i++) {
      transcript += event.results[i][0].transcript;
    }
    answerInput.value = transcript;
  };

  recognition.onerror = (event) => {
    if (event.error !== 'no-speech') {
      console.error('语音识别错误:', event.error);
    }
    stopVoiceInput();
  };

  recognition.onend = () => {
    stopVoiceInput();
  };

  isRecording = true;
  micBtn.classList.add('recording');
  micBtn.textContent = '⏹';
  recognition.start();
}

function stopVoiceInput() {
  if (recognition) {
    recognition.stop();
    recognition = null;
  }
  isRecording = false;
  const micBtn = $('mic-btn');
  if (micBtn) {
    micBtn.classList.remove('recording');
    micBtn.textContent = '🎤';
  }
}
document.addEventListener('keydown', e => {
  if (e.key === 'Enter' && e.ctrlKey) {
    if (!$('prep-loading').classList.contains('hidden')) runAnalysis();
    else if (!$('review-loading').classList.contains('hidden')) runReview();
  }
  if (e.key === 'Enter' && e.ctrlKey && document.getElementById('interview-active') && !document.getElementById('interview-loading').classList.contains('hidden')) {
    submitAnswer();
  }
});
