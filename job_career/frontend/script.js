const API_BASE = window.location.origin;
const API_URL = `${API_BASE}/api/analyze`;
const ARCHIVE_API_URL = `${API_BASE}/api/archive`;

const profileEl = document.getElementById('profile');
const analyzeBtn = document.getElementById('analyzeBtn');
const resetBtn = document.getElementById('resetBtn');
const loadExampleBtn = document.getElementById('loadExample');
const loadingEl = document.getElementById('loading');
const resultContainer = document.getElementById('resultContainer');
const resultGrid = document.getElementById('resultGrid');
const followUpContainer = document.getElementById('followUpContainer');
const followUpSummary = document.getElementById('followUpSummary');
const followUpGrid = document.getElementById('followUpGrid');
const followUpSubmit = document.getElementById('followUpSubmit');
const matchCountEl = document.getElementById('matchCount');
const errorAlert = document.getElementById('errorAlert');
const errorMessage = document.getElementById('errorMessage');
const archiveModal = document.getElementById('archiveModal');
const archiveModalTitle = document.getElementById('archiveModalTitle');
const archiveModalMeta = document.getElementById('archiveModalMeta');
const archiveModalBody = document.getElementById('archiveModalBody');
const archiveModalClose = document.getElementById('archiveModalClose');

let currentProfile = '';
let followUpTimeoutId = null;
let analysisSessionId = '';
let analysisSessionState = 'idle';

const FOLLOW_UP_NONE_LABEL = '상관없음';
const FOLLOW_UP_NONE_VALUE = '__none__';
const FOLLOW_UP_SESSION_TIMEOUT_MS = 5 * 60 * 1000;

// 예시 텍스트 리스트
const EXAMPLE_PROFILE = "저는 3년 동안 병원에서 원무과 행정 직원으로 일했습니다. 환자 데이터를 다루다 보니 의료 행정 지식과 의료정보 보호 정책 수립 쪽에 관심이 생겼고, 관련 경험도 쌓았습니다. 공공기관 쪽으로 이직하고 싶습니다.";

loadExampleBtn.addEventListener('click', () => {
    profileEl.value = EXAMPLE_PROFILE;
    profileEl.focus();
});

