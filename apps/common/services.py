"""Shared, dependency-light helpers used by more than one app."""
import io

from django.http import HttpResponse


def qr_png(url, box_size=8, border=2):
    """Render `url` as a PNG QR code and return the raw bytes."""
    import qrcode

    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=box_size,
        border=border,
    )
    qr.add_data(str(url))
    qr.make(fit=True)
    image = qr.make_image(fill_color='black', back_color='white')
    buffer = io.BytesIO()
    image.save(buffer, format='PNG')
    return buffer.getvalue()


def qr_response(url, filename='qr.png'):
    """An HTTP response carrying `url` as a scannable PNG."""
    response = HttpResponse(qr_png(url), content_type='image/png')
    response['Content-Disposition'] = f'inline; filename="{filename}"'
    response['Cache-Control'] = 'public, max-age=3600'
    return response


def absolute_uri(request, path):
    """Full http(s) URL for an internal path — what QR/NFC tags must encode."""
    return request.build_absolute_uri(path)
