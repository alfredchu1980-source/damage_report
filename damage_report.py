import streamlit as st
import requests
import urllib.parse
from PIL import Image, ImageDraw, ImageFont, ImageEnhance
from pyzbar.pyzbar import decode
from datetime import datetime, timedelta
import io

# ==========================================
# 參數配置區
# ==========================================
CS_CONTACTS = {
    "CS_1": {"phone": "85254494485", "apikey": "7932406"},
    "CS_2": {"phone": "85293487111", "apikey": "5290226"},
    "CS_CHINA": {"phone": "85296488174", "apikey": "4339950"}
}

WARNING_TEXT_ZH = "如果兩日內 貴公司未有對有關貨物的處理，向本公司作出任何指示，本公司將會棄置或處理有關貨物的，日後亦不作出任何形式的賠償。"
WARNING_TEXT_EN = "If your company does not provide any instructions regarding the handling of the goods within two days, our company will dispose of the goods and will not provide any form of compensation in the future."

# ==========================================
# 初始化 Session State (購物車與 UI 狀態)
# ==========================================
if 'cart' not in st.session_state:
    st.session_state.cart = []
if 'uploader_key' not in st.session_state:
    st.session_state.uploader_key = 0

# ==========================================
# 服務層：影像處理與 API
# ==========================================
def process_image_with_watermark(image_bytes, max_size=(1280, 1280), quality=75):
    """調整尺寸、加上紅色時間戳記並壓縮圖片大小以加快上傳速度"""
    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    
    # 1. 調整圖片尺寸 (保持長寬比)
    if hasattr(Image, 'Resampling'):
        img.thumbnail(max_size, Image.Resampling.LANCZOS)
    else:
        img.thumbnail(max_size, Image.LANCZOS)

    draw = ImageDraw.Draw(img)
    hk_time = datetime.utcnow() + timedelta(hours=8)
    current_time = hk_time.strftime("%Y-%m-%d %H:%M")
    
    font_size = max(30, int(img.height / 20))
    try:
        font = ImageFont.truetype("DejaVuSans.ttf", font_size)
    except IOError:
        try:
            font = ImageFont.truetype("FreeMono.ttf", font_size)
        except IOError:
            font = ImageFont.load_default()
            
    x, y = 20, 20 
    outline_color = "black"
    for adj_x in [-2, 0, 2]:
        for adj_y in [-2, 0, 2]:
            draw.text((x + adj_x, y + adj_y), current_time, font=font, fill=outline_color)
    draw.text((x, y), current_time, font=font, fill="red")
    
    output = io.BytesIO()
    img.save(output, format="JPEG", quality=quality, optimize=True)
    return output.getvalue()

def extract_barcode(image_bytes):
    """從圖片擷取條碼 (雙重嘗試：原圖掃描 + 灰階對比強化)"""
    try:
        raw_img = Image.open(io.BytesIO(image_bytes))
        decoded_objects = decode(raw_img)
        if decoded_objects:
            return decoded_objects[0].data.decode("utf-8")
        
        gray_img = raw_img.convert('L')
        enhancer = ImageEnhance.Contrast(gray_img)
        enhanced_img = enhancer.enhance(2.0)
        decoded_objects = decode(enhanced_img)
        if decoded_objects:
            return decoded_objects[0].data.decode("utf-8")
        return None
    except Exception:
        return None

def upload_image_to_cloudinary(image_bytes):
    """上傳圖片至 Cloudinary (免密碼上傳)"""
    cloud_name = "piic2wdz"
    upload_preset = "damagereport"
    
    url = f"https://api.cloudinary.com/v1_1/{cloud_name}/image/upload"
    data = {"upload_preset": upload_preset}
    files = {"file": image_bytes}
    
    try:
        response = requests.post(url, data=data, files=files)
        if response.status_code == 200:
            return response.json()["secure_url"]
        return None
    except Exception:
        return None

def send_whatsapp_alert(message, phone, apikey):
    encoded_msg = urllib.parse.quote(message)
    url = f"https://api.callmebot.com/whatsapp.php?phone={phone}&text={encoded_msg}&apikey={apikey}"
    try:
