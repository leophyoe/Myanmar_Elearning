from django.test import TestCase
from django.urls import reverse
from apps.users.models import User, UserRole
from apps.courses.models import Course, Module, Lesson, Quiz, Question, Choice, Assignment, AssignmentSubmission
from apps.courses.forms import QuestionForm, QuestionFormSet


class QuizAndAssignmentBuilderTests(TestCase):
    def setUp(self):
        self.teacher = User.objects.create_user(
            username='instructor_test',
            email='instructor@test.com',
            password='password123',
            role=UserRole.TEACHER,
        )
        self.course = Course.objects.create(
            title='Python Fullstack & Cyber Defense',
            slug='python-fullstack-cyber',
            owner=self.teacher,
            status=Course.Status.PUBLISHED,
        )
        self.module = Module.objects.create(
            course=self.course,
            title='Chapter 1: Network Fundamentals',
            code='MOD-101',
            order=1,
        )
        self.lesson = Lesson.objects.create(
            module=self.module,
            title='TCP/IP and OSI Layer Architecture',
            order=1,
            estimated_minutes=30,
        )
        self.quiz = Quiz.objects.create(
            title='Lesson 1 Checkpoint Quiz',
            lesson=self.lesson,
            course=self.course,
            module=self.module,
            passing_percentage=70,
        )

    def test_question_form_multiple_choice_validation_and_saving(self):
        """Test QuestionForm saves multiple choice with single correct answer."""
        data = {
            'order': 1,
            'prompt': 'Which protocol operates on TCP port 443?',
            'question_type': Question.QuestionType.MULTIPLE_CHOICE,
            'points': 10,
            'choice_1': 'HTTP',
            'choice_2': 'HTTPS',
            'choice_3': 'SSH',
            'choice_4': 'FTP',
            'correct_choice': 2,
            'explanation': 'HTTPS uses port 443 by default.',
        }
        form = QuestionForm(data=data)
        self.assertTrue(form.is_valid(), form.errors)
        question = form.save(commit=False)
        question.quiz = self.quiz
        question.save()
        form.save_m2m()

        self.assertEqual(question.question_type, Question.QuestionType.MULTIPLE_CHOICE)
        self.assertEqual(question.choices.count(), 4)
        correct_choice = question.choices.filter(is_correct=True).first()
        self.assertIsNotNone(correct_choice)
        self.assertEqual(correct_choice.text, 'HTTPS')

    def test_question_form_multiple_select_validation_and_saving(self):
        """Test QuestionForm saves multiple select checkboxes with multiple correct answers."""
        data = {
            'order': 2,
            'prompt': 'Which of the following are transport layer protocols?',
            'question_type': Question.QuestionType.MULTIPLE_SELECT,
            'points': 15,
            'choice_1': 'TCP',
            'choice_2': 'UDP',
            'choice_3': 'IP',
            'choice_4': 'ICMP',
            'correct_choices_multi': '1,2',
            'explanation': 'TCP and UDP operate at Layer 4 (Transport).',
        }
        form = QuestionForm(data=data)
        self.assertTrue(form.is_valid(), form.errors)
        question = form.save(commit=False)
        question.quiz = self.quiz
        question.save()
        form.save_m2m()

        self.assertEqual(question.question_type, Question.QuestionType.MULTIPLE_SELECT)
        correct_choices = list(question.choices.filter(is_correct=True).values_list('text', flat=True))
        self.assertIn('TCP', correct_choices)
        self.assertIn('UDP', correct_choices)
        self.assertEqual(len(correct_choices), 2)

    def test_question_form_true_false_auto_population(self):
        """Test QuestionForm handles True/False choices automatically."""
        data = {
            'order': 3,
            'prompt': 'Ethernet operates at the Data Link Layer (Layer 2).',
            'question_type': Question.QuestionType.TRUE_FALSE,
            'points': 10,
            'correct_choice': 1,
        }
        form = QuestionForm(data=data)
        self.assertTrue(form.is_valid(), form.errors)
        question = form.save(commit=False)
        question.quiz = self.quiz
        question.save()
        form.save_m2m()

        self.assertEqual(question.question_type, Question.QuestionType.TRUE_FALSE)
        true_choice = question.choices.filter(text='True').first()
        false_choice = question.choices.filter(text='False').first()
        self.assertIsNotNone(true_choice)
        self.assertIsNotNone(false_choice)
        self.assertTrue(true_choice.is_correct)
        self.assertFalse(false_choice.is_correct)

    def test_question_form_fill_in_the_blank(self):
        """Test QuestionForm saves fill in the blank with pipe separated variants."""
        data = {
            'order': 4,
            'prompt': 'What command line tool sends ICMP Echo Request packets to test network connectivity?',
            'question_type': Question.QuestionType.FILL_IN_BLANK,
            'points': 10,
            'correct_text_answer': 'ping | ping.exe | PING',
            'explanation': 'The ping command uses ICMP to verify reachability.',
        }
        form = QuestionForm(data=data)
        self.assertTrue(form.is_valid(), form.errors)
        question = form.save(commit=False)
        question.quiz = self.quiz
        question.save()
        form.save_m2m()

        self.assertEqual(question.question_type, Question.QuestionType.FILL_IN_BLANK)
        self.assertEqual(question.correct_text_answer, 'ping | ping.exe | PING')

    def test_question_form_short_answer_and_coding(self):
        """Test QuestionForm saves short answer and coding problem with criteria."""
        data = {
            'order': 5,
            'prompt': 'Write a Python function named check_port that returns True if a socket connection succeeds.',
            'question_type': Question.QuestionType.CODING,
            'points': 20,
            'correct_text_answer': 'def check_port | socket.socket | connect',
            'rubric_criteria': 'Must handle socket timeout or connection errors gracefully.',
        }
        form = QuestionForm(data=data)
        self.assertTrue(form.is_valid(), form.errors)
        question = form.save(commit=False)
        question.quiz = self.quiz
        question.save()
        form.save_m2m()

        self.assertEqual(question.question_type, Question.QuestionType.CODING)
        self.assertIn('def check_port', question.correct_text_answer)
        self.assertIn('socket timeout', question.rubric_criteria)

    def test_quiz_builder_view_saves_formset(self):
        """Test QuizBuilderView saves multiple questions via formset POST."""
        self.client.login(username='instructor_test', password='password123')
        url = reverse('quiz-edit', kwargs={'lesson_id': self.lesson.id})

        post_data = {
            'title': 'Comprehensive Network Quiz',
            'passing_percentage': 75,
            'max_attempts': 3,
            'questions-TOTAL_FORMS': '2',
            'questions-INITIAL_FORMS': '0',
            'questions-MIN_NUM_FORMS': '0',
            'questions-MAX_NUM_FORMS': '1000',
            # Question 1: MCQ
            'questions-0-order': '1',
            'questions-0-prompt': 'What does DNS stand for?',
            'questions-0-question_type': 'multiple_choice',
            'questions-0-points': '10',
            'questions-0-choice_1': 'Domain Name System',
            'questions-0-choice_2': 'Data Network Server',
            'questions-0-choice_3': 'Dynamic Node Service',
            'questions-0-choice_4': 'Digital Naming Standard',
            'questions-0-correct_choice': '1',
            # Question 2: Fill in Blank
            'questions-1-order': '2',
            'questions-1-prompt': 'Which port is used by SSH by default?',
            'questions-1-question_type': 'fill_in_blank',
            'questions-1-points': '10',
            'questions-1-correct_text_answer': '22',
        }

        response = self.client.post(url, post_data)
        self.assertEqual(response.status_code, 302)

        self.quiz.refresh_from_db()
        self.assertEqual(self.quiz.title, 'Comprehensive Network Quiz')
        self.assertEqual(self.quiz.questions.count(), 2)

        q1 = self.quiz.questions.get(order=1)
        self.assertEqual(q1.question_type, Question.QuestionType.MULTIPLE_CHOICE)
        self.assertEqual(q1.choices.filter(is_correct=True).first().text, 'Domain Name System')

        q2 = self.quiz.questions.get(order=2)
        self.assertEqual(q2.question_type, Question.QuestionType.FILL_IN_BLANK)
        self.assertEqual(q2.correct_text_answer, '22')

    def test_assignment_create_and_listing(self):
        """Test creating an assignment for a chapter/module."""
        self.client.login(username='instructor_test', password='password123')
        url = reverse('assignment-create')

        post_data = {
            'module': str(self.module.id),
            'title': 'Wireshark Packet Analysis Homework',
            'description': 'Capture a 3-way TCP handshake and submit a screenshot and packet summary.',
            'max_score': 100,
        }

        response = self.client.post(url, post_data)
        self.assertEqual(response.status_code, 302)

        assignment = Assignment.objects.filter(module=self.module, title='Wireshark Packet Analysis Homework').first()
        self.assertIsNotNone(assignment)
        self.assertEqual(assignment.max_score, 100)
