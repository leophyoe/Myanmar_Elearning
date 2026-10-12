import os
import re
import json
import zipfile
import subprocess
import xml.etree.ElementTree as ET
from django.conf import settings


def _clean_node_text(p_elem, ns):
    """Extracts and strips concatenated text from XML drawingml paragraph node."""
    parts = [elem.text for elem in p_elem.findall('.//a:t', ns) if elem.text]
    return ''.join(parts).strip()


def _extract_slide_shapes(z, s_name, ns):
    """Extracts all text shapes with bounding coordinates from a slide XML file."""
    root = ET.fromstring(z.read(s_name))
    raw_shapes = []
    for sp in root.findall('.//p:sp', ns):
        xfrm = sp.find('.//a:xfrm', ns)
        off = xfrm.find('a:off', ns) if xfrm is not None else None
        ext = xfrm.find('a:ext', ns) if xfrm is not None else None
        x = int(off.attrib.get('x', 0)) if off is not None else 0
        y = int(off.attrib.get('y', 0)) if off is not None else 0
        w = int(ext.attrib.get('cx', 0)) if ext is not None else 0
        h = int(ext.attrib.get('cy', 0)) if ext is not None else 0
        paras = []
        for p in sp.findall('.//a:p', ns):
            t = _clean_node_text(p, ns)
            if t:
                paras.append(t)
        if paras:
            raw_shapes.append({'x': x, 'y': y, 'w': w, 'h': h, 'paras': paras})

    # Sort shapes from top to bottom, left to right
    raw_shapes.sort(key=lambda s: (s['y'], s['x']))

    # Filter out footer watermarks and slide numbers
    filtered = []
    for s in raw_shapes:
        p0 = s['paras'][0]
        # Slide counter patterns: '2 / 12', '12 / 12', 'Slide 1 of 10'
        if re.match(r'^\s*(\d+\s*/\s*\d+|slide\s*\d+(\s*of\s*\d+)?)\s*$', p0, re.I):
            continue
        # Bottom watermarks (y > 5,500,000) with Course / Episode / Copyright / Thuta
        if s['y'] > 5500000 and any(k in p0.lower() for k in ['course', 'episode', 'slide', 'copyright', 'thuta']):
            continue
        filtered.append(s)

    return filtered


