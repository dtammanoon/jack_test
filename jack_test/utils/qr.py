import io
import base64
import pyqrcode  # มากับ Frappe อยู่แล้ว

def get_qr_base64(data, scale=6):
    if not data:
        return ""
    qr = pyqrcode.create(str(data))
    buf = io.BytesIO()
    qr.png(buf, scale=scale, quiet_zone=1)
    return base64.b64encode(buf.getvalue()).decode()