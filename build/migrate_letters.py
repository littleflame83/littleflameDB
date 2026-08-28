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
    if m:
        y, mo, d = m.groups()
        return f"{int(y):04d}-{int(mo):02d}-{int(d):02d}"
    # "2008년 5월" 처럼 일자가 없는 경우 -> 1일로 처리 (정렬/구분용, 화면엔 원문 그대로 표시됨)
    m = re.search(r'(\d{4})년\s*(\d{1,2})월', date_text)
    if m:
        y, mo = m.groups()
        return f"{int(y):04d}-{int(mo):02d}-01"
    return "0000-00-00"

def extract_collection(soup, tmpl_prefix, card_selector_attr, out_dir, manifest_title):
    """template 기반 글 모음(기도편지/가족이야기/캄보디아이야기)을 공통 로직으로 추출"""
    out_dir.mkdir(parents=True, exist_ok=True)
    cards = {}
    for btn in soup.select(f'[{card_selector_attr}]'):
        idx = btn.get(card_selector_attr)
        img = btn.select_one('img')
        excerpt_p = btn.select('p')
        cards[idx] = {
            'image': img['src'] if img else (btn.get('data-photos', '')[2:-2].split('","')[0] if btn.get('data-photos') else ''),
            'excerpt': excerpt_p[-1].get_text(strip=True) if excerpt_p else '',
        }

    templates = soup.select(f'template[id^="{tmpl_prefix}-tmpl-"]')
    count = 0
    seen_dates = {}
    manifest_lines = []
    for tmpl in templates:
        idx = tmpl['id'].replace(f'{tmpl_prefix}-tmpl-', '')
        inner = tmpl.decode_contents()
        tsoup = BeautifulSoup(inner, "html.parser")

        date_span = tsoup.select_one('span')
        date_text = date_span.get_text(strip=True) if date_span else ''
        date_iso = parse_korean_date(date_text)

        h2 = tsoup.select_one('h2')
        title = h2.get_text(strip=True) if h2 else f'제목없음-{idx}'

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
        print(f"생성됨: {out_file.relative_to(out_dir.parent.parent)}  ({title})")
        count += 1
        manifest_lines.append(f"- `{url_slug}.html` → {title} ({date_text})")

    manifest_path = out_dir / "INDEX.md"
    manifest_path.write_text(
        f"# {manifest_title} 파일 목록 (파일명 → 제목)\n\n" + "\n".join(manifest_lines) + "\n",
        encoding="utf-8",
    )
    return count


def extract_static_page(soup, overlay_id, out_file, heading=None, eyebrow=None, accent=None, strip_header=True):
    """오버레이 안의 <section> 또는 콘텐츠 div를 그대로 추출해 고정 페이지 콘텐츠로 저장"""
    overlay = soup.select_one(f'#{overlay_id}')
    if overlay is None:
        print(f"경고: #{overlay_id} 를 찾지 못했습니다")
        return
    # 상단 sticky 타이틀바(제목만 있는 얇은 바)는 base.html에 이미 있는 페이지 헤더로 대체하므로 제거
    sticky = overlay.select_one('.sticky')
    if strip_header and sticky:
        sticky.decompose()

    inner_html = overlay.decode_contents().strip()
    # 오버레이 열고닫기용 onclick 잔재 정리: 실제 링크로 교체
    inner_html = inner_html.replace(
        "onclick=\"closeOverlay('aboutOverlay'); openOverlay('supportOverlay')\"",
        'href="/support/"'
    )
    if heading:
        header_block = f'''<div class="max-w-3xl mx-auto text-center px-6 pt-12 pb-2 sm:pt-16">
  <p class="text-{accent} text-xs font-bold tracking-[0.25em] uppercase mb-3">{eyebrow}</p>
  <h1 class="text-2xl sm:text-3xl font-bold tracking-tight text-ink-900">{heading}</h1>
</div>\n'''
        inner_html = header_block + inner_html

    out_file.write_text(inner_html, encoding="utf-8")
    print(f"생성됨: {out_file.name} (정적 페이지)")


def extract_gallery_page(soup, out_file):
    overlay = soup.select_one('#galleryOverlay')
    lightbox = soup.select_one('#galleryLightbox')
    if overlay is None:
        print("경고: #galleryOverlay 를 찾지 못했습니다")
        return

    sticky = overlay.select_one('.sticky')
    if sticky:
        sticky.decompose()
    gallery_html = overlay.decode_contents().strip()
    lightbox_html = lightbox.decode_contents().strip() if lightbox else ""

    script = '''
<script>
  (function() {
    function filterGallery(category) {
      document.querySelectorAll('.gallery-card').forEach(card => {
        const match = category === 'all' || card.dataset.category === category;
        card.classList.toggle('hidden', !match);
      });
      document.querySelectorAll('.gallery-filter-btn').forEach(btn => {
        const active = btn.dataset.galleryFilter === category;
        btn.classList.toggle('active', active);
        btn.classList.toggle('bg-ink-900', active);
        btn.classList.toggle('text-white', active);
        btn.classList.toggle('bg-white', !active);
        btn.classList.toggle('text-ink-700', !active);
      });
    }
    window.filterGallery = filterGallery;

    const galleryLightbox = document.getElementById('galleryLightbox');
    const galleryLightboxImg = document.getElementById('galleryLightboxImg');
    const galleryLightboxVideoWrap = document.getElementById('galleryLightboxVideoWrap');
    const galleryLightboxVideoFrame = document.getElementById('galleryLightboxVideoFrame');
    const galleryLightboxPrev = document.getElementById('galleryLightboxPrev');
    const galleryLightboxNext = document.getElementById('galleryLightboxNext');
    const galleryLightboxCounter = document.getElementById('galleryLightboxCounter');
    const galleryLightboxCloseBtn = document.getElementById('galleryLightboxCloseBtn');
    let galleryPhotos = [];
    let galleryIndex = 0;

    function updateGalleryLightbox() {
      galleryLightboxImg.src = galleryPhotos[galleryIndex];
      const multi = galleryPhotos.length > 1;
      galleryLightboxPrev.classList.toggle('hidden', !multi);
      galleryLightboxNext.classList.toggle('hidden', !multi);
      galleryLightboxCounter.classList.toggle('hidden', !multi);
      if (multi) galleryLightboxCounter.textContent = (galleryIndex + 1) + ' / ' + galleryPhotos.length;
    }

    function openGalleryLightbox(photos, startIdx) {
      galleryLightboxVideoWrap.classList.add('hidden');
      galleryLightboxVideoFrame.src = '';
      galleryLightboxImg.classList.remove('hidden');
      galleryPhotos = photos;
      galleryIndex = startIdx || 0;
      updateGalleryLightbox();
      galleryLightbox.classList.remove('hidden');
      document.body.style.overflow = 'hidden';
    }

    function openGalleryVideo(videoId, title) {
      galleryLightboxImg.classList.add('hidden');
      galleryLightboxPrev.classList.add('hidden');
      galleryLightboxNext.classList.add('hidden');
      galleryLightboxCounter.classList.add('hidden');
      galleryLightboxVideoWrap.classList.remove('hidden');
      galleryLightboxVideoFrame.src = 'https://www.youtube.com/embed/' + videoId + '?autoplay=1&rel=0';
      galleryLightboxVideoFrame.title = title || '';
      const fallbackLink = document.getElementById('galleryLightboxVideoFallback');
      if (fallbackLink) fallbackLink.href = 'https://youtu.be/' + videoId;
      galleryLightbox.classList.remove('hidden');
      document.body.style.overflow = 'hidden';
    }

    function closeGalleryLightbox() {
      galleryLightbox.classList.add('hidden');
      document.body.style.overflow = '';
      galleryLightboxVideoWrap.classList.add('hidden');
      galleryLightboxVideoFrame.src = '';
      galleryLightboxImg.classList.remove('hidden');
    }

    document.querySelectorAll('.gallery-card').forEach(card => {
      card.addEventListener('click', () => {
        const videoId = card.getAttribute('data-video-id');
        if (videoId) {
          const title = card.querySelector('.gallery-title')?.textContent || '';
          openGalleryVideo(videoId, title);
          return;
        }
        const photos = JSON.parse(card.getAttribute('data-photos') || '[]');
        openGalleryLightbox(photos, 0);
      });
    });

    galleryLightboxPrev.addEventListener('click', () => {
      galleryIndex = (galleryIndex - 1 + galleryPhotos.length) % galleryPhotos.length;
      updateGalleryLightbox();
    });
    galleryLightboxNext.addEventListener('click', () => {
      galleryIndex = (galleryIndex + 1) % galleryPhotos.length;
      updateGalleryLightbox();
    });
    galleryLightboxCloseBtn.addEventListener('click', closeGalleryLightbox);
    galleryLightbox.addEventListener('click', (e) => { if (e.target === galleryLightbox) closeGalleryLightbox(); });
    document.addEventListener('keydown', (e) => {
      if (galleryLightbox.classList.contains('hidden')) return;
      if (e.key === 'ArrowLeft') galleryLightboxPrev.click();
      if (e.key === 'ArrowRight') galleryLightboxNext.click();
      if (e.key === 'Escape') closeGalleryLightbox();
    });
  })();
</script>
'''
    full = gallery_html + "\n" + f'<div id="galleryLightbox" class="hidden fixed inset-0 z-[115] bg-ink-900/90 flex items-center justify-center p-6">{lightbox_html}</div>' + script
    out_file.write_text(full, encoding="utf-8")
    print(f"생성됨: {out_file.name} (정적 페이지, 필터+라이트박스 포함)")


def main():
    src_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("/home/claude/index.html")
    base_content_dir = Path(__file__).parent / "content"

    html_text = src_path.read_text(encoding="utf-8")
    soup = BeautifulSoup(html_text, "html.parser")

    n1 = extract_collection(soup, "ovltr", "data-ovltr", base_content_dir / "letter", "기도편지")
    print(f"기도편지 {n1}개 완료\n")

    n2 = extract_collection(soup, "ovrpt", "data-ovrpt", base_content_dir / "family", "가족이야기")
    print(f"가족이야기 {n2}개 완료\n")

    n3 = extract_collection(soup, "ovcam", "data-ovcam", base_content_dir / "cambodia", "캄보디아이야기")
    print(f"캄보디아이야기 {n3}개 완료\n")

    extract_static_page(soup, "aboutOverlay", base_content_dir / "about.html")
    extract_static_page(soup, "supportOverlay", base_content_dir / "support.html",
                         heading="후원 안내", eyebrow="Support", accent="ember")
    extract_gallery_page(soup, base_content_dir / "media.html")

    print(f"총 {n1 + n2 + n3}개 글 + 3개 고정페이지를 옮겼습니다.")

if __name__ == "__main__":
    main()
