#!/usr/bin/env python3
"""
기존 index.html 안의 기도편지(<template id="ovltr-tmpl-N">)를 자동으로 읽어서
content/letters/*.html 파일로 하나씩 뽑아내는 1회용 변환 스크립트.

사용법: python3 migrate_letters.py <원본 index.html 경로>
"""
import re
import sys
import html as htmllib
from pathlib import Path
from bs4 import BeautifulSoup

def url_slug_for(date_iso, seen_dates):
    # 파일명 = 실제 URL 주소와 동일하게: 한글 없이 날짜 기반으로 통일
    # (압축파일로 주고받을 때 한글 파일명이 깨지는 문제를 근본적으로 없애기 위함)
    # 같은 날짜에 편지가 여러 개면 -2, -3 이렇게 붙여서 구분
    seen_dates[date_iso] = seen_dates.get(date_iso, 0) + 1
    n = seen_dates[date_iso]
    return date_iso if n == 1 else f"{date_iso}-{n}"

def parse_korean_date(date_text):
    # "2026년 8월 7일" -> "2026-08-07"
    m = re.search(r'(\d{4})년\s*(\d{1,2})월\s*(\d{1,2})일', date_text)
    if not m:
        return "0000-00-00"
    y, mo, d = m.groups()
    return f"{int(y):04d}-{int(mo):02d}-{int(d):02d}"

def main():
    src_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("/home/claude/index.html")
    out_dir = Path(__file__).parent / "content" / "letters"
    out_dir.mkdir(parents=True, exist_ok=True)

    html_text = src_path.read_text(encoding="utf-8")
    soup = BeautifulSoup(html_text, "html.parser")

    # 1) 카드(목록)에서 이미지+요약(excerpt) 가져오기
    cards = {}
    for btn in soup.select('button[data-ovltr]'):
        idx = btn.get('data-ovltr')
        img = btn.select_one('img')
        excerpt_p = btn.select('p')
        cards[idx] = {
            'image': img['src'] if img else '',
            'excerpt': excerpt_p[-1].get_text(strip=True) if excerpt_p else '',
        }

    # 2) template(본문 전체) 가져오기
    templates = soup.select('template[id^="ovltr-tmpl-"]')
    count = 0
    seen_dates = {}
    manifest_lines = []
    for tmpl in templates:
        idx = tmpl['id'].replace('ovltr-tmpl-', '')
        inner = tmpl.decode_contents()
        tsoup = BeautifulSoup(inner, "html.parser")

        date_span = tsoup.select_one('span')
        date_text = date_span.get_text(strip=True) if date_span else ''
        date_iso = parse_korean_date(date_text)

        h2 = tsoup.select_one('h2')
        title = h2.get_text(strip=True) if h2 else f'제목없음-{idx}'

        # 본문 div (가장 마지막 div.text-[15px])
        body_div = tsoup.select_one('div.text-\\[15px\\]') or tsoup.select_one('div[class*="text-[15px]"]')
        body_html = body_div.decode_contents().strip() if body_div else ''

        card = cards.get(idx, {})
        image = card.get('image', '')
        excerpt = card.get('excerpt', '')

        url_slug = url_slug_for(date_iso, seen_dates)

        frontmatter = (
            "---\n"
            f"title: \"{title}\"\n"
            f"date: \"{date_iso}\"\n"
            f"date_display: \"{date_text}\"\n"
            f"image: \"{image}\"\n"
            f"excerpt: \"{excerpt}\"\n"
            f"url_slug: \"{url_slug}\"\n"
            "---\n"
        )

        out_file = out_dir / f"{url_slug}.html"
        out_file.write_text(frontmatter + body_html + "\n", encoding="utf-8")
        print(f"생성됨: {out_file.name}  ({title})")
        count += 1
        manifest_lines.append(f"- `{url_slug}.html` → {title} ({date_text})")

    manifest_path = out_dir / "INDEX.md"
    manifest_path.write_text(
        "# 기도편지 파일 목록 (파일명 → 제목)\n\n" + "\n".join(manifest_lines) + "\n",
        encoding="utf-8",
    )
    print(f"목록 파일 생성됨: {manifest_path.name}")

    print(f"\n총 {count}개 기도편지를 옮겼습니다 -> {out_dir}")

if __name__ == "__main__":
    main()
