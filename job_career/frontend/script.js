const API_BASE = window.location.origin;
const API_URL = `${API_BASE}/api/analyze`;
const ARCHIVE_API_URL = `${API_BASE}/api/archive`;

const views = {
    home: document.getElementById('viewHome'),
    analyze: document.getElementById('viewAnalyze'),
    followup: document.getElementById('viewFollowup'),
    result: document.getElementById('viewResult'),
};

const profileEl = document.getElementById('profile');

const analyzeBtn = document.getElementById('analyzeBtn');
const resetBtn = document.getElementById('resetBtn');
const loadExampleBtn = document.getElementById('loadExample');
const heroExampleBtn = document.getElementById('heroExampleBtn');
const startAnalyzeBtn = document.getElementById('startAnalyzeBtn');
const navHome = document.getElementById('navHome');

const loadingEl = document.getElementById('loading');
const resultSummary = document.getElementById('resultSummary');
const resultGrid = document.getElementById('resultGrid');
const resultTableContainer = document.getElementById('resultTableContainer');
const resultTableBody = document.getElementById('resultTableBody');

const followUpSummary = document.getElementById('followUpSummary');
const followUpGrid = document.getElementById('followUpGrid');
const followUpSubmit = document.getElementById('followUpSubmit');
const selectedSummaryCard = document.getElementById('selectedSummaryCard');
const selectedSummaryList = document.getElementById('selectedSummaryList');

const matchCountEl = document.getElementById('matchCount');
const errorAlert = document.getElementById('errorAlert');
const errorMessage = document.getElementById('errorMessage');

const archiveModal = document.getElementById('archiveModal');
const archiveModalTitle = document.getElementById('archiveModalTitle');
const archiveModalMeta = document.getElementById('archiveModalMeta');
const archiveModalBody = document.getElementById('archiveModalBody');
const archiveModalClose = document.getElementById('archiveModalClose');

const promptChips = document.querySelectorAll('[data-prompt-chip]');
const stepItems = document.querySelectorAll('[data-step]');

let followUpTimeoutId = null;
let analysisSessionId = '';
let analysisSessionState = 'idle';

const FOLLOW_UP_SESSION_TIMEOUT_MS = 5 * 60 * 1000;

const EXAMPLE_PROFILE = '저는 3년 동안 병원에서 원무과 행정 직원으로 일했습니다. 환자 데이터를 다루다 보니 의료 행정 지식과 의료정보 보호 정책 수립 쪽에 관심이 생겼고, 관련 경험도 쌓았습니다. 공공기관 쪽으로 이직하고 싶습니다.';

function showPage(pageName) {
    Object.entries(views).forEach(([name, element]) => {
        if (!element) return;
        element.classList.toggle('hidden', name !== pageName);
    });

    loadingEl.classList.add('hidden');
    errorAlert.classList.add('hidden');

    window.scrollTo({ top: 0, behavior: 'smooth' });
    lucide.createIcons();
}

document.querySelectorAll('[data-page-link]').forEach((button) => {
    button.addEventListener('click', () => {
        const pageName = button.dataset.pageLink;

        if (pageName === 'result' && !resultGrid.children.length) {
            showPage('home');
            return;
        }

        showPage(pageName);
    });
});

navHome.addEventListener('click', () => showPage('home'));
startAnalyzeBtn.addEventListener('click', () => showPage('analyze'));

function fillExample() {
    profileEl.value = EXAMPLE_PROFILE;
    showPage('analyze');

    window.setTimeout(() => {
        profileEl.focus();
    }, 120);
}

loadExampleBtn.addEventListener('click', fillExample);

if (heroExampleBtn) {
    heroExampleBtn.addEventListener('click', fillExample);
}

promptChips.forEach((chip) => {
    chip.addEventListener('click', () => {
        const text = chip.dataset.promptChip || '';
        const current = profileEl.value.trim();

        profileEl.value = current ? `${current}\n${text}` : text;
        profileEl.focus();
    });
});

resetBtn.addEventListener('click', () => {
    profileEl.value = '';
    resetAnalysisView();
    setActiveStep(1);
});

archiveModalClose.addEventListener('click', closeArchiveModal);

archiveModal.addEventListener('click', (event) => {
    if (event.target === archiveModal) {
        closeArchiveModal();
    }
});

document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape') {
        closeArchiveModal();
    }
});

