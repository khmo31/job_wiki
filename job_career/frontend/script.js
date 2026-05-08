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
const matchCountEl = document.getElementById('matchCount');
const errorAlert = document.getElementById('errorAlert');
const errorMessage = document.getElementById('errorMessage');
const archiveModal = document.getElementById('archiveModal');
const archiveModalTitle = document.getElementById('archiveModalTitle');
const archiveModalMeta = document.getElementById('archiveModalMeta');
const archiveModalBody = document.getElementById('archiveModalBody');
const archiveModalClose = document.getElementById('archiveModalClose');

// 예시 텍스트 리스트
const EXAMPLE_PROFILE = "저는 3년 동안 병원에서 원무과 행정 직원으로 일했습니다. 환자 데이터를 다루다 보니 의료 행정 지식과 의료정보 보호 정책 수립 쪽에 관심이 생겼고, 관련 경험도 쌓았습니다. 공공기관 쪽으로 이직하고 싶습니다.";

loadExampleBtn.addEventListener('click', () => {
    profileEl.value = EXAMPLE_PROFILE;
    profileEl.focus();
});

resetBtn.addEventListener('click', () => {
    profileEl.value = '';
    resultContainer.classList.add('hidden');
    errorAlert.classList.add('hidden');
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

analyzeBtn.addEventListener('click', async () => {
    const profile = profileEl.value.trim();
    
    if (!profile) {
        alert('프로필을 입력해주세요.');
        return;
    }

    // UI 초기화 및 로딩 시작
    showLoading(true);
    resultContainer.classList.add('hidden');
    errorAlert.classList.add('hidden');

    try {
        const response = await fetch(API_URL, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ profile })
        });

        const result = await response.json();

        if (result.status === 'success') {
            renderResults(result.data.recommended_institutions);
        } else {
            throw new Error(result.error || '분석 중 오류가 발생했습니다.');
        }
    } catch (err) {
        showError(err.message);
    } finally {
        showLoading(false);
    }
});

function showLoading(isLoading) {
    loadingEl.classList.toggle('hidden', !isLoading);
    analyzeBtn.disabled = isLoading;
    if (isLoading) analyzeBtn.innerHTML = `<i class="animate-spin w-5 h-5 border-2 border-white/20 border-t-white rounded-full"></i> 분석 중...`;
    else analyzeBtn.innerHTML = `<i data-lucide="zap" class="w-5 h-5"></i> 분석 시작하기`;
    lucide.createIcons();
}

function showError(msg) {
    errorMessage.textContent = msg;
    errorAlert.classList.remove('hidden');
}

function renderResults(institutions) {
    resultGrid.innerHTML = '';
    matchCountEl.textContent = institutions.length;
    
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

        card.innerHTML = `
            <div class="flex justify-between items-start mb-4">
                <h3 class="text-xl font-bold text-white">${item.institution}</h3>
                <div class="flex flex-col items-end">
                    <span class="text-indigo-400 text-sm font-bold">${item.score}점</span>
                    <div class="w-16 h-1 bg-slate-700 rounded-full mt-1 overflow-hidden">
                        <div class="h-full bg-indigo-500" style="width: ${Math.min(item.score * 7, 100)}%"></div>
                    </div>
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
