from django.test import TestCase, Client
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.users.models import User
from apps.courses.models import Course, Module, Lesson
from apps.courses.forms import LessonForm


class VideoTutorialUploadTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.instructor = User.objects.create_user(
            username='videoteacher',
            email='videoteacher@example.com',
            password='Password123!',
            role='instructor',
        )
        self.course = Course.objects.create(
            title="Python Video Masterclass",
            slug="python-video-masterclass",
            owner=self.instructor,
        )
        self.module = Module.objects.create(
            course=self.course,
            title="Module 1: Introduction",
            order=1,
            code="MOD-01",
        )

    def test_lesson_form_accepts_valid_video_formats(self):
        for ext in ['mp4', 'webm', 'mkv', 'mov', 'avi']:
            dummy_video = SimpleUploadedFile(f"test_lecture.{ext}", b"fake video content", content_type="video/mp4")
            form = LessonForm(
                data={
                    'module': self.module.id,
                    'title': f'Video Lecture {ext.upper()}',
                    'lesson_type': 'video',
                    'order': 1,
                    'estimated_minutes': 30,
                    'content_markdown': 'Full lecture notes',
                },
                files={'video_file': dummy_video}
            )
            self.assertTrue(form.is_valid(), f"Form should be valid for extension .{ext}, errors: {form.errors}")

    def test_lesson_form_rejects_oversized_video(self):
        # Create an object with size attribute larger than 1000 MB
        oversized_video = SimpleUploadedFile("huge_lecture.mp4", b"x", content_type="video/mp4")
        oversized_video.size = 1001 * 1024 * 1024  # 1001 MB
        form = LessonForm(
            data={
                'module': self.module.id,
                'title': 'Huge Lecture',
                'lesson_type': 'video',
                'order': 1,
                'estimated_minutes': 45,
                'content_markdown': 'Lecture notes',
            },
            files={'video_file': oversized_video}
        )
        self.assertFalse(form.is_valid())
        self.assertIn('video_file', form.errors)
        self.assertIn('limit is 1000 MB', form.errors['video_file'][0])

    def test_video_embed_url_providers(self):
        # 1. YouTube
        yt_lesson = Lesson(title="YT", video_url="https://www.youtube.com/watch?v=dQw4w9WgXcQ")
        self.assertEqual(yt_lesson.video_embed_url, "https://www.youtube-nocookie.com/embed/dQw4w9WgXcQ?rel=0&modestbranding=1")

        # 2. Vimeo
        vimeo_lesson = Lesson(title="VM", video_url="https://vimeo.com/123456789")
        self.assertEqual(vimeo_lesson.video_embed_url, "https://player.vimeo.com/video/123456789")

        # 3. Google Drive
        gdrive_lesson = Lesson(title="GD", video_url="https://drive.google.com/file/d/1a2b3c4d5e6f7g8h9/view?usp=sharing")
        self.assertEqual(gdrive_lesson.video_embed_url, "https://drive.google.com/file/d/1a2b3c4d5e6f7g8h9/preview")

        # 4. Loom
        loom_lesson = Lesson(title="LM", video_url="https://www.loom.com/share/abc123def456")
        self.assertEqual(loom_lesson.video_embed_url, "https://www.loom.com/embed/abc123def456")

        # 5. Bunny Stream
        bunny_url = "https://iframe.mediadelivery.net/embed/12345/video-guid"
        bunny_lesson = Lesson(title="BS", video_url=bunny_url)
        self.assertEqual(bunny_lesson.video_embed_url, bunny_url)

    def test_lesson_create_view_and_video_upload(self):
        self.client.force_login(self.instructor)
        video_file = SimpleUploadedFile("my_screencast.mp4", b"dummy video bytes", content_type="video/mp4")
        response = self.client.post(
            reverse('lesson-create') + f"?module={self.module.id}",
            {
                'module': self.module.id,
                'title': 'Hands-on Python Screencast',
                'lesson_type': 'video',
                'order': 1,
                'estimated_minutes': 25,
                'content_markdown': 'Follow the hands-on video above.',
                'video_file': video_file,
            }
        )
        self.assertEqual(response.status_code, 302)
        created_lesson = Lesson.objects.filter(title='Hands-on Python Screencast').first()
        self.assertIsNotNone(created_lesson)
        self.assertTrue(created_lesson.has_video)
        self.assertTrue(bool(created_lesson.video_file))