resetBtn.addEventListener('click', () => {
    profileEl.value = '';
    resetAnalysisView();
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
    const isNoneOption = button.dataset.followupValue === FOLLOW_UP_NONE_VALUE;

    if (isNoneOption) {
        followUpGrid.querySelectorAll(`button[data-followup-category="${category}"]`).forEach((otherButton) => {
            setFollowUpButtonState(otherButton, otherButton === button);
        });
        return;
    }

    if (!multiSelect) {
        followUpGrid.querySelectorAll(`button[data-followup-category="${category}"]`).forEach((otherButton) => {
            if (otherButton !== button) {
                setFollowUpButtonState(otherButton, false);
            }
        });
    } else {
        const noneButton = followUpGrid.querySelector(`button[data-followup-category="${category}"][data-followup-value="${FOLLOW_UP_NONE_VALUE}"]`);
        if (noneButton) {
            setFollowUpButtonState(noneButton, false);
        }
    }

    setFollowUpButtonState(button, !button.classList.contains('is-selected'));
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

    currentProfile = profile;
    analysisSessionState = phase;

    clearFollowUpTimeout();

    // UI 초기화 및 로딩 시작
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

        if (result.status === 'success') {
            const report = result.data || {};
            renderResults(report);
            if (Object.keys(supplementalSelections).length) {
                hideFollowUpQuestions();
                closeAnalysisSession();
            } else {
                renderFollowUpQuestions(report.follow_up_questions || []);
            }
        } else {
            throw new Error(result.error || '분석 중 오류가 발생했습니다.');
        }
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
    if (isLoading) analyzeBtn.innerHTML = `<i class="animate-spin w-5 h-5 border-2 border-white/20 border-t-white rounded-full"></i> 분석 중...`;
    else analyzeBtn.innerHTML = `<i data-lucide="zap" class="w-5 h-5"></i> 분석 시작하기`;
    lucide.createIcons();
}

function showError(msg) {
    errorMessage.textContent = msg;
    errorAlert.classList.remove('hidden');
}

function renderResults(report) {
    const institutions = Array.isArray(report?.recommended_institutions) ? report.recommended_institutions : [];
    const matchMessage = report?.match_message || '';
    const isWaitingForFollowUp = Array.isArray(report?.follow_up_questions) && report.follow_up_questions.length > 0;

    resultGrid.innerHTML = '';
    matchCountEl.textContent = institutions.length;

    if (!institutions.length) {
        const emptyCard = document.createElement('div');
        emptyCard.className = 'md:col-span-2 rounded-3xl border border-amber-500/20 bg-amber-500/5 p-6 text-center';
        emptyCard.innerHTML = `
            <div class="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-full bg-amber-500/10 text-amber-300">
                <i data-lucide="search-x" class="w-7 h-7"></i>
            </div>
            <h3 class="text-xl font-bold text-white mb-2">${isWaitingForFollowUp ? '분류 선택 후 추천을 제공합니다' : '매칭되는 기업이 없습니다'}</h3>
            <p class="text-slate-300">${matchMessage || (isWaitingForFollowUp ? '조금 더 조건을 정리해 주시면 추천을 다시 계산할 수 있어요.' : '조건에 맞는 추천 공고를 아직 찾지 못했습니다. 핵심 조건을 조금 넓혀 다시 시도해 주세요.')}</p>
        `;
        resultGrid.appendChild(emptyCard);
        resultContainer.classList.remove('hidden');
        lucide.createIcons();
        resultContainer.scrollIntoView({ behavior: 'smooth', block: 'start' });
        return;
    }

    institutions.forEach((item, index) => {
        const delay = index * 0.1; // 순차적 애니메이션
        const relatedFiles = Array.isArray(item.files) && item.files.length
            ? item.files
            : (item.file ? [item.file] : []);
        const fileButtons = relatedFiles.map((fileName, fileIndex) => `
            <button type="button" data-analysis-file="${fileName}" data-institution="${item.institution}" class="inline-flex items-center gap-2 px-3 py-2 rounded-xl border text-xs transition-colors break-all ${fileIndex === 0 ? 'bg-indigo-500/15 text-indigo-100 border-indigo-500/30 hover:bg-indigo-500/25' : 'bg-slate-800/40 text-slate-200 border-slate-700/60 hover:bg-slate-800/70'}">
                <i data-lucide="file-text" class="w-3 h-3 shrink-0"></i>
                <span class="text-left">${fileName}</span>
            </button>
        `).join('');
        const card = document.createElement('div');
        card.className = 'glass p-6 rounded-2xl border border-slate-700/50 card-hover fade-in-up';
        card.style.animationDelay = `${delay}s`;
        
        // 매칭 키워드 태그 생성
        const tags = item.matched_keywords.map(kw => 
            `<span class="px-2 py-1 bg-emerald-500/10 text-emerald-400 text-xs rounded-lg border border-emerald-500/20"># ${kw}</span>`
        ).join('');
        const rankLabel = Number.isFinite(Number(item.rank)) && Number(item.rank) > 0 ? `${item.rank}순위` : `${index + 1}순위`;
        const rawScoreLabel = Number.isFinite(Number(item.raw_score)) ? `가중 점수 ${Number(item.raw_score).toFixed(2)}` : '';

        card.innerHTML = `
            <div class="flex justify-between items-start mb-4">
                <h3 class="text-xl font-bold text-white">${item.institution}</h3>
                <div class="flex flex-col items-end">
                    <span class="text-indigo-400 text-sm font-bold">${rankLabel}</span>
                    ${rawScoreLabel ? `<span class="text-xs text-slate-400 mt-1">${rawScoreLabel}</span>` : ''}
                </div>
            </div>
            <div class="flex flex-wrap gap-2 mb-6">
                ${tags}
            </div>
            <div class="space-y-3 mt-auto pt-4 border-t border-slate-700/50">
                <div class="flex items-center justify-between gap-3">
                    <span class="text-xs uppercase tracking-[0.18em] text-slate-500">관련 공고</span>
                    <span class="text-xs text-slate-400">${relatedFiles.length}개</span>
                </div>
                <div class="flex flex-wrap gap-2">
                    ${fileButtons}
                </div>
            </div>
        `;
        resultGrid.appendChild(card);
    });
    
    resultContainer.classList.remove('hidden');
    lucide.createIcons();
    
    // 결과창으로 부드럽게 스크롤
    resultContainer.scrollIntoView({ behavior: 'smooth', block: 'start' });
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
        card.className = 'rounded-2xl border border-slate-700/60 bg-slate-900/60 p-4';

        const options = Array.isArray(question.options) ? question.options : [];
        const optionButtons = options.map((option) => {
            const value = typeof option === 'string' ? option : (option?.value || option?.label || '');
            const label = typeof option === 'string' ? option : (option?.label || option?.value || '');
            const count = typeof option === 'object' && option && Number.isFinite(option.count) ? option.count : null;
            const countBadge = count !== null ? `<span class="ml-2 text-[11px] text-slate-400">${count}개</span>` : '';

            return `
                <button type="button" data-followup-category="${question.category}" data-followup-value="${value}" data-multi-select="${question.multi_select ? 'true' : 'false'}" class="followup-option inline-flex items-center rounded-full border border-slate-700 bg-slate-800/50 px-3 py-2 text-sm text-slate-200 transition-colors hover:border-slate-500 hover:bg-slate-800">
                    <span>${label}</span>
                    ${countBadge}
                </button>
            `;
        }).join('');

        card.innerHTML = `
            <div class="mb-4">
                <p class="text-xs uppercase tracking-[0.28em] text-emerald-400 mb-2">${question.title || question.category}</p>
                <h4 class="text-lg font-semibold text-white">${question.prompt || '추가 조건을 선택해 주세요.'}</h4>
            </div>
            <div class="flex flex-wrap gap-2">${optionButtons}</div>
        `;

        followUpGrid.appendChild(card);
    });

    followUpContainer.classList.remove('hidden');
    lucide.createIcons();
    followUpContainer.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

