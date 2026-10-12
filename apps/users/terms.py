"""
THUTA Platform Policy Terms, Codes of Conduct, and Versioned Agreements.
Provides canonical terms content, eligibility criteria, and agreement recording services.
"""
from typing import Dict, Any, Optional
from django.utils import timezone


CURRENT_TERMS_VERSION = '2026.1'

TERMS_DEFINITIONS = {
    'student_registration': {
        'version': '2026.1',
        'title': 'Student Registration Terms & Privacy Policy',
        'title_my': 'ကျောင်းသား မှတ်ပုံတင်ခြင်း စည်းမျဉ်းများနှင့် ကိုယ်ရေးအချက်အလက် မူဝါဒ',
        'summary': 'Academic integrity, fair platform use, credential verification rules, and safeguarding policies.',
        'clauses': [
            'All assessments, challenges, and labs must be performed by the registered account holder.',
            'Course materials are for individual educational use and may not be redistributed without authorization.',
            'Respectful communication is required with all faculty members, teaching assistants, and fellow students.',
            'Account credentials and access tokens are strictly personal and non-transferable.'
        ]
    },
    'teacher_application': {
        'version': '2026.1',
        'title': 'Faculty Application & Teaching Agreement',
        'title_my': 'ဆရာ/ဆရာမ လျှောက်ထားခြင်းနှင့် သင်ကြားရေး သဘောတူညီချက်',
        'summary': 'Mandatory free tutorial contribution, intellectual property declaration, code of conduct, and pedagogy guidelines.',
        'clauses': [
            'Requirement of Qualifying Free Tutorial: An approved Teacher must submit at least one qualifying free tutorial for academic review to activate teaching standing.',
            'Entry-Level Scope: Teachers at the entry-level Teacher status may publish approved free tutorials and open learning resources. Paid course publishing requires promotion to an Instructor rank.',
            'Copyright & Content Ownership: All submitted lecture materials, slides, code examples, and videos must be original work or properly licensed.',
            'Student Safeguarding: Instructors must uphold student privacy, refrain from collecting out-of-band contact info, and comply with safety guidelines.',
            'Quality Standards: Video and audio lectures must adhere to minimum production, audio clarity, and instructional structure guidelines.'
        ]
    },
    'instructor_promotion': {
        'version': '2026.1',
        'title': 'Instructor Promotion & Paid Content Revenue Share Terms',
        'title_my': 'Instructor အဆင့်တိုးမြှင့်ခြင်းနှင့် သင်ရိုး ဝင်ငွေခွဲဝေမှု စည်းမျဉ်းများ',
        'summary': 'Paid course monetization permissions, revenue-sharing split tiers, dispute handling, and policy adherence.',
        'clauses': [
            'Revenue Sharing Hierarchy: Paid course sales follow the platform revenue share split calculated on actual student payment after discounts:',
            '  • Associate Instructor: THUTA 60%, Instructor 40%',
            '  • Instructor: THUTA 50%, Instructor 50%',
            '  • Professional Instructor: THUTA 40%, Instructor 60%',
            'Transaction Freezing: Revenue split percentages and amounts are permanently frozen at the time of each payment transaction and will not retroactively alter historical ledgers upon future promotions.',
            'Refunds & Disputes: If a student payment is lawfully refunded or rejected, the corresponding instructor revenue allocation is proportionally adjusted.',
            'Community Contribution: Promoted instructors agree to maintain their qualifying free tutorials as an ongoing public educational contribution.',
            'Administrative Oversight: Instructor levels, course publishing approvals, and commission assignments are subject to administrative audit and may be suspended upon policy violations.'
        ]
    },
    'course_publishing': {
        'version': '2026.1',
        'title': 'Course Publishing Declaration & Academic Quality Standard',
        'title_my': 'သင်ရိုး ထုတ်ဝေခြင်း ဝန်ခံချက်နှင့် ပညာရေး အရည်အသွေး စံချိန်စံညွှန်း',
        'summary': 'Accuracy of course content, technical validity, exam criteria, and intellectual property warranty.',
        'clauses': [
            'Instructor warrants that the course content does not infringe third-party patents, copyrights, or trade secrets.',
            'Cyber Range and security tutorials must adhere strictly to ethical defensive practices and safety guidelines.',
            'Pricing and discount declarations must accurately reflect educational value and student expectations.'
        ]
    }
}


def get_terms_content(terms_type: str, version: Optional[str] = None) -> Dict[str, Any]:
    """Retrieves canonical versioned terms content."""
    terms_info = TERMS_DEFINITIONS.get(terms_type)
    if not terms_info:
        return {
            'version': version or CURRENT_TERMS_VERSION,
            'title': 'Platform Terms and Policies',
            'summary': 'General platform terms and conditions.',
            'clauses': ['Users must abide by all applicable platform terms and policies.']
        }
    return terms_info


def record_term_agreement(
    user,
    terms_type: str,
    request=None,
    version: Optional[str] = None,
    terms_version: Optional[str] = None,
    metadata: Optional[dict] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
):
    """
    Persists a versioned policy agreement record for the user.
    """
    from apps.users.models import TermAgreement

    ver = terms_version or version or CURRENT_TERMS_VERSION
    ip_addr = ip_address
    ua = user_agent or ''

    if request:
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip_addr = x_forwarded_for.split(',')[0].strip()
        else:
            ip_addr = request.META.get('REMOTE_ADDR')
        ua = request.META.get('HTTP_USER_AGENT', '')[:500]

    agreement = TermAgreement.objects.create(
        user=user,
        terms_type=terms_type,
        terms_version=ver,
        ip_address=ip_addr,
        user_agent=ua,
        metadata=metadata or {}
    )
    return agreement


def has_agreed_to_terms(user, terms_type: str, version: Optional[str] = None) -> bool:
    """Checks if the user has accepted the specified version of the terms."""
    if not user or not user.is_authenticated:
        return False
    from apps.users.models import TermAgreement
    ver = version or CURRENT_TERMS_VERSION
    return TermAgreement.objects.filter(
        user=user,
        terms_type=terms_type,
        terms_version=ver
    ).exists()

