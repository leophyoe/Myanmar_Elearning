from .models import ActivityLog, ActivityAction

class ActivityAuditMiddleware:
    """
    Captures sensitive and operational requests into the immutable ActivityLog.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        # Log specific actions based on request path and method
        if request.user.is_authenticated:
            path = request.path
            action = None

            if 'lab-start' in path and request.method == 'POST':
                action = ActivityAction.LAB_START
            elif 'lab-stop' in path and request.method == 'POST':
                action = ActivityAction.LAB_STOP
            elif 'lab-reset' in path and request.method == 'POST':
                action = ActivityAction.LAB_RESET
            elif 'flag-submit' in path and request.method == 'POST':
                action = ActivityAction.FLAG_SUBMIT
            elif 'quiz/submit' in path and request.method == 'POST':
                action = ActivityAction.QUIZ_SUBMIT

            if action:
                ip = request.META.get('HTTP_X_FORWARDED_FOR', request.META.get('REMOTE_ADDR'))
                if ip and ',' in ip:
                    ip = ip.split(',')[0].strip()

                ActivityLog.objects.create(
                    user=request.user,
                    action=action,
                    ip_address=ip,
                    user_agent=request.META.get('HTTP_USER_AGENT', '')[:255],
                    path=path[:512],
                    metadata={'status_code': response.status_code}
                )

        return response