resultGrid.addEventListener('click', async (event) => {
    const button = event.target.closest('button[data-analysis-file]');

    if (!button) {
        return;
    }

    const analysisFile = button.dataset.analysisFile;
    const institution = button.dataset.institution || '상세보기';

    await openArchiveModal(analysisFile, institution);
});

followUpGrid.addEventListener('click', (event) => {
    const button = event.target.closest('button[data-followup-category]');

    if (!button) {
        return;
    }

    const category = button.dataset.followupCategory;
    const multiSelect = button.dataset.multiSelect === 'true';

    const sameCategoryButtons = Array.from(followUpGrid.querySelectorAll('button[data-followup-category]'))
        .filter((item) => item.dataset.followupCategory === category);

    if (!multiSelect) {
        sameCategoryButtons.forEach((otherButton) => {
            if (otherButton !== button) {
                setFollowUpButtonState(otherButton, false);
            }
        });
    }

    setFollowUpButtonState(button, !button.classList.contains('is-selected'));
    updateSelectedSummary();
});

followUpSubmit.addEventListener('click', async () => {
    const supplementalSelections = collectSupplementalSelections();

    if (!Object.keys(supplementalSelections).length) {
        alert('보완 입력에서 하나 이상 선택해 주세요.');
        return;
    }

    await requestAnalysis({ supplementalSelections, phase: 'followup' });
});

analyzeBtn.addEventListener('click', async () => {
    beginNewAnalysisSession();
    await requestAnalysis({ phase: 'initial' });
});

async function requestAnalysis({ supplementalSelections = {}, phase = 'initial' } = {}) {
    const profile = profileEl.value.trim();

    if (!profile) {
        alert('프로필을 입력해주세요.');
        return;
    }

    analysisSessionState = phase;

    clearFollowUpTimeout();
    showLoading(true);
    errorAlert.classList.add('hidden');

    try {
        const response = await fetch(API_URL, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                profile,
                supplemental_selections: supplementalSelections,
                analysis_session_id: analysisSessionId,
                analysis_phase: phase,
            })
        });

        const result = await response.json();

        if (result.status !== 'success') {
            throw new Error(result.error || '분석 중 오류가 발생했습니다.');
        }

        const report = result.data || {};
        const followUpQuestions = Array.isArray(report.follow_up_questions) ? report.follow_up_questions : [];
        const hasSupplementalSelections = Object.keys(supplementalSelections).length > 0;

        if (!hasSupplementalSelections && followUpQuestions.length > 0) {
            renderFollowUpQuestions(followUpQuestions);
            setActiveStep(2);
            showPage('followup');
            return;
        }

        renderResults(report);
        hideFollowUpQuestions();
        closeAnalysisSession();
        setActiveStep(3);
        showPage('result');
    } catch (err) {
        showError(err.message);
    } finally {
        showLoading(false);
    }
}

function showLoading(isLoading) {
    loadingEl.classList.toggle('hidden', !isLoading);
    analyzeBtn.disabled = isLoading;
    followUpSubmit.disabled = isLoading;

    if (isLoading) {
        analyzeBtn.innerHTML = '<span class="btn-spinner"></span> 분석 중...';
    } else {
        analyzeBtn.innerHTML = '<i data-lucide="search-check" class="h-5 w-5"></i> 분석 시작하기';
    }

    lucide.createIcons();
}

function showError(msg) {
    errorMessage.textContent = msg;
    errorAlert.classList.remove('hidden');
}

