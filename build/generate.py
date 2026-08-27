#!/usr/bin/env python3
"""
content/letters/*.html 파일들을 읽어서 실제 사이트 페이지(html)를 만들어냅니다.
- /letters/index.html            (기도편지 목록)
- /letters/<slug>/index.html     (기도편지 각각, 고유 주소)

배포 시(깃허브 액션)에서 이 스크립트가 자동으로 실행됩니다.
사장님은 content/letters/ 안에 파일만 추가하시면 됩니다.
"""
import re
from pathlib import Path
from jinja2 import Environment, FileSystemLoader

BASE = Path(__file__).parent
CONTENT_DIR = BASE / "content" / "letters"
TEMPLATES_DIR = BASE / "templates"
OUTPUT_DIR = BASE.parent / "dist"   # 최종 결과물 (깃허브 액션이 이 폴더를 그대로 배포)
SITE_URL = "https://cammission.com"

env = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)))


def parse_content_file(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    m = re.match(r"^---\n(.*?)\n---\n(.*)$", text, re.DOTALL)
    if not m:
        raise ValueError(f"프론트매터 형식이 아닙니다: {path}")
    fm_text, body = m.groups()
    data = {}
    for line in fm_text.splitlines():
        if ":" not in line:
            continue
        key, val = line.split(":", 1)
        data[key.strip()] = val.strip().strip('"')
    data["body"] = body.strip()
    return data


def render_page(template_name: str, out_path: Path, **context):
    tmpl = env.get_template(template_name)
    inner_html = tmpl.render(**context)

    base_tmpl = env.get_template("base.html")
    full_html = base_tmpl.render(content=inner_html, **context)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(full_html, encoding="utf-8")
    print(f"생성됨: {out_path.relative_to(OUTPUT_DIR.parent)}")


def normalize_image(path: str) -> str:
    if not path:
        return ""
    if path.startswith("http") or path.startswith("/"):
        return path
    return "/" + path


def main():
    letters = []
    for f in sorted(CONTENT_DIR.glob("*.html")):
        data = parse_content_file(f)
        data["image"] = normalize_image(data.get("image", ""))
        letters.append(data)

    # 최신 글이 먼저 오도록 날짜순 정렬
    letters.sort(key=lambda x: x.get("date", ""), reverse=True)

    # 1) 목록 페이지
    render_page(
        "letters_index.html",
        OUTPUT_DIR / "letters" / "index.html",
        letters=letters,
        active_nav="letters",
        page_title="기도 편지 | 작은불꽃 홍선교",
        page_description="캄보디아 프놈펜 선교사 홍성화의 기도편지 모음입니다.",
        page_url=f"{SITE_URL}/letters/",
        page_image=f"{SITE_URL}/images/img-809ccadbb89a.jpg",
    )

    # 2) 편지 하나하나의 개별 페이지 (진짜 고유 주소! 한글 없이 날짜 기반이라 카톡 공유해도 안 깨짐)
    for letter in letters:
        image_url = letter["image"]
        if not image_url.startswith("http"):
            image_url = f"{SITE_URL}{image_url}"
        url_slug = letter["url_slug"]
        render_page(
            "letter_page.html",
            OUTPUT_DIR / "letters" / url_slug / "index.html",
            letter=letter,
            active_nav="letters",
            page_title=f"{letter['title']} | 작은불꽃 홍선교",
            page_description=letter["excerpt"],
            page_url=f"{SITE_URL}/letters/{url_slug}/",
            page_image=image_url,
        )

    print(f"\n총 {len(letters)}개 기도편지 페이지 생성 완료 -> {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
