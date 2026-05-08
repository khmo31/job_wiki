import sys, os, pathlib
ROOT = pathlib.Path(__file__).resolve().parent.parent
SCRIPTS_DIR = pathlib.Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import os
import re
import json
from collections import Counter
from typing import List, Dict

import config

try:
    import seaborn as sns
except Exception:
    sns = None

import matplotlib.pyplot as plt


def _extract_frontmatter(md_text: str) -> str:
    parts = md_text.split("---")
    if len(parts) >= 3:
        return parts[1]
    m = re.search(r"^---\n(.*?)\n---\n", md_text, flags=re.S)
    return m.group(1) if m else ""


def _parse_skills_from_frontmatter(yaml_body: str) -> List[str]:
    # find skills: block and extract dash items
    m = re.search(r"(?m)^\s*skills:\s*\n(?P<block>(?:\s*-\s*.*\n?)*)", yaml_body)
    if not m:
        return []
    block = m.group("block")
    skills: List[str] = []
    for line in block.splitlines():
        line = line.strip()
        if not line.startswith("-"):
            continue
        val = line.lstrip("-").strip()
        if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
            val = val[1:-1]
        # remove [[...]] if present
        val = re.sub(r"\[\[(.*?)\]\]", r"\1", val)
        skills.append(val.strip())
    return skills


def _parse_basic_frontmatter_fields(yaml_body: str) -> Dict[str, str]:
    out: Dict[str, str] = {}
    for line in yaml_body.splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            out[k.strip()] = v.strip()
    return out


def main(limit: int | None = None, save_plots: bool = True) -> Dict:
    raw_dir = os.path.join(str(config.BASE_DIR), config.RAW_DIR)
    files = [f for f in os.listdir(raw_dir) if f.endswith(".md")]
    files.sort()
    if limit:
        files = files[:limit]

    skill_counts = Counter()
    file_skills = {}
    file_meta = {}

    for fn in files:
        path = os.path.join(raw_dir, fn)
        try:
            with open(path, "r", encoding="utf-8") as fh:
                md = fh.read()
        except Exception:
            continue
        yaml_body = _extract_frontmatter(md)
        skills = _parse_skills_from_frontmatter(yaml_body)
        skills_unique = []
        for s in skills:
            if s and s not in skills_unique:
                skills_unique.append(s)
        file_skills[fn] = skills_unique
        for s in skills_unique:
            skill_counts[s] += 1
        file_meta[fn] = _parse_basic_frontmatter_fields(yaml_body)

    unique_skills = list(skill_counts.keys())
    S = len(unique_skills) or 1

    # compute per-file R_i = deg(file)/S
    r_scores = {fn: (len(skills) / S) for fn, skills in file_skills.items()}

    # Top 10 skills
    top_skills = skill_counts.most_common(10)

    # prepare interest mapping (focus: 공장 게임, 자동화)
    INTEREST_MAP = {
        "아두이노": ["아두이노", "임베디드", "시리얼 통신"],
        "공장 게임": ["자원 배분", "물류", "재고 관리", "생산계획", "병목 분석", "시뮬레이션", "PLC", "데이터 로깅", "센서"],
        "자동화 로직": ["자동화 알고리즘", "PLC", "임베디드", "C/C++", "MES"],
    }

    # build interest skill set for user's interests (prefer '공장 게임' and '자동화 로직')
    interest_skills = set()
    for interest in ("공장 게임", "자동화 로직"):
        interest_skills.update(INTEREST_MAP.get(interest, []))

    # score files by intersection with interest_skills
    match_scores = []
    for fn, skills in file_skills.items():
        score = len(set(skills) & interest_skills)
        match_scores.append((fn, score, r_scores.get(fn, 0.0), skills))

    # top 3 matches
    match_scores.sort(key=lambda x: (x[1], x[2]), reverse=True)
    top3 = match_scores[:3]

    # Plotting
    os.makedirs(raw_dir, exist_ok=True)
    if top_skills:
        skills_names = [k for k, _ in top_skills][::-1]
        skills_vals = [v for _, v in top_skills][::-1]
        import matplotlib.pyplot as plt
        plt.figure(figsize=(8, 6))
        if sns:
            sns.barplot(x=skills_vals, y=skills_names, palette="viridis")
        else:
            plt.barh(skills_names, skills_vals, color="#4C72B0")
        plt.xlabel("Count")
        plt.title("Top 10 Skills (by file occurrences)")
        plt.tight_layout()
        top_plot_path = os.path.join(raw_dir, "stats_top_skills.png")
        if save_plots:
            plt.savefig(top_plot_path)
        plt.close()
    else:
        top_plot_path = None

    # R-score distribution
    r_values = list(r_scores.values())
    import matplotlib.pyplot as plt
    plt.figure(figsize=(8, 6))
    if sns:
        sns.histplot(r_values, bins=10, kde=False)
    else:
        plt.hist(r_values, bins=10, color="#55A868")
    plt.xlabel("R-score (deg(file)/#unique_skills)")
    plt.ylabel("Number of files")
    plt.title("R-score Distribution")
    plt.tight_layout()
    r_plot_path = os.path.join(raw_dir, "stats_r_distribution.png")
    if save_plots:
        plt.savefig(r_plot_path)
    plt.close()

    # build report
    report = {
        "top_skills": top_skills,
        "r_metrics": {"per_file": r_scores, "mean_r": (sum(r_values) / len(r_values) if r_values else 0.0)},
        "top3_matches": [ {"file": fn, "match_score": score, "r_score": r, "skills": skills} for fn, score, r, skills in top3 ],
        "plots": {"top_skills_plot": top_plot_path, "r_distribution_plot": r_plot_path},
    }

    # print concise report
    print(json.dumps({
        "top_skills": top_skills,
        "mean_r": report["r_metrics"]["mean_r"],
        "top3_files": report["top3_matches"]
    }, ensure_ascii=False, indent=2))

    return report


if __name__ == "__main__":
    main(limit=None, save_plots=True)
