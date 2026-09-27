import os
import mimetypes
from django.core.exceptions import ValidationError
from django.conf import settings

def validate_resource_file(file_obj):
    """
    Validates uploaded course resource files to strictly prevent malicious uploads.
    Enforces:
    - Maximum file size limit
    - Allowed extension list
    - Rejection of executable extensions
    - Basic MIME type validation
    """
    max_size = getattr(settings, 'MAX_UPLOAD_SIZE_MB', 25) * 1024 * 1024
    if file_obj.size > max_size:
        raise ValidationError(f"File size exceeds the maximum allowed limit of {settings.MAX_UPLOAD_SIZE_MB}MB.")

    name = file_obj.name.lower()
    ext = os.path.splitext(name)[1].lstrip('.')

    # 1. Reject hazardous executable and script extensions
    disallowed_extensions = getattr(settings, 'DISALLOWED_RESOURCE_EXTENSIONS', [
        'exe', 'sh', 'bat', 'cmd', 'ps1', 'msi', 'bin', 'py', 'php', 'js', 'vbs', 'elf', 'dll', 'so'
    ])
    if ext in disallowed_extensions:
        raise ValidationError(f"Security Alert: Uploading executable file extension '.{ext}' is strictly prohibited.")

    # 2. Check allowed extension list
    allowed_extensions = getattr(settings, 'ALLOWED_RESOURCE_EXTENSIONS', [
        'pdf', 'doc', 'docx', 'ppt', 'pptx', 'txt', 'md',
        'zip', 'tar', 'gz', 'png', 'jpg', 'jpeg', 'svg'
    ])
    if ext not in allowed_extensions:
        raise ValidationError(f"File extension '.{ext}' is not supported. Allowed extensions: {', '.join(allowed_extensions)}")

    # 3. Check content type / MIME
    content_type = getattr(file_obj, 'content_type', '')
    if content_type:
        dangerous_mimes = [
            'application/x-dosexec',
            'application/x-executable',
            'application/x-sh',
            'application/x-bat',
            'application/javascript',
            'text/javascript',
            'application/x-php'
        ]
        if content_type in dangerous_mimes:
            raise ValidationError(f"Security Alert: Executable MIME type '{content_type}' is prohibited.")

    return file_obj