def parse_pptx_to_slides(file_path, lesson=None):
    """
    Parses any PowerPoint (.pptx) presentation file into structured, rich slide objects.
    Dynamically extracts titles, subtitles, code blocks, terminal sessions,
    steps roadmaps, quizzes, multi-column cards, warnings, and takeaways without
    hardcoding any specific course or topic.
    """
    if not os.path.exists(file_path):
        return []

    lesson_id = None
    lesson_title = ""
    module_title = ""
    course_title = ""

    if lesson:
        if hasattr(lesson, 'id'):
            lesson_id = lesson.id
            lesson_title = getattr(lesson, 'title', '') or ''
            if hasattr(lesson, 'module') and lesson.module:
                module_title = getattr(lesson.module, 'title', '') or ''
                if hasattr(lesson.module, 'course') and lesson.module.course:
                    course_title = getattr(lesson.module.course, 'title', '') or ''
        else:
            lesson_id = str(lesson)

    try:
        with zipfile.ZipFile(file_path, 'r') as z:
            slide_files = sorted(
                [f for f in z.namelist() if re.match(r'ppt/slides/slide\d+\.xml', f)],
                key=lambda x: int(re.search(r'\d+', x).group())
            )
            if not slide_files:
                return []

            ns = {
                'a': 'http://schemas.openxmlformats.org/drawingml/2006/main',
                'p': 'http://schemas.openxmlformats.org/presentationml/2006/main',
            }

            # Extract any embedded logo/image for presentation cover
            logo_url = None
            if lesson_id:
                cache_dir = os.path.join(settings.MEDIA_ROOT, 'lessons', 'slides_cache', str(lesson_id))
                os.makedirs(cache_dir, exist_ok=True)
                for item in z.namelist():
                    if item.startswith('ppt/media/') and item.lower().endswith(('.png', '.jpg', '.jpeg', '.svg', '.webp')):
                        out_name = os.path.basename(item)
                        out_path = os.path.join(cache_dir, out_name)
                        if not os.path.exists(out_path):
                            with open(out_path, 'wb') as f_out:
                                f_out.write(z.read(item))
                        if not logo_url:
                            logo_url = f"{settings.MEDIA_URL}lessons/slides_cache/{lesson_id}/{out_name}"

            # Pre-scan Slide 2 for fallback title/features if Slide 1 is minimal
            s2_title = ""
            s2_tagline = ""
            s2_features = []
            if len(slide_files) > 1:
                s2_shapes = _extract_slide_shapes(z, slide_files[1], ns)
                for sp in s2_shapes:
                    if len(sp['paras']) >= 2 and not s2_title and sp['y'] < 2000000:
                        s2_title = sp['paras'][0]
                        s2_tagline = sp['paras'][1]
                    elif len(sp['paras']) >= 1 and len(s2_features) < 4 and sp['y'] >= 2000000:
                        card_lead = sp['paras'][0]
                        if not any(k in card_lead.lower() for k in ['chapter', 'episode']) and len(card_lead.strip('။.,!?:; ')) >= 2:
                            s2_features.append(card_lead)

            slides = []
            total_slides = len(slide_files)

            for slide_num, s_name in enumerate(slide_files, 1):
                shapes = _extract_slide_shapes(z, s_name, ns)

                # ==============================================================
                # 1. Slide 1 (Cover / Presentation Title Slide)
                # ==============================================================
                if slide_num == 1:
                    all_paras = []
                    for s in shapes:
                        all_paras.extend(s['paras'])

                    cover_sub = ""
                    cover_title = ""
                    cover_tagline = ""
                    cover_features = []

                    # Detect agenda/topics line for feature badges (exclude chapter / episode / lesson badges)
                    p_feat = next(
                        (p for p in all_paras if (
                            ('📌' in p or 'အဓိက' in p or 'agenda' in p.lower() or 'topics' in p.lower() or 'roadmap' in p.lower() or (p.count('•') >= 2 and not any(k in p.lower() for k in ['chapter', 'episode', 'lesson'])))
                        )),
                        None
                    )
                    if p_feat:
                        clean_feat = re.sub(r'^[📌•\s]*[^:\-\–]*[:\-\–]\s*', '', p_feat)
                        cover_features = [f.strip() for f in re.split(r'[•·,]', clean_feat) if f.strip()][:5]

                    remaining = [p for p in all_paras if p != p_feat]

                    if len(remaining) > 2:
                        lesson_cand = next((p for p in remaining if re.search(r'\b(lesson|episode)\b', p, re.I)), None)
                        if lesson_cand:
                            cover_title = lesson_cand
                            idx = remaining.index(lesson_cand)
                            before = remaining[:idx]
                            after = remaining[idx + 1:]
                            cover_sub = ' • '.join(before) if before else (module_title or "LESSON OVERVIEW")
                            cover_tagline = ' '.join(after) if after else ""
                        else:
                            cover_sub = remaining[0]
                            cover_title = remaining[1]
                            cover_tagline = ' '.join(remaining[2:])
                    else:
                        cover_sub = remaining[0] if remaining else (module_title or f"LESSON 1")
                        cover_title = s2_title or lesson_title or course_title or "Interactive Presentation"
                        cover_tagline = s2_tagline or f"{total_slides} Interactive Presentation Slides"
                        if not cover_features and s2_features:
                            cover_features = s2_features[:4]

                    if not cover_features:
                        if course_title and lesson_title:
                            cover_features = [f"{total_slides} Slides", course_title, lesson_title]
                        else:
                            cover_features = [f"{total_slides} Slides", "Interactive Curriculum", "Step-by-Step Learning"]

                    slides.append({
                        'number': 1,
                        'layout': 'cover',
                        'subtitle': cover_sub,
                        'title': cover_title,
                        'tagline': cover_tagline,
                        'features': cover_features,
                        'bullets': [],
                        'code_block': None,
                        'image_url': logo_url,
                    })
                    continue

                # ==============================================================
                # Slides 2+: Header Extraction
                # ==============================================================
                header_shapes = [s for s in shapes if s['y'] < 1600000]
                body_shapes = [s for s in shapes if s['y'] >= 1600000]

                subtitle = module_title or course_title
                title = f"Slide {slide_num}"
                tagline = ""

                if header_shapes:
                    if len(header_shapes) == 1:
                        hp = header_shapes[0]['paras']
                        if len(hp) == 1:
                            title = hp[0]
                        elif len(hp) == 2:
                            subtitle = hp[0]
                            title = hp[1]
                        else:
                            subtitle = hp[0]
                            title = hp[1]
                            tagline = hp[2]
                    else:
                        subtitle = header_shapes[0]['paras'][0]
                        title = header_shapes[1]['paras'][0]
                        if len(header_shapes[1]['paras']) > 1:
                            tagline = header_shapes[1]['paras'][1]

                # ==============================================================
                # Layout Detection: Quiz / Code-Terminal / Steps / Cards / 2-Col
                # ==============================================================

                # 1. Interactive Quiz / Q&A Slide
                is_quiz_title = bool(re.search(r'(?:quiz|မေးခွန်း|စစ်ဆေးချက်|knowledge check|test your)', title, re.I))
                quiz_shape_matches = [
                    s for s in body_shapes
                    if re.match(r'^(?:💡\s*)?(?:မေးခွန်း\s*[၁-၉\d]+|Question\s*\d+|Q\d+)\b', s['paras'][0], re.I)
                    or any('အဖြေ' in p or 'answer' in p.lower() for p in s['paras'])
                ]

                if is_quiz_title or len(quiz_shape_matches) >= 2:
                    quiz_items = []
                    for idx, qs in enumerate(body_shapes, 1):
                        q_label = f"မေးခွန်း {idx}"
                        question = ""
                        answer = ""
                        for p in qs['paras']:
                            if 'အဖြေ' in p or 'answer' in p.lower():
                                answer = re.sub(r'^(?:💡\s*)?(?:အဖြေ|Answer)\s*[:\-]\s*', '', p, flags=re.I)
                            elif not question:
                                match_lbl = re.match(r'^(မေးခွန်း\s*[၁-၉\d]+|Question\s*\d+|Q\d+)\s*[:\-]\s*(.*)$', p, re.I)
                                if match_lbl:
                                    q_label = match_lbl.group(1)
                                    question = match_lbl.group(2)
                                else:
                                    question = p
                            else:
                                if not answer:
                                    question += f" {p}"
                                else:
                                    answer += f" {p}"
                        if question:
                            quiz_items.append({
                                'q_label': q_label,
                                'question': question,
                                'answer': answer,
                            })

                    slides.append({
                        'number': slide_num,
                        'layout': 'quiz',
                        'subtitle': subtitle,
                        'title': title,
                        'tagline': tagline,
                        'quiz_items': quiz_items,
                        'bullets': [f"{q['q_label']}: {q['question']}" for q in quiz_items],
                        'code_block': None,
                        'image_url': None,
                    })
                    continue

                # 2. Code & Terminal Side-by-Side Sandbox Split
                code_shape = next(
                    (s for s in body_shapes if any(k in s['paras'][0].lower() for k in ['code', 'python code', 'script', 'app.py', 'source'])),
                    None
                )
                term_shape = next(
                    (s for s in body_shapes if any(k in s['paras'][0].lower() for k in ['terminal', 'output', 'terminal output', 'console', 'result'])),
                    None
                )

                if code_shape and term_shape and code_shape != term_shape:
                    code_title = code_shape['paras'][0]
                    code_lines = []
                    code_notes = []
                    for p in code_shape['paras'][1:]:
                        if p.startswith(('•', '*', 'Note:', 'ရှင်းလင်းချက်')):
                            code_notes.append(p.lstrip('•* '))
                        else:
                            code_lines.append(p)

                    term_title = term_shape['paras'][0]
                    term_lines = []
                    term_notes = []
                    for p in term_shape['paras'][1:]:
                        if p.startswith(('✅', '•', '*', 'Note:', 'ရှင်းလင်းချက်')):
                            term_notes.append(p.lstrip('✅•* '))
                        else:
                            term_lines.append(p)

                    slides.append({
                        'number': slide_num,
                        'layout': 'code_terminal',
                        'subtitle': subtitle,
                        'title': title,
                        'tagline': tagline,
                        'code_title': code_title,
                        'code_text': '\n'.join(code_lines),
                        'code_notes': code_notes,
                        'terminal_title': term_title,
                        'terminal_text': '\n'.join(term_lines),
                        'terminal_notes': term_notes,
                        'bullets': code_lines + term_lines,
                        'code_block': '\n'.join(code_lines),
                        'image_url': None,
                    })
                    continue

                # 3. Steps Roadmap Layout
                step_shapes = [
                    s for s in body_shapes
                    if any(re.search(r'(?:အဆင့်|Step|Phase|Part|Stage|Module)\s*[၁-၉\d]', p, re.I) for p in s['paras'])
                ]

                if len(step_shapes) >= 3:
                    steps = []
                    for i, st_s in enumerate(step_shapes):
                        step_badge = st_s['paras'][0]
                        step_t = st_s['paras'][1] if len(st_s['paras']) > 1 else f"Step {i+1}"
                        step_desc = ' '.join(st_s['paras'][2:]) if len(st_s['paras']) > 2 else ""
                        steps.append({'step_no': step_badge, 'title': step_t, 'description': step_desc})

                    slides.append({
                        'number': slide_num,
                        'layout': 'steps_roadmap',
                        'subtitle': subtitle,
                        'title': title,
                        'tagline': tagline,
                        'steps': steps,
                        'bullets': [f"{st['step_no']}: {st['title']} - {st['description']}" for st in steps],
                        'code_block': None,
                        'image_url': None,
                    })
                    continue

                # 4. Multi-Column Cards Grid (2, 3, or 4 columns)
                intro_text = ""
                card_candidates = list(body_shapes)
                # If the first shape is wide and at top, treat as intro/banner
                if len(card_candidates) >= 3 and card_candidates[0]['w'] > 6000000 and card_candidates[0]['y'] < 2500000:
                    intro_text = ' '.join(card_candidates[0]['paras'])
                    card_candidates = card_candidates[1:]

                xs = sorted([s['x'] for s in card_candidates])
                is_grid = len(card_candidates) in [2, 3, 4] and len(xs) >= 2 and (xs[-1] - xs[0] > 3500000)

                if is_grid:
                    cards = []
                    all_bullets = []
                    for cs in card_candidates:
                        card_title = cs['paras'][0]
                        items = cs['paras'][1:]
                        error_msg = None
                        cause = None
                        solution = None
                        bullet_items = []

                        for it in items:
                            if 'အကြောင်းရင်း' in it or 'cause' in it.lower():
                                cause = re.sub(r'^(?:အကြောင်းရင်း|Cause)\s*[:\-]\s*', '', it, flags=re.I)
                            elif 'ဖြေရှင်းနည်း' in it or 'solution' in it.lower() or 'fix' in it.lower():
                                solution = re.sub(r'^(?:💡\s*)?(?:ဖြေရှင်းနည်း|Solution|Fix)\s*[:\-]\s*', '', it, flags=re.I)
                            elif ('error' in card_title.lower() or 'ပြဿနာ' in card_title or 'pitfall' in card_title.lower()) and not error_msg:
                                error_msg = it
                            else:
                                bullet_items.append(it)

                        all_bullets.extend(items)
                        cards.append({
                            'title': card_title,
                            'items': bullet_items,
                            'error_msg': error_msg,
                            'cause': cause,
                            'solution': solution,
                        })

                    slides.append({
                        'number': slide_num,
                        'layout': 'cards_grid',
                        'subtitle': subtitle,
                        'title': title,
                        'tagline': tagline,
                        'intro_text': intro_text,
                        'cards': cards,
                        'bullets': all_bullets,
                        'code_block': None,
                        'image_url': None,
                    })
                    continue

                # 5. 2-Column Split Layout (Guidelines left, Alert/Terminal/Notes right)
                left_shapes = [s for s in body_shapes if s['x'] < 5500000]
                right_shapes = [s for s in body_shapes if s['x'] >= 5500000]

                if left_shapes and right_shapes:
                    left_title = left_shapes[0]['paras'][0]
                    left_items = left_shapes[0]['paras'][1:]
                    if len(left_shapes) > 1:
                        for extra in left_shapes[1:]:
                            left_items.extend(extra['paras'])

                    right_title = right_shapes[0]['paras'][0]
                    right_items = right_shapes[0]['paras'][1:]
                    right_callout = None
                    if len(right_shapes) > 1:
                        for extra in right_shapes[1:]:
                            for p in extra['paras']:
                                if 'add python' in p.lower() or '☑' in p:
                                    right_callout = p
                                else:
                                    right_items.append(p)

                    is_terminal = any(any(k in p for k in ['$ ', '>>>', 'Python 3.', 'pip ']) for p in right_items)
                    is_code = 'app.py' in right_title.lower() or any(k in right_title.lower() for k in ['file:', 'code editor'])
                    is_alert = any(k in right_title.lower() for k in ['သတိပေးချက်', 'golden rule', '⚠️', 'သတိပြုရန်', 'warning'])

                    code_lines = []
                    terminal_output_lines = []
                    if is_code:
                        in_terminal = False
                        for p in right_items:
                            if 'terminal output' in p.lower() or '🖥️' in p:
                                in_terminal = True
                                continue
                            if in_terminal:
                                terminal_output_lines.append(p)
                            else:
                                code_lines.append(p)

                    all_bullets = left_items + [p for p in right_items if not p.startswith(('$', '>>>'))]

                    slides.append({
                        'number': slide_num,
                        'layout': 'split_2col',
                        'subtitle': subtitle,
                        'title': title,
                        'tagline': tagline,
                        'left_title': left_title,
                        'left_items': left_items,
                        'right_title': right_title,
                        'right_items': right_items,
                        'right_callout': right_callout,
                        'is_terminal': is_terminal,
                        'is_code': is_code,
                        'is_alert': is_alert,
                        'code_text': '\n'.join(code_lines) if code_lines else ('\n'.join(right_items) if is_terminal else None),
                        'terminal_output': '\n'.join(terminal_output_lines) if terminal_output_lines else None,
                        'bullets': all_bullets,
                        'code_block': '\n'.join(code_lines or right_items) if (is_code or is_terminal) else None,
                        'image_url': None,
                    })
                    continue

                # 6. Fallback Content Cards Layout
                content_cards = []
                all_bullets = []
                for s in body_shapes:
                    if len(s['paras']) == 1:
                        card_title = ""
                        raw_items = s['paras']
                    else:
                        card_title = s['paras'][0]
                        raw_items = s['paras'][1:]

                    parsed_items = []
                    for it in raw_items:
                        is_bullet = it.startswith(('•', '*', '-'))
                        text = it.lstrip('•*- ').strip()
                        parsed_items.append({'text': text, 'is_bullet': is_bullet})
                        all_bullets.append(text)

                    content_cards.append({
                        'title': card_title,
                        'items': parsed_items,
                    })

                slides.append({
                    'number': slide_num,
                    'layout': 'content_cards',
                    'subtitle': subtitle,
                    'title': title,
                    'tagline': tagline,
                    'content_cards': content_cards,
                    'bullets': all_bullets,
                    'code_block': None,
                    'image_url': None,
                })

            return slides
    except Exception as e:
        print(f"[SlidesService] Error parsing PPTX '{file_path}': {e}")
        return []


