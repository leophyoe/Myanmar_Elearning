import os
import re
import json
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path
from django.core.management.base import BaseCommand
from django.utils.text import slugify
from django.conf import settings

from apps.courses.models import Course, Module, Lesson, LessonType
from apps.users.models import User, UserRole


def extract_pptx_slides(pptx_path):
    """
    Extracts text, slide titles, bullet points, and speaker notes from a .pptx file.
    Uses pure Python standard library (zipfile + xml.etree.ElementTree).
    Falls back gracefully if python-pptx is available.
    """
    # 1. Try python-pptx if installed
    try:
        from pptx import Presentation
        prs = Presentation(pptx_path)
        slides_data = []
        for idx, slide in enumerate(prs.slides, start=1):
            title = ""
            paragraphs = []
            if slide.shapes.title and slide.shapes.title.text:
                title = slide.shapes.title.text.strip()
            for shape in slide.shapes:
                if shape.has_text_frame and shape != slide.shapes.title:
                    for para in shape.text_frame.paragraphs:
                        text = para.text.strip()
                        if text:
                            paragraphs.append(text)
            notes_text = ""
            if slide.has_notes_slide and slide.notes_slide.notes_text_frame:
                notes_text = slide.notes_slide.notes_text_frame.text.strip()
            slides_data.append({
                "slide_number": idx,
                "title": title or f"Slide {idx}",
                "bullets": paragraphs,
                "notes": notes_text,
            })
        return slides_data
    except ImportError:
        pass

    # 2. Pure Python Standard Library parser (zipfile + ElementTree)
    slides_data = []
    ns = {
        'a': 'http://schemas.openxmlformats.org/drawingml/2006/main',
        'r': 'http://schemas.openxmlformats.org/officeDocument/2006/relationships',
        'p': 'http://schemas.openxmlformats.org/presentationml/2006/main',
    }

    try:
        with zipfile.ZipFile(pptx_path, 'r') as zf:
            slide_files = [
                f for f in zf.namelist()
                if f.startswith('ppt/slides/slide') and f.endswith('.xml')
            ]
            # Natural sort: slide1.xml, slide2.xml, slide10.xml
            def slide_num_key(name):
                match = re.search(r'slide(\d+)\.xml', name)
                return int(match.group(1)) if match else 0

            slide_files.sort(key=slide_num_key)

            for idx, slide_file in enumerate(slide_files, start=1):
                xml_content = zf.read(slide_file)
                tree = ET.fromstring(xml_content)

                title = ""
                paragraphs = []

                # Find shapes
                for sp in tree.findall('.//p:sp', ns):
                    # Check if title shape
                    ph = sp.find('.//p:nvSpPr/p:nvPr/p:ph', ns)
                    is_title = False
                    if ph is not None:
                        ph_type = ph.attrib.get('type', '')
                        if ph_type in ('title', 'ctrTitle'):
                            is_title = True

                    # Extract text inside this shape
                    sp_texts = []
                    for p_elem in sp.findall('.//a:p', ns):
                        t_elems = p_elem.findall('.//a:t', ns)
                        p_str = "".join([t.text or "" for t in t_elems]).strip()
                        if p_str:
                            sp_texts.append(p_str)

                    if is_title and sp_texts:
                        title = sp_texts[0]
                        if len(sp_texts) > 1:
                            paragraphs.extend(sp_texts[1:])
                    else:
                        paragraphs.extend(sp_texts)

                # Check for speaker notes
                notes_text = ""
                notes_file = f"ppt/notesSlides/notesSlide{idx}.xml"
                if notes_file in zf.namelist():
                    try:
                        notes_xml = zf.read(notes_file)
                        notes_tree = ET.fromstring(notes_xml)
                        notes_paragraphs = []
                        for p_elem in notes_tree.findall('.//a:p', ns):
                            t_elems = p_elem.findall('.//a:t', ns)
                            p_str = "".join([t.text or "" for t in t_elems]).strip()
                            if p_str:
                                notes_paragraphs.append(p_str)
                        notes_text = "\n".join(notes_paragraphs)
                    except Exception:
                        pass

                slides_data.append({
                    "slide_number": idx,
                    "title": title or f"Slide {idx}",
                    "bullets": paragraphs,
                    "notes": notes_text,
                })
    except Exception as e:
        slides_data.append({
            "slide_number": 1,
            "title": "Extraction Error",
            "bullets": [f"Error extracting PPTX: {str(e)}"],
            "notes": "",
        })

    return slides_data


class Command(BaseCommand):
    help = (
        "Processes PowerPoint (.pptx) slides from curriculum/academic_programs/<course>/slides/ "
        "and reconstructs modules, lessons, and AI course content for Myanmar E-Learning."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--curriculum-dir',
            type=str,
            default='curriculum/academic_programs',
            help='Path to the academic programs curriculum directory.'
        )
        parser.add_argument(
            '--course',
            type=str,
            default='',
            help='Filter by course slug (e.g., diploma-in-cyber-security).'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Parse slides and preview generated content without updating database.'
        )
        parser.add_argument(
            '--generate-prompts',
            action='store_true',
            help='Generate AI course generation prompt files in the modules/ directory.'
        )

    def handle(self, *args, **options):
        base_dir = Path(settings.BASE_DIR) / options['curriculum_dir']
        target_course = options['course'].strip()
        dry_run = options['dry_run']
        gen_prompts = options['generate_prompts']

        if not base_dir.exists():
            self.stdout.write(self.style.ERROR(f"Curriculum directory not found: {base_dir}"))
            return

        self.stdout.write(self.style.NOTICE("=" * 70))
        self.stdout.write(self.style.NOTICE("Myanmar E-Learning (MEL) — AI PowerPoint Course Rebuilder"))
        self.stdout.write(self.style.NOTICE(f"Scanning directory: {base_dir}"))
        self.stdout.write(self.style.NOTICE("=" * 70))

        course_folders = sorted([d for d in base_dir.iterdir() if d.is_dir()])
        total_slides_processed = 0

        for folder in course_folders:
            manifest_path = folder / "manifest.json"
            slides_path = folder / "slides"
            modules_path = folder / "modules"

            if not manifest_path.exists():
                continue

            try:
                with open(manifest_path, 'r', encoding='utf-8') as f:
                    manifest = json.load(f)
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Failed to read {manifest_path}: {e}"))
                continue

            slug = manifest.get('slug', folder.name)
            title = manifest.get('title', slug)

            if target_course and slug != target_course and folder.name != target_course:
                continue

            self.stdout.write(self.style.SUCCESS(f"\n📂 Program: {title} ({slug})"))
            self.stdout.write(f"   Folder: {folder.name}")

            if not slides_path.exists():
                self.stdout.write(self.style.WARNING(f"   [!] Slides folder missing: {slides_path}"))
                continue

            pptx_files = sorted(list(slides_path.glob("*.pptx")) + list(slides_path.glob("*.ppt")))
            if not pptx_files:
                self.stdout.write(
                    self.style.WARNING(
                        f"   ℹ️  No PowerPoint files found in {slides_path.name}/. "
                        f"Drop .pptx files here to rebuild course lessons."
                    )
                )
                continue

            # We found PowerPoint files!
            self.stdout.write(self.style.SUCCESS(f"   Found {len(pptx_files)} presentation(s):"))

            # Retrieve or locate Django course
            course_obj = None
            if not dry_run:
                course_obj = Course.objects.filter(slug=slug).first()
                if not course_obj:
                    admin_user = User.objects.filter(role=UserRole.ADMIN).first()
                    course_obj = Course.objects.create(
                        title=title,
                        slug=slug,
                        description=manifest.get('description', ''),
                        is_published=True,
                        is_official=True,
                        owner=admin_user,
                    )
                    self.stdout.write(self.style.SUCCESS(f"   Created Course in DB: {title}"))

            for pptx in pptx_files:
                self.stdout.write(f"   -> Processing presentation: {pptx.name}")
                slides_data = extract_pptx_slides(str(pptx))
                total_slides_processed += len(slides_data)
                self.stdout.write(f"      Parsed {len(slides_data)} slides successfully.")

                # Format extracted text into comprehensive Markdown lesson body
                lesson_body = f"# {pptx.stem.replace('_', ' ')}\n\n"
                lesson_body += f"> *Automatically reconstructed from lecture presentation `{pptx.name}` by Myanmar E-Learning AI Engine.*\n\n"

                for s in slides_data:
                    lesson_body += f"## Slide {s['slide_number']}: {s['title']}\n\n"
                    if s['bullets']:
                        for b in s['bullets']:
                            lesson_body += f"- {b}\n"
                        lesson_body += "\n"
                    if s['notes']:
                        lesson_body += f"**Instructor Lecture Notes:**\n> {s['notes']}\n\n"

                if gen_prompts:
                    modules_path.mkdir(parents=True, exist_ok=True)
                    prompt_file = modules_path / f"ai_prompt_{slugify(pptx.stem)}.md"
                    prompt_content = (
                        f"# AI Course Rebuilding Prompt for: {title}\n"
                        f"## Presentation: {pptx.name}\n\n"
                        f"You are an expert curriculum designer and educator for Myanmar E-Learning.\n"
                        f"Transform the following extracted slide content into an in-depth, production-ready "
                        f"lesson syllabus with explanations, code examples, hands-on activities, and a 5-question quiz.\n\n"
                        f"```markdown\n{lesson_body}\n```\n"
                    )
                    with open(prompt_file, 'w', encoding='utf-8') as pf:
                        pf.write(prompt_content)
                    self.stdout.write(self.style.SUCCESS(f"      Generated AI Prompt: {prompt_file.name}"))

                if not dry_run and course_obj:
                    # Match or create Module
                    mod_order = 1
                    mod_match = re.search(r'(?:MOD[-_]?|Module[-_]?)(\d+)', pptx.stem, re.IGNORECASE)
                    if mod_match:
                        mod_order = int(mod_match.group(1))

                    module, _ = Module.objects.get_or_create(
                        course=course_obj,
                        order=mod_order,
                        defaults={
                            'code': f"MOD-{mod_order:02d}",
                            'title': pptx.stem.replace('_', ' '),
                            'summary': f"Curriculum module generated from {pptx.name}",
                        }
                    )

                    # Create or update lesson
                    lesson_order = module.lessons.count() + 1
                    lesson_title = pptx.stem.replace('_', ' ')
                    lesson, created = Lesson.objects.update_or_create(
                        module=module,
                        title=lesson_title,
                        defaults={
                            'order': lesson_order,
                            'lesson_type': LessonType.TEXT,
                            'content': lesson_body,
                            'duration_minutes': max(15, len(slides_data) * 3),
                        }
                    )
                    action_str = "Created" if created else "Updated"
                    self.stdout.write(self.style.SUCCESS(f"      [DB] {action_str} Lesson: {lesson.title} in Module {module.code}"))

        self.stdout.write(self.style.NOTICE("\n" + "=" * 70))
        if dry_run:
            self.stdout.write(self.style.NOTICE(f"[Dry Run] Successfully scanned {total_slides_processed} slides across all curricula."))
        else:
            self.stdout.write(self.style.SUCCESS(f"Rebuilder finished. Total slides processed: {total_slides_processed}."))
        self.stdout.write(self.style.NOTICE("=" * 70))