function renderResults(report) {
    const institutions = Array.isArray(report?.recommended_institutions) ? report.recommended_institutions : [];
    const matchMessage = report?.match_message || '';

    resultGrid.innerHTML = '';
    resultTableBody.innerHTML = '';
    resultSummary.innerHTML = '';
    matchCountEl.textContent = institutions.length;
    resultTableContainer.classList.add('hidden');

    if (!institutions.length) {
        resultSummary.innerHTML = buildSummaryPanel({
            title: '추천 결과가 없습니다',
            description: matchMessage || '입력한 프로필과 현재 수집된 공고 사이의 매칭 점수가 충분하지 않습니다.',
            icon: 'search-x'
        });

        const emptyCard = document.createElement('div');
        emptyCard.className = 'md:col-span-2 xl:col-span-3 rounded-3xl border border-amber-200 bg-amber-50 p-8 text-center fade-in-up';
        emptyCard.innerHTML = `
            <div class="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-2xl border border-amber-200 bg-white text-amber-600">
                <i data-lucide="search-x" class="h-7 w-7"></i>
            </div>
            <h3 class="mb-2 text-xl font-black text-slate-950">매칭되는 기관이 없습니다</h3>
            <p class="text-slate-600">${escapeHtml(matchMessage || '매칭률이 50%를 초과하는 기관이 없습니다.')}</p>
        `;

        resultGrid.appendChild(emptyCard);
        lucide.createIcons();
        return;
    }

    const topScore = getMatchRate(institutions[0]);
    const totalFiles = institutions.reduce((sum, item) => sum + getRelatedFiles(item).length, 0);
    const topKeywords = collectTopKeywords(institutions);

    resultSummary.innerHTML = `
        <div class="summary-panel">
            <div class="grid grid-cols-1 gap-6 lg:grid-cols-[1.2fr_0.8fr] lg:items-center">
                <div>
                    <p class="section-eyebrow">Analysis Summary</p>
                    <h3 class="mt-2 mb-3 text-3xl font-black text-slate-950">맞춤형 추천 결과가 생성되었습니다</h3>
                    <p class="leading-8 text-slate-600">
                        입력한 프로필과 선택 조건을 기준으로 공공기관 채용공고 Wiki를 비교하여
                        상위 매칭 기관을 정리했습니다.
                    </p>
                </div>

                <div class="grid grid-cols-3 gap-3">
                    <div class="summary-metric">
                        <p class="text-2xl font-black text-slate-950">${institutions.length}</p>
                        <p class="mt-1 text-xs text-slate-500">추천 기관</p>
                    </div>
                    <div class="summary-metric">
                        <p class="text-2xl font-black text-blue-700">${topScore}%</p>
                        <p class="mt-1 text-xs text-slate-500">최고 매칭률</p>
                    </div>
                    <div class="summary-metric">
                        <p class="text-2xl font-black text-slate-950">${totalFiles}</p>
                        <p class="mt-1 text-xs text-slate-500">관련 공고</p>
                    </div>
                </div>
            </div>

            ${topKeywords.length ? `
                <div class="mt-6 border-t border-slate-200 pt-6">
                    <p class="mb-3 text-sm font-black text-slate-700">주요 매칭 키워드</p>
                    <div class="flex flex-wrap gap-2">
                        ${topKeywords.map((keyword) => `<span class="keyword-tag"># ${escapeHtml(keyword)}</span>`).join('')}
                    </div>
                </div>
            ` : ''}
        </div>
    `;

    institutions.forEach((item, index) => {
        const delay = index * 0.08;
        const relatedFiles = getRelatedFiles(item);
        const keywords = getKeywords(item);
        const matchRate = getMatchRate(item);
        const reasons = buildRecommendationReasons(item, relatedFiles, keywords);
        const institutionName = item.institution || '기관명 없음';

        const fileButtons = relatedFiles.map((fileName) => `
            <button type="button"
                data-analysis-file="${escapeAttr(fileName)}"
                data-institution="${escapeAttr(institutionName)}"
                class="file-button">
                <i data-lucide="file-text" class="h-3.5 w-3.5 shrink-0"></i>
                <span class="text-left">${escapeHtml(fileName)}</span>
            </button>
        `).join('');

        const tags = keywords.length
            ? keywords.map((keyword) => `<span class="keyword-tag"># ${escapeHtml(keyword)}</span>`).join('')
            : '<span class="text-sm text-slate-400">표시할 키워드가 없습니다.</span>';

        const card = document.createElement('article');
        card.className = 'result-card fade-in-up';
        card.style.animationDelay = `${delay}s`;

        card.innerHTML = `
            <div class="mb-5 flex items-start justify-between gap-4">
                <div>
                    <span class="rank-badge">
                        <i data-lucide="award" class="h-3.5 w-3.5"></i>
                        TOP ${index + 1}
                    </span>
                    <h3 class="mt-3 text-xl font-black text-slate-950">${escapeHtml(institutionName)}</h3>
                </div>

                <div class="text-right">
                    <p class="text-3xl font-black text-blue-700">${matchRate}%</p>
                    <p class="text-xs font-bold text-slate-400">매칭률</p>
                </div>
            </div>

            <div class="mb-5 h-2 w-full overflow-hidden rounded-full bg-slate-100">
                <div class="h-full rounded-full bg-gradient-to-r from-blue-700 to-sky-400" style="width: ${Math.min(matchRate, 100)}%"></div>
            </div>

            <div class="mb-5">
                <p class="mb-3 text-xs font-black uppercase tracking-[0.18em] text-slate-400">Matched Keywords</p>
                <div class="flex flex-wrap gap-2">${tags}</div>
            </div>

            <div class="reason-box mb-5">
                <p class="mb-3 text-xs font-black uppercase tracking-[0.18em] text-blue-700">추천 이유</p>
                <ul class="reason-list">
                    ${reasons.map((reason) => `<li>${escapeHtml(reason)}</li>`).join('')}
                </ul>
            </div>

            <div class="mt-auto border-t border-slate-200 pt-4">
                <div class="mb-3 flex items-center justify-between gap-3">
                    <span class="text-xs font-black uppercase tracking-[0.18em] text-slate-400">관련 공고</span>
                    <span class="text-xs font-bold text-slate-500">${relatedFiles.length}개</span>
                </div>

                <div class="flex flex-wrap gap-2">
                    ${fileButtons || '<span class="text-sm text-slate-400">연결된 공고가 없습니다.</span>'}
                </div>
            </div>
        `;

        resultGrid.appendChild(card);
        appendComparisonRow(item, index, relatedFiles, keywords, matchRate);
    });

    resultTableContainer.classList.remove('hidden');
    lucide.createIcons();
}