def parse_pdf_to_slides(file_path, lesson_id):
    """
    Renders PDF pages to raster PNG slide images using system pdftoppm.
    Cached in media/lessons/slides_cache/<lesson_id>/
    """
    if not os.path.exists(file_path):
        return []

    cache_dir = os.path.join(settings.MEDIA_ROOT, 'lessons', 'slides_cache', str(lesson_id))
    os.makedirs(cache_dir, exist_ok=True)

    # Check if cached images already exist
    existing = sorted([
        f for f in os.listdir(cache_dir)
        if f.endswith('.png') and re.search(r'\d+', f)
    ], key=lambda x: int(re.search(r'\d+', x).group()))

    base_url = f"{settings.MEDIA_URL}lessons/slides_cache/{lesson_id}/"

    if existing:
        return [
            {
                'number': idx,
                'layout': 'image',
                'title': f'Slide {idx}',
                'subtitle': 'PDF Presentation',
                'bullets': [],
                'code_block': None,
                'image_url': f"{base_url}{f}",
            }
            for idx, f in enumerate(existing, 1)
        ]

    # Run pdftoppm
    prefix = os.path.join(cache_dir, 'slide')
    try:
        res = subprocess.run(
            ['pdftoppm', '-png', '-r', '150', file_path, prefix],
            capture_output=True,
            timeout=30,
        )
        if res.returncode == 0:
            generated = sorted([
                f for f in os.listdir(cache_dir)
                if f.endswith('.png') and re.search(r'\d+', f)
            ], key=lambda x: int(re.search(r'\d+', x).group()))
            return [
                {
                    'number': idx,
                    'layout': 'image',
                    'title': f'Slide {idx}',
                    'subtitle': 'PDF Presentation',
                    'bullets': [],
                    'code_block': None,
                    'image_url': f"{base_url}{f}",
                }
                for idx, f in enumerate(generated, 1)
            ]
    except Exception as e:
        print(f"[SlidesService] pdftoppm failed: {e}")

    return []


def get_lesson_slide_deck(lesson):
    """
    Main entry point: returns a list of slide dicts for a lesson.
    """
    if not lesson.document_file:
        return []

    ext = lesson.document_extension.lower()
    file_path = lesson.document_file.path

    if ext in ['pptx', 'ppt']:
        return parse_pptx_to_slides(file_path, lesson=lesson)

    if ext == 'pdf':
        slides = parse_pdf_to_slides(file_path, lesson.id)
        if slides:
            return slides

    return []
