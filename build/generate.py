#!/usr/bin/env python3
"""
content/ 안의 글들을 읽어서 실제 사이트 페이지(html)를 만들어냅니다.

- /letters/, /letters/<slug>/        기도 편지
- /reports/, /reports/<slug>/        가족 이야기
- /cambodia/, /cambodia/<slug>/      캄보디아 이야기
- /about/                            사역 소개 (고정 1페이지)
- /support/                          후원 안내 (고정 1페이지)
- /gallery/                          사진과 영상 (고정 1페이지)

배포 시(깃허브 액션)에서 이 스크립트가 자동으로 실행됩니다.
사장님은 content/<섹션>/ 안에 파일만 추가하시면 됩니다.
"""
import re
from pathlib import Path
from jinja2 import Environment, FileSystemLoader

BASE = Path(__file__).parent
CONTENT_DIR = BASE / "content"
TEMPLATES_DIR = BASE / "templates"
OUTPUT_DIR = BASE.parent / "dist"
SITE_URL = "https://cammission.com"
DEFAULT_IMAGE = f"{SITE_URL}/images/img-809ccadbb89a.jpg"

env = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)))

COLLECTIONS = [
    {
        "key": "letter",
        "heading": "기도 편지",
        "eyebrow": "Prayer Letter",
        "accent": "violet-500",
        "description": "캄보디아 프놈펜 선교사 홍성화의 기도편지 모음입니다.",
    },
    {
        "key": "family",
        "heading": "가족 이야기",
        "eyebrow": "Family Story",
        "accent": "rose-500",
        "description": "홍성화 선교사 가족의 준비 과정과 일상 이야기입니다.",
    },
    {
        "key": "cambodia",
        "heading": "캄보디아 이야기",
        "eyebrow": "Cambodia Story",
        "accent": "ember",
        "description": "캄보디아를 처음 품었던 순간부터 그 땅에서 만난 사람들과 이야기들입니다.",
    },
]


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
    data["_source_file"] = path.name
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


def absolute_image(path: str) -> str:
    if not path:
        return DEFAULT_IMAGE
    return path if path.startswith("http") else f"{SITE_URL}{path}"


def build_collection(cfg: dict):
    key = cfg["key"]
    content_dir = CONTENT_DIR / key
    items = []
    for f in sorted(content_dir.glob("*.html")):
        data = parse_content_file(f)
        data["image"] = normalize_image(data.get("image", ""))
        items.append(data)

    items.sort(key=lambda x: x.get("date", ""), reverse=True)

    seen = {}
    for item in items:
        seen.setdefault(item["url_slug"], []).append(item["_source_file"])
    duplicates = {k: v for k, v in seen.items() if len(v) > 1}
    if duplicates:
        msg = [f"[{key}] 같은 주소(url_slug)를 가진 글이 여러 개 있어요:"]
        for slug, files in duplicates.items():
            msg.append(f"  '{slug}' 사용 중: {', '.join(files)}")
        raise SystemExit("\n".join(msg))

    render_page(
        "collection_index.html",
        OUTPUT_DIR / key / "index.html",
        items=items,
        collection=key,
        heading=cfg["heading"],
        eyebrow=cfg["eyebrow"],
        accent=cfg["accent"],
        subheading=None,
        active_nav=key,
        page_title=f"{cfg['heading']} | 작은불꽃 홍선교",
        page_description=cfg["description"],
        page_url=f"{SITE_URL}/{key}/",
        page_image=DEFAULT_IMAGE,
    )

    for item in items:
        url_slug = item["url_slug"]
        render_page(
            "collection_page.html",
            OUTPUT_DIR / key / url_slug / "index.html",
            item=item,
            collection=key,
            heading=cfg["heading"],
            accent=cfg["accent"],
            active_nav=key,
            page_title=f"{item['title']} | 작은불꽃 홍선교",
            page_description=item.get("excerpt", cfg["description"]),
            page_url=f"{SITE_URL}/{key}/{url_slug}/",
            page_image=absolute_image(item["image"]),
        )

    print(f"-> {key}: {len(items)}개 페이지 생성 완료\n")
    return len(items)


def build_static_page(key: str, page_title: str, page_description: str, page_image: str = None):
    content_file = CONTENT_DIR / f"{key}.html"
    inner_html = content_file.read_text(encoding="utf-8")
    base_tmpl = env.get_template("base.html")
    full_html = base_tmpl.render(
        content=inner_html,
        active_nav=key,
        page_title=page_title,
        page_description=page_description,
        page_url=f"{SITE_URL}/{key}/",
        page_image=page_image or DEFAULT_IMAGE,
    )
    out_path = OUTPUT_DIR / key / "index.html"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(full_html, encoding="utf-8")
    print(f"생성됨: {out_path.relative_to(OUTPUT_DIR.parent)}\n")


def main():
    total = 0
    for cfg in COLLECTIONS:
        total += build_collection(cfg)

    build_static_page(
        "about",
        "사역 소개 | 작은불꽃 홍선교",
        "캄보디아 프놈펜에서 사역하는 홍성화 & 박윤희 선교사의 사역 소개입니다.",
        f"{SITE_URL}/images/img-7bf08bd0fd0d.jpg",
    )
    build_static_page(
        "support",
        "후원 안내 | 작은불꽃 홍선교",
        "캄보디아 선교 동역 및 후원 안내입니다.",
    )
    build_static_page(
        "media",
        "사진과 영상 | 작은불꽃 홍선교",
        "캄보디아 현장과 준비 과정을 담은 사진과 영상입니다.",
    )

    print(f"총 {total}개 글 + 3개 고정 페이지 생성 완료 -> {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
