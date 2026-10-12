import uuid
from decimal import Decimal
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from apps.courses.models import Course, Module, Lesson, Quiz, Question, Choice, Enrollment, UserProgress
from apps.certificates.models import Certificate

User = get_user_model()


class FinalExamAndCertificateFlowTest(TestCase):
    def setUp(self):
        self.student = User.objects.create_user(
            username='student1',
            email='student1@test.com',
            password='password123',
            first_name='Ko Mg',
            last_name='Mg',
        )
        self.course = Course.objects.create(
            title='Python Zero to Hero',
            slug='python-zero-to-hero',
            description='Master Python Programming from scratch.',
            is_published=True,
            is_official=True,
            price=Decimal('0.00'),
            access_type=Course.AccessType.FREE,
            certificate_eligible=True,
            exam_required=True,
        )
        self.module = Module.objects.create(
            course=self.course,
            title='Module 1: Fundamentals',
            code='MOD-01',
            order=1,
        )
        self.lesson1 = Lesson.objects.create(
            module=self.module,
            title='Lesson 1: Intro to Variables',
            order=1,
            content_markdown='Lesson 1 content',
        )
        self.lesson2 = Lesson.objects.create(
            module=self.module,
            title='Lesson 2: Control Flow',
            order=2,
            content_markdown='Lesson 2 content',
        )

        # Final Assessment / Exam
        self.final_exam = Quiz.objects.create(
            course=self.course,
            title='Python Certified Final Assessment Exam',
            quiz_type=Quiz.AssessmentType.FINAL_EXAM,
            passing_percentage=70,
            status=Quiz.Status.PUBLISHED,
        )
        self.q1 = Question.objects.create(
            quiz=self.final_exam,
            prompt='What is the output of print(2 ** 3)?',
            question_type=Question.QuestionType.MULTIPLE_CHOICE,
            points=10,
        )
        self.choice1_corr = Choice.objects.create(question=self.q1, text='8', is_correct=True)
        self.choice1_wrong = Choice.objects.create(question=self.q1, text='6', is_correct=False)

        # Enrol student
        self.enrollment = Enrollment.objects.create(
            student=self.student,
            course=self.course,
            status=Enrollment.Status.ACTIVE,
        )
        self.client = Client()
        self.client.login(username='student1', password='password123')

    def test_end_to_end_lessons_to_exam_to_certificate_flow(self):
        # 1. Initially, lessons are not completed
        res_course = self.client.get(reverse('course-detail', kwargs={'slug': self.course.slug}))
        self.assertEqual(res_course.status_code, 200)
        self.assertFalse(res_course.context['all_lessons_completed'])
        self.assertIsNone(res_course.context['earned_certificate'])

        # 2. Mark lesson 1 completed
        UserProgress.objects.create(
            user=self.student,
            course=self.course,
            module=self.module,
            lesson=self.lesson1,
            is_completed=True,
        )
        res_lesson1 = self.client.get(reverse('lesson-detail', kwargs={'lesson_id': self.lesson1.id}))
        self.assertEqual(res_lesson1.context['next_lesson'].id, self.lesson2.id)

        # 3. Mark lesson 2 (final lesson) completed
        UserProgress.objects.create(
            user=self.student,
            course=self.course,
            module=self.module,
            lesson=self.lesson2,
            is_completed=True,
        )

        # 4. Check final lesson page: next action routes to Final Exam
        res_lesson2 = self.client.get(reverse('lesson-detail', kwargs={'lesson_id': self.lesson2.id}))
        self.assertEqual(res_lesson2.status_code, 200)
        self.assertIsNone(res_lesson2.context['next_lesson'])
        self.assertTrue(res_lesson2.context['is_last_lesson'])
        self.assertIsNotNone(res_lesson2.context['final_exam'])
        self.assertFalse(res_lesson2.context['final_exam_passed'])
        # Verify the template has link to take final exam
        self.assertContains(res_lesson2, reverse('assessment-detail', kwargs={'slug': self.course.slug, 'assessment_id': self.final_exam.id}))
        self.assertContains(res_lesson2, "Take Final Exam")

        # 5. Check course detail page: all lessons completed banner appears
        res_course_completed = self.client.get(reverse('course-detail', kwargs={'slug': self.course.slug}))
        self.assertEqual(res_course_completed.status_code, 200)
        self.assertTrue(res_course_completed.context['all_lessons_completed'])
        self.assertFalse(res_course_completed.context['final_exam_passed'])
        self.assertIsNone(res_course_completed.context['earned_certificate'])
        self.assertContains(res_course_completed, "Final Assessment Exam ဖြေဆိုပါ")
        self.assertContains(res_course_completed, "Take Final Exam Now")

        # Certificate must NOT be issued yet because final exam has not been passed
        cert_before_exam = Certificate.objects.filter(student=self.student, course=self.course, is_revoked=False).first()
        self.assertIsNone(cert_before_exam)

        # 6. Student opens the Final Exam page
        res_exam = self.client.get(reverse('assessment-detail', kwargs={'slug': self.course.slug, 'assessment_id': self.final_exam.id}))
        self.assertEqual(res_exam.status_code, 200)
        self.assertTrue(res_exam.context['can_attempt'])

        # 7. Student submits the passing answer to the Final Exam
        submit_url = reverse('assessment-submit', kwargs={'slug': self.course.slug, 'assessment_id': self.final_exam.id})
        res_submit = self.client.post(submit_url, {
            f'question_{self.q1.id}': self.choice1_corr.id,
            'time_taken_seconds': 45,
        }, follow=True)
        self.assertEqual(res_submit.status_code, 200)

        # 8. Certificate is now officially issued!
        cert = Certificate.objects.filter(student=self.student, course=self.course, is_revoked=False).first()
        self.assertIsNotNone(cert)
        self.assertTrue(len(cert.certificate_code) > 0)

        # 9. Assessment detail displays the celebration card with certificate link
        self.assertContains(res_submit, "Final Examination အောင်မြင်ပြီး တရားဝင် အောင်လက်မှတ် ရရှိပါပြီ")
        self.assertContains(res_submit, cert.certificate_code)
        self.assertContains(res_submit, reverse('certificate-verify', kwargs={'cert_id': cert.pk}))

        # 10. Course detail now displays Certified Alumnus celebration banner
        res_course_cert = self.client.get(reverse('course-detail', kwargs={'slug': self.course.slug}))
        self.assertEqual(res_course_cert.status_code, 200)
        self.assertIsNotNone(res_course_cert.context['earned_certificate'])
        self.assertTrue(res_course_cert.context['final_exam_passed'])
        self.assertContains(res_course_cert, "CERTIFIED ALUMNUS")
        self.assertContains(res_course_cert, cert.certificate_code)
        self.assertContains(res_course_cert, reverse('certificate-verify', kwargs={'cert_id': cert.pk}))

        # 11. Public Verification page renders successfully
        verify_url = reverse('certificate-verify', kwargs={'cert_id': cert.pk})
        res_verify = self.client.get(verify_url)
        self.assertEqual(res_verify.status_code, 200)
        self.assertContains(res_verify, cert.certificate_code)
        self.assertContains(res_verify, 'Ko Mg Mg')
        self.assertContains(res_verify, 'Python Zero to Hero')

    def test_teacher_creates_final_assessment_and_blocks_until_lessons_completed(self):
        """
        Verify teacher can create a Course Final Assessment, and student is blocked
        from taking it until all curriculum lessons are 100% completed.
        """
        teacher = User.objects.create_user(
            username='teacher_py',
            email='teacher_py@test.com',
            password='password123',
            role='teacher',
        )
        self.course.owner = teacher
        self.course.exam_required = False
        self.course.save(update_fields=['owner', 'exam_required'])

        # 1. Teacher visits exam creation with ?course=<id>
        self.client.login(username='teacher_py', password='password123')
        create_url = reverse('standalone-exam-create') + f"?course={self.course.id}"
        resp_get = self.client.get(create_url)
        self.assertEqual(resp_get.status_code, 200)

        # 2. Teacher submits the new course final assessment
        post_data = {
            'title': f'{self.course.title} Comprehensive Final Exam',
            'course': str(self.course.id),
            'description': 'Final assessment testing full syllabus.',
            'quiz_type': Quiz.AssessmentType.FINAL_EXAM,
            'status': Quiz.Status.PUBLISHED,
            'price': '0',
            'time_limit_minutes': 45,
            'passing_percentage': 75,
            'max_attempts': 3,
            'certificate_type': 'course_completion',
        }
        resp_post = self.client.post(reverse('standalone-exam-create'), post_data)
        self.assertEqual(resp_post.status_code, 302)

        # 3. Exam created and course marked exam_required
        created_exam = Quiz.objects.filter(course=self.course, title__contains='Comprehensive Final Exam').first()
        self.assertIsNotNone(created_exam)
        self.course.refresh_from_db()
        self.assertTrue(self.course.exam_required)

        # 4. Teacher accesses question builder for this exam
        edit_q_url = reverse('quiz-edit', kwargs={'lesson_id': created_exam.id})
        resp_q = self.client.get(edit_q_url)
        self.assertEqual(resp_q.status_code, 200)

        # 5. Student cannot take exam before finishing lessons
        new_student = User.objects.create_user(
            username='fresh_student',
            email='fresh@test.com',
            password='password123',
        )
        Enrollment.objects.create(student=new_student, course=self.course, status=Enrollment.Status.ACTIVE)
        self.client.login(username='fresh_student', password='password123')

        exam_url = reverse('assessment-detail', kwargs={'slug': self.course.slug, 'assessment_id': created_exam.id})
        resp_blocked = self.client.get(exam_url)
        self.assertEqual(resp_blocked.status_code, 200)
        self.assertFalse(resp_blocked.context['can_attempt'])
        self.assertContains(resp_blocked, "Final Assessment Locked")

        # 6. Student completes all lessons
        UserProgress.objects.create(user=new_student, course=self.course, lesson=self.lesson1, is_completed=True)
        UserProgress.objects.create(user=new_student, course=self.course, lesson=self.lesson2, is_completed=True)

        # 7. Exam unlocks!
        resp_unlocked = self.client.get(exam_url)
        self.assertEqual(resp_unlocked.status_code, 200)
        self.assertTrue(resp_unlocked.context['can_attempt'])
