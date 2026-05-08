import sys, os, pathlib
ROOT = pathlib.Path(__file__).resolve().parent.parent
SCRIPTS_DIR = pathlib.Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import os
import json
import re
from typing import List

import config
from analyzer import extract_skills_and_reasoning, preprocess_text
from formatter import render_markdown


RAW_DIR = os.path.join(str(config.BASE_DIR), config.RAW_DIR)


def parse_frontmatter(md_text: str) -> dict:
    m = re.match(r"^---\n(.*?)\n---\n", md_text, flags=re.S)
    res = {}
    if not m:
        return res
    body = m.group(1)
    for line in body.splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            res[k.strip()] = v.strip()
    return res


def extract_sections(md_text: str) -> dict:
    out = {"summary": "", "requirements": ""}
    m = re.search(r"##\s*요약\s*(.*?)##\s*Matching Reasoning", md_text, flags=re.S)
    if m:
        out["summary"] = m.group(1).strip()
    m2 = re.search(r"Original Requirements:\s*(.*)$", md_text, flags=re.S)
    if m2:
        out["requirements"] = m2.group(1).strip()
    return out


def baseline_analyze(text: str, user_interests: List[str], top_n: int = 4):
    # recreate baseline analyzer behavior (pre-tuning)
    BASE_PATTERNS = {
        "아두이노": [r"아두이노", r"arduino"],
        "시리얼 통신": [r"시리얼", r"Serial", r"UART"],
        "PLC": [r"PLC"],
        "자동화 알고리즘": [r"자동화 알고리즘", r"자동화 로직", r"제어 알고리즘", r"제어 로직"],
        "C/C++": [r"C\\+\\+", r"\\bC\\b"],
        "Python": [r"Python", r"파이썬"],
        "센서": [r"센서", r"sensor"],
        "데이터 로깅": [r"데이터 로깅", r"로깅", r"데이터 수집"],
        "ROS": [r"ROS"],
        "임베디드": [r"임베디드", r"embedded"],
    }
    text = preprocess_text(text)
    scores = {}
    for skill, patterns in BASE_PATTERNS.items():
        score = 0
        evidence = None
        for p in patterns:
            hits = re.findall(p, text, flags=re.I)
            if hits:
                score += len(hits)
                if not evidence:
                    m = re.search(r"([^.\n]{0,200}" + p + r"[^.\n]{0,200})", text, flags=re.I)
                    evidence = m.group(0) if m else None
        if evidence and any(w in evidence for w in ["주요", "담당", "필수", "요구", "우대"]):
            score += 2
        scores[skill] = {"score": score, "evidence": evidence}

    INTEREST_MAP = {
        "아두이노": ["아두이노", "임베디드"],
        "공장 게임": ["자동화 알고리즘", "PLC", "데이터 로깅", "시리얼 통신", "센서"],
        "자동화 로직": ["자동화 알고리즘", "PLC", "임베디드", "C/C++"],
    }
    for interest in user_interests:
        related = INTEREST_MAP.get(interest, [])
        for r in related:
            if r in scores:
                scores[r]["score"] += 3

    items = sorted(scores.items(), key=lambda kv: kv[1]["score"], reverse=True)
    selected = [k for k, v in items if v["score"] > 0][:top_n]
    if not selected:
        selected = [k for k, _ in items][:top_n]
    reasoning = {s: (scores[s].get("evidence") or "공고에서 관련 표현이 발견됨") for s in selected}
    return selected, reasoning


def reanalyze_limit(limit: int = 10) -> dict:
    files = [f for f in os.listdir(RAW_DIR) if f.endswith(".md")]
    files.sort()
    report = {"files": [], "metrics": {}}
    processed = 0
    baseline_links = {}
    new_links = {}
    for fn in files:
        if processed >= limit:
            break
        path = os.path.join(RAW_DIR, fn)
        with open(path, "r", encoding="utf-8") as fh:
            md = fh.read()

        fm = parse_frontmatter(md)
        secs = extract_sections(md)
        job = {
            "title": fm.get("title", os.path.splitext(fn)[0]),
            "company": fm.get("company", ""),
            "posted_date": fm.get("date", ""),
            "description": secs.get("summary", ""),
            "requirements": secs.get("requirements", ""),
            "ncs_nm": fm.get("ncs_nm", ""),
            "raw": None,
        }
        text = (job.get("description", "") or "") + "\n" + (job.get("requirements", "") or "")

        base_skills, base_reason = baseline_analyze(text, config.USER_INTERESTS, top_n=config.TOP_N_SKILLS)
        new_skills, new_reason = extract_skills_and_reasoning(text, config.USER_INTERESTS, top_n=config.TOP_N_SKILLS, ncs=job.get("ncs_nm"))

        baseline_links[fn] = base_skills
        new_links[fn] = new_skills

        new_md = render_markdown(job, new_skills, new_reason, interests=config.USER_INTERESTS)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(new_md)

        report["files"].append({"file": path, "before": base_skills, "after": new_skills})
        processed += 1

    F = processed
    S_base = set(s for skills in baseline_links.values() for s in skills)
    S_new = set(s for skills in new_links.values() for s in skills)
    E_base = sum(len(skills) for skills in baseline_links.values())
    E_new = sum(len(skills) for skills in new_links.values())
    R_base = (E_base / (F * len(S_base))) if F and S_base else 0.0
    R_new = (E_new / (F * len(S_new))) if F and S_new else 0.0

    report["metrics"] = {
        "files_processed": F,
        "baseline": {"unique_skills": len(S_base), "edges": E_base, "R": R_base},
        "new": {"unique_skills": len(S_new), "edges": E_new, "R": R_new},
    }
    return report


if __name__ == "__main__":
    out = reanalyze_limit(10)
    print(json.dumps(out, ensure_ascii=False, indent=2))