function hideFollowUpQuestions() {
    clearFollowUpTimeout();
    followUpGrid.innerHTML = '';
    followUpSummary.textContent = '선택지를 고르면 추천을 다시 계산합니다.';
    followUpContainer.classList.add('hidden');
}

function resetAnalysisView(message = '') {
    clearFollowUpTimeout();
    currentProfile = '';
    analysisSessionId = '';
    analysisSessionState = 'idle';
    resultGrid.innerHTML = '';
    matchCountEl.textContent = '0';
    resultContainer.classList.add('hidden');
    followUpGrid.innerHTML = '';
    followUpContainer.classList.add('hidden');
    loadingEl.classList.add('hidden');
    analyzeBtn.disabled = false;
    followUpSubmit.disabled = false;
    analyzeBtn.innerHTML = `<i data-lucide="zap" class="w-5 h-5"></i> 분석 시작하기`;
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
    matchCountEl.textContent = '0';
    resultContainer.classList.add('hidden');
    hideFollowUpQuestions();
    errorAlert.classList.add('hidden');
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
    followUpSummary.textContent = `선택한 항목을 반영해 더 구체적인 추천을 다시 계산합니다. 남은 시간: 05:00`;

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
    button.classList.toggle('border-emerald-400/50', isSelected);
    button.classList.toggle('bg-emerald-500/15', isSelected);
    button.classList.toggle('text-emerald-100', isSelected);
    button.classList.toggle('border-slate-700', !isSelected);
    button.classList.toggle('bg-slate-800/50', !isSelected);
    button.classList.toggle('text-slate-200', !isSelected);
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

function openArchiveModal(analysisFile, institution) {
    archiveModalTitle.textContent = `${institution} 원문 공고`;
    archiveModalMeta.textContent = '원본 공고(아카이브) 섹션을 불러오는 중입니다...';
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