function renderFollowUpQuestions(questions) {
    followUpGrid.innerHTML = '';

    if (!Array.isArray(questions) || questions.length === 0) {
        hideFollowUpQuestions();
        return;
    }

    startFollowUpTimeout();

    questions.forEach((question) => {
        const card = document.createElement('div');
        card.className = 'rounded-3xl border border-slate-200 bg-white p-5 fade-in-up';

        const options = Array.isArray(question.options) ? question.options : [];
        const optionButtons = options.map((option) => {
            const value = typeof option === 'string' ? option : (option?.value || option?.label || '');
            const label = typeof option === 'string' ? option : (option?.label || option?.value || '');
            const count = typeof option === 'object' && option && Number.isFinite(option.count) ? option.count : null;
            const countBadge = count !== null ? `<span class="ml-2 text-[11px] text-slate-400">${count}개</span>` : '';

            return `
                <button type="button"
                    data-followup-category="${escapeAttr(question.category)}"
                    data-followup-value="${escapeAttr(value)}"
                    data-followup-label="${escapeAttr(label)}"
                    data-multi-select="${question.multi_select ? 'true' : 'false'}"
                    class="followup-option">
                    <span>${escapeHtml(label)}</span>
                    ${countBadge}
                </button>
            `;
        }).join('');

        card.innerHTML = `
            <div class="mb-4">
                <p class="section-eyebrow">${escapeHtml(question.title || question.category || '조건 선택')}</p>
                <h4 class="mt-2 text-xl font-black text-slate-950">
                    ${escapeHtml(question.prompt || '추가 조건을 선택해 주세요.')}
                </h4>
                <p class="mt-2 text-sm text-slate-500">
                    ${question.multi_select ? '여러 개 선택할 수 있습니다.' : '하나만 선택할 수 있습니다.'}
                </p>
            </div>

            <div class="flex flex-wrap gap-2">
                ${optionButtons}
            </div>
        `;

        followUpGrid.appendChild(card);
    });

    updateSelectedSummary();
    lucide.createIcons();
}

function hideFollowUpQuestions() {
    clearFollowUpTimeout();
    followUpGrid.innerHTML = '';
    followUpSummary.textContent = '선택지를 고르면 추천을 다시 계산합니다.';
    selectedSummaryCard.classList.add('hidden');
    selectedSummaryList.innerHTML = '';
}

function resetAnalysisView(message = '') {
    clearFollowUpTimeout();

    analysisSessionId = '';
    analysisSessionState = 'idle';

    resultGrid.innerHTML = '';
    resultTableBody.innerHTML = '';
    resultSummary.innerHTML = '';
    matchCountEl.textContent = '0';

    resultTableContainer.classList.add('hidden');
    followUpGrid.innerHTML = '';
    selectedSummaryCard.classList.add('hidden');
    selectedSummaryList.innerHTML = '';
    loadingEl.classList.add('hidden');

    analyzeBtn.disabled = false;
    followUpSubmit.disabled = false;
    analyzeBtn.innerHTML = '<i data-lucide="search-check" class="h-5 w-5"></i> 분석 시작하기';

    lucide.createIcons();

    if (message) {
        showError(message);
    } else {
        errorAlert.classList.add('hidden');
    }
}

