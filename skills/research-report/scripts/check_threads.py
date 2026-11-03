#!/usr/bin/env python3
"""检查调研报告是否把两条线索编进了正文：核心问题/技术难点、自研优劣。

用法：python scripts/check_threads.py <报告.md>

只做启发式提示，不修改文件。命中后回看原文判断，不要机械加词。
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

DIFF_WORDS = [
    "难点", "瓶颈", "卡在", "卡点", "测不准", "测不到", "失效", "退化",
    "做不到", "无法", "上限", "边界", "约束", "不可逆", "不确定", "门槛",
]
SELF_WORDS = [
    "自研", "自制", "自建", "自己做", "采购", "外购", "买断", "外部厂商", "成套",
]
PRO_WORDS = ["优势", "多得", "多拿", "值得", "抓手", "贴合", "主动权", "沉淀", "省下"]
COST_WORDS = [
    "劣势", "代价", "成本", "资质", "留存", "信任", "独立性", "制度", "人力",
    "折旧", "不足", "短板", "风险",
]
SKIP_CHAPTER = ("附录", "参考文献", "资料来源")
CTX_CHAPTER = ("背景", "目的", "总览", "市场")  # 交代语境，不强求两条线索落在正文


def needs(title: str, has_matrix: bool) -> tuple[int, int, bool]:
    """返回 (难点词门槛, 自研词门槛, 是否逐章检查)。"""
    if any(k in title for k in SKIP_CHAPTER):
        return 0, 0, False
    if any(k in title for k in CTX_CHAPTER):
        return 0, 0, False
    if "摘要" in title:
        return 1, 1, True
    if "案例" in title:
        return 1, 0, True
    if "结论" in title:
        return 0, 2, True
    return 2, 2, True


def hits(text: str, words: list[str]) -> int:
    return sum(text.count(w) for w in words)


def distinct(text: str, words: list[str]) -> int:
    return sum(1 for w in words if w in text)


def parse_tables(body: list[str]) -> list[list[str]]:
    """返回每张表的表头单元格列表。"""
    tables, i = [], 0
    while i < len(body) - 1:
        line = body[i].strip()
        nxt = body[i + 1].strip()
        if line.startswith("|") and re.match(r"^\|[\s:|-]+\|$", nxt):
            cells = [c.strip() for c in line.strip("|").split("|")]
            tables.append(cells)
            i += 2
            continue
        i += 1
    return tables


def split_chapters(lines: list[str]) -> list[dict]:
    chapters: list[dict] = []
    cur = None
    for line in lines:
        if line.startswith("## "):
            cur = {"title": line[3:].strip(), "level2": [], "body": []}
            chapters.append(cur)
        elif line.startswith("### ") and cur is not None:
            cur["level2"].append(line[4:].strip())
            cur["body"].append(line)
        elif cur is not None:
            cur["body"].append(line)
    for ch in chapters:
        ch["text"] = "\n".join(ch["body"])
        ch["tables"] = parse_tables(ch["body"])
        ch["has_matrix"] = any(any("难点" in c for c in h) for h in ch["tables"])
    return chapters


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("md")
    args = ap.parse_args()
    path = Path(args.md)
    if not path.is_file():
        print(f"[FAIL] 找不到文件：{path}")
        return 2

    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    lines = path.read_text(encoding="utf-8").splitlines()
    chapters = split_chapters(lines)
    if not chapters:
        print("[FAIL] 未识别到二级标题（## 一、…），无法按章检查")
        return 2

    rows, warns, infos = [], [], []
    total_self = sum(hits(ch["text"], SELF_WORDS) for ch in chapters)

    for ch in chapters:
        t = ch["text"]
        d, s = distinct(t, DIFF_WORDS), distinct(t, SELF_WORDS)
        p, c = hits(t, PRO_WORDS), hits(t, COST_WORDS)

        judge = []
        standalone_self = bool(re.search(r"自研|自主可控|自制|国产化", ch["title"]))
        need_d, need_s, check = needs(ch["title"], ch["has_matrix"])
        if check:
            if d < need_d:
                warns.append(f"{ch['title']}：缺难点收口（难点类词 {d} 个，建议 ≥{need_d}，需落到具体判据）")
                judge.append("缺难点")
            if need_s and not standalone_self and s < need_s:
                warns.append(f"{ch['title']}：缺自研判断（自研/采购类词 {s} 个，建议 ≥{need_s}）")
                judge.append("缺自研")
            if p >= 3 and c == 0:
                warns.append(f"{ch['title']}：只讲自研优势未讲代价（优势词 {p}、代价词 {c}），需补一句成本或补偿手段")
                judge.append("只讲优势")
        if "分类" in ch["title"] and ch["tables"]:
            head = ch["tables"][0]
            if not any(re.search(r"自研|自制|采购|外购", h) for h in head):
                warns.append(f"{ch['title']}：分类体系表缺「自制/采购判断」列，分层结论无处承载")
                judge.append("分类表缺列")

        if standalone_self:
            warns.append(f"{ch['title']}：自研被单列成章，按规范应融进各章末的收口段")
            judge.append("单列自研")
        elif re.search(r"难点|瓶颈|核心问题|核心矛盾", ch["title"]):
            if ch["has_matrix"]:
                infos.append(f"{ch['title']}：难点单独成章，已含难点矩阵表，按例外条款可接受；需确认不重复前文事实且与选型挂钩")
                judge.append("难点章(例外)")
            else:
                warns.append(f"{ch['title']}：难点单列成章但无难点矩阵表，建议融回各章末，或补可突破顺序矩阵")
                judge.append("单列难点")

        rows.append((ch["title"], d, s, f"{p}/{c}", "、".join(judge) or "OK"))

    concl = [ch for ch in chapters if "结论" in ch["title"]]
    if concl:
        ch = concl[-1]
        if not ch["has_matrix"]:
            warns.append(f"{ch['title']}：结论章未见难点矩阵表（表头应含“难点”），全篇难点无处收口")
        if distinct(ch["text"], SELF_WORDS) < 2:
            warns.append(f"{ch['title']}：结论章未给出“先自研哪一块”的排序")
    else:
        warns.append("未找到结论章（标题含“结论”），无法确认两条线索的收口")

    if total_self >= 6:
        top = max(chapters, key=lambda c: hits(c["text"], SELF_WORDS))
        share = hits(top["text"], SELF_WORDS) / total_self
        if share > 0.55:
            infos.append(f"自研论述集中在《{top['title']}》一章（占比 {share:.0%}），建议分散到各层")

    w = max(len(r[0]) for r in rows)
    print(f"{'章'.ljust(w)}  难点  自研  优劣  判定")
    for title, d, s, pc, j in rows:
        print(f"{title.ljust(w)}  {d:>4}  {s:>4}  {pc:>5}  {j}")
    print()
    for i in infos:
        print(f"[INFO] {i}")
    for m in warns:
        print(f"[WARN] {m}")
    print(f"\n共 {len(chapters)} 章；[WARN] {len(warns)} 项，[INFO] {len(infos)} 项。"
          f"{' 通过' if not warns else ''}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
