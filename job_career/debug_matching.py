#!/usr/bin/env python
"""Debug wiki matching logic"""
from pathlib import Path
import json
import re

profile = '저는 3년 동안 병원에서 원무과 행정 직원으로 일했습니다. 환자 데이터를 다루다 보니 의료 행정 지식과 의료정보 보호 정책 수립 쪽에 관심이 생겼고, 관련 경험도 쌓았습니다. 공공기관 쪽으로 이직하고 싶습니다.'

# 키워드 추출
keywords = ['병원', '행정', '의료', '의료정보', '의료정보 보호 정책 수립', '공공기관', '개인정보', '보안']
print('프로필 키워드:', keywords)

# Wiki 파일 로드
wiki_root = Path('c:/Users/khmo/Desktop/coding/job_wiki/10_Wiki/Analysis')
wiki_files = sorted(wiki_root.glob('*.md'))
print(f'\n찾은 Wiki 파일: {len(wiki_files)}개\n')

# 각 파일 매칭 스코어 계산
scores = []
for wiki_file in wiki_files[:3]:  # 처음 3개만 확인
    try:
        content = wiki_file.read_text(encoding='utf-8', errors='ignore')
    except:
        content = ""
    
    score = 0
    matched_keywords = []
    
    for kw in keywords:
        if kw in content:
            score += 1
            matched_keywords.append(kw)
    
    # 특정 키워드로 추가 점수
    if '병원' in wiki_file.name or '병원' in content:
        score += 1
    if '의료' in content:
        score += 1
    if '행정' in content:
        score += 1
    
    scores.append((score, wiki_file.name, matched_keywords))
    print(f'{wiki_file.name}')
    print(f'  점수: {score}')
    print(f'  매칭 키워드: {matched_keywords}')
    print(f'  파일 크기: {len(content)} bytes')
    print()

# 점수순 정렬
scores.sort(key=lambda x: -x[0])
print('\n상위 3개 (점수순):')
for score, fname, matched in scores[:3]:
    print(f'  {score:>2} 점 - {fname} ({", ".join(matched)})')