function beginNewAnalysisSession() {
    analysisSessionId = createAnalysisSessionId();
    analysisSessionState = 'initial';

    clearFollowUpTimeout();

    resultGrid.innerHTML = '';
    resultTableBody.innerHTML = '';
    resultSummary.innerHTML = '';
    matchCountEl.textContent = '0';

    resultTableContainer.classList.add('hidden');
    hideFollowUpQuestions();
    errorAlert.classList.add('hidden');

    setActiveStep(1);
}

function closeAnalysisSession() {
    analysisSessionState = 'completed';
    clearFollowUpTimeout();
}

function createAnalysisSessionId() {
    if (window.crypto && typeof window.crypto.randomUUID === 'function') {
        return window.crypto.randomUUID();
    }

    return `session-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function startFollowUpTimeout() {
    clearFollowUpTimeout();
    followUpSummary.textContent = '선택한 항목을 반영해 더 구체적인 추천을 다시 계산합니다. 남은 시간: 05:00';

    const startedAt = Date.now();

    const tick = () => {
        const elapsed = Date.now() - startedAt;
        const remaining = Math.max(FOLLOW_UP_SESSION_TIMEOUT_MS - elapsed, 0);
        const minutes = String(Math.floor(remaining / 60000)).padStart(2, '0');
        const seconds = String(Math.floor((remaining % 60000) / 1000)).padStart(2, '0');

        followUpSummary.textContent = `선택한 항목을 반영해 더 구체적인 추천을 다시 계산합니다. 남은 시간: ${minutes}:${seconds}`;
    };

    tick();

    followUpTimeoutId = window.setInterval(() => {
        const elapsed = Date.now() - startedAt;

        if (elapsed >= FOLLOW_UP_SESSION_TIMEOUT_MS) {
            clearFollowUpTimeout();
            resetAnalysisView('분류 선택 시간이 5분을 초과해 초기 상태로 돌아갔습니다. 다시 분석해 주세요.');
            setActiveStep(1);
            showPage('analyze');
            return;
        }

        tick();
    }, 1000);
}

function clearFollowUpTimeout() {
    if (followUpTimeoutId !== null) {
        window.clearInterval(followUpTimeoutId);
        followUpTimeoutId = null;
    }
}

function setFollowUpButtonState(button, isSelected) {
    button.classList.toggle('is-selected', isSelected);
}

function collectSupplementalSelections() {
    const selections = {};

    followUpGrid.querySelectorAll('button[data-followup-category].is-selected').forEach((button) => {
        const category = button.dataset.followupCategory;
        const value = button.dataset.followupValue;

        if (!category || !value) {
            return;
        }

        if (!selections[category]) {
            selections[category] = [];
        }

        selections[category].push(value);
    });

    return selections;
}

function updateSelectedSummary() {
    const selectedButtons = Array.from(followUpGrid.querySelectorAll('button[data-followup-category].is-selected'));

    if (!selectedButtons.length) {
        selectedSummaryCard.classList.add('hidden');
        selectedSummaryList.innerHTML = '';
        return;
    }

    selectedSummaryList.innerHTML = selectedButtons.map((button) => {
        const category = button.dataset.followupCategory || '조건';
        const label = button.dataset.followupLabel || button.dataset.followupValue || '';

        return `<span class="summary-pill">${escapeHtml(category)}: ${escapeHtml(label)}</span>`;
    }).join('');

    selectedSummaryCard.classList.remove('hidden');
}

function openArchiveModal(analysisFile, institution) {
    archiveModalTitle.textContent = `${institution} 원문 공고`;
    archiveModalMeta.textContent = '원본 공고를 불러오는 중입니다...';
    archiveModalBody.textContent = '불러오는 중...';
    archiveModal.classList.remove('hidden');

    return fetch(ARCHIVE_API_URL, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ file: analysisFile })
    })
        .then(async (response) => {
            const result = await response.json();

            if (!response.ok || result.status !== 'success') {
                throw new Error(result.error || '원문 공고를 불러오지 못했습니다.');
            }

            const data = result.data;

            archiveModalTitle.textContent = `${institution} 원문 공고`;
            archiveModalMeta.textContent = `${data.raw_file} · ${analysisFile}`;
            archiveModalBody.textContent = data.archive;
        })
        .catch((err) => {
            archiveModalTitle.textContent = `${institution} 원문 공고`;
            archiveModalMeta.textContent = '불러오기에 실패했습니다.';
            archiveModalBody.textContent = err.message;
        });
}

function closeArchiveModal() {
    archiveModal.classList.add('hidden');
}

function setActiveStep(activeStep) {
    stepItems.forEach((item) => {
        const step = Number(item.dataset.step);

        item.classList.toggle('step-active', step === activeStep);
        item.classList.toggle('step-completed', step < activeStep);
    });
}

function getRelatedFiles(item) {
    if (Array.isArray(item.files) && item.files.length) {
        return item.files;
    }

    if (item.file) {
        return [item.file];
    }

    return [];
}

function getKeywords(item) {
    if (!Array.isArray(item.matched_keywords)) {
        return [];
    }

    return item.matched_keywords
        .map((keyword) => String(keyword || '').trim())
        .filter(Boolean);
}

function getMatchRate(item) {
    const rawScore = item.match_rate ?? item.score ?? 0;
    const score = Number(rawScore);

    if (!Number.isFinite(score)) {
        return 0;
    }

    return Math.max(0, Math.min(Math.round(score), 100));
}

function buildRecommendationReasons(item, relatedFiles, keywords) {
    const reasons = [];
    const institutionName = item.institution || '해당 기관';

    if (keywords.length) {
        reasons.push(`입력 프로필과 ${keywords.slice(0, 3).join(', ')} 키워드가 연결됩니다.`);
    }

    if (relatedFiles.length) {
        reasons.push(`${institutionName} 관련 공고 ${relatedFiles.length}개가 추천 근거로 사용되었습니다.`);
    }

    const score = getMatchRate(item);

    if (score >= 90) {
        reasons.push('사용자 조건과 공고 태그의 일치도가 매우 높습니다.');
    } else if (score >= 70) {
        reasons.push('사용자 조건과 공고 태그가 전반적으로 잘 맞습니다.');
    } else {
        reasons.push('일부 조건이 일치하여 후보 기관으로 분류되었습니다.');
    }

    return reasons;
}

function appendComparisonRow(item, index, relatedFiles, keywords, matchRate) {
    const row = document.createElement('tr');
    row.className = 'border-b border-slate-100';

    row.innerHTML = `
        <td class="py-4 pr-4 font-bold text-slate-500">TOP ${index + 1}</td>
        <td class="py-4 pr-4 font-black text-slate-950">${escapeHtml(item.institution || '기관명 없음')}</td>
        <td class="py-4 pr-4 font-black text-blue-700">${matchRate}%</td>
        <td class="py-4 pr-4 text-slate-600">${relatedFiles.length}개</td>
        <td class="py-4 pr-4 text-slate-500">
            ${keywords.length ? keywords.slice(0, 4).map((keyword) => `#${escapeHtml(keyword)}`).join(' ') : '-'}
        </td>
    `;

    resultTableBody.appendChild(row);
}

function collectTopKeywords(institutions) {
    const counts = new Map();

    institutions.forEach((item) => {
        const keywords = getKeywords(item);

        keywords.forEach((keyword) => {
            counts.set(keyword, (counts.get(keyword) || 0) + 1);
        });
    });

    return Array.from(counts.entries())
        .sort((a, b) => b[1] - a[1])
        .slice(0, 8)
        .map(([keyword]) => keyword);
}

function buildSummaryPanel({ title, description, icon }) {
    return `
        <div class="summary-panel">
            <div class="flex items-start gap-4">
                <div class="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl bg-blue-50 text-blue-700">
                    <i data-lucide="${icon}" class="h-6 w-6"></i>
                </div>
                <div>
                    <h3 class="mb-2 text-xl font-black text-slate-950">${escapeHtml(title)}</h3>
                    <p class="leading-7 text-slate-600">${escapeHtml(description)}</p>
                </div>
            </div>
        </div>
    `;
}

function escapeHtml(value) {
    return String(value ?? '')
        .replaceAll('&', '&amp;')
        .replaceAll('<', '&lt;')
        .replaceAll('>', '&gt;')
        .replaceAll('"', '&quot;')
        .replaceAll("'", '&#039;');
}

function escapeAttr(value) {
    return escapeHtml(value).replaceAll('`', '&#096;');
}
