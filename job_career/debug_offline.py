#!/usr/bin/env python
"""Debug offline fallback"""
import sys
sys.path.insert(0, 'src')

from pathlib import Path
import re

user_profile = "저는 3년 동안 병원에서 원무과 행정 직원으로 일했습니다. 환자 데이터를 다루다 보니 의료 행정 지식과 의료정보 보호 정책 수립 쪽에 관심이 생겼고, 관련 경험도 쌓았습니다. 공공기관 쪽으로 이직하고 싶습니다."

# Wiki 경로
wiki_root = Path(__file__).resolve().parents[0].parent / "job_wiki" / "10_Wiki" / "Analysis"
print(f"Wiki root: {wiki_root}")
print(f"Exists: {wiki_root.exists()}\n")

wiki_files = sorted(wiki_root.glob("*.md")) if wiki_root.exists() else []
print(f"Found {len(wiki_files)} files\n")

# 첫 3개 파일 스코링
scored_files = []
for wiki_file in wiki_files[:3]:
    try:
        content = wiki_file.read_text(encoding="utf-8", errors="ignore")
    except Exception as e:
        print(f"Error reading {wiki_file.name}: {e}")
        content = ""
    
    score = 0
    
    # 프로필 키워드 직접 매칭
    keywords = ["병원", "의료", "행정", "개인정보", "보안", "공공", "정보보호", "공단", "연구원"]
    matched_kws = []
    for kw in keywords:
        if kw in user_profile and kw in content:
            score += 2
            matched_kws.append(f"{kw}(프로필+파일)")
        elif kw in content:
            score += 1
            matched_kws.append(f"{kw}(파일만)")
    
    # 파일명 기반
    if "병원" in wiki_file.stem:
        score += 2
    if any(token in wiki_file.stem for token in ["공단", "연구원", "공사", "위원회", "적십자사"]):
        score += 1
    
    company_match = re.search(r"company:\s*\"\[\[(.+?)\]\]\"", content)
    company_name = company_match.group(1) if company_match else wiki_file.stem.split("_")[1]
    
    scored_files.append((score, wiki_file.name, company_name, matched_kws))
    print(f"File: {wiki_file.name}")
    print(f"  Score: {score}")
    print(f"  Company: {company_name}")
    print(f"  Matched: {matched_kws}")
    print()

# 점수순 정렬
scored_files.sort(key=lambda x: -x[0])
print("Top 3 by score:")
for score, fname, company, matched in scored_files:
    print(f"  {score:>2} - {company} ({fname})")
