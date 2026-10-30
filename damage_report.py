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
def process_image_with_watermark(image_bytes):
    """加上紅色時間戳記 (精確至分鐘，鎖定香港時間 UTC+8)"""
    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    draw = ImageDraw.Draw(img)
    hk_time = datetime.utcnow() + timedelta(hours=8)
    current_time = hk_time.strftime("%Y-%m-%d %H:%M")
    font_size = max(40, int(img.height / 20))
    try:
        font = ImageFont.truetype("DejaVuSans.ttf", font_size)
    except IOError:
        try:
            font = ImageFont.truetype("FreeMono.ttf", font_size)
        except IOError:
            font = ImageFont.load_default()
    x, y = 40, 40 
    outline_color = "black"
    for adj_x in [-2, 0, 2]:
        for adj_y in [-2, 0, 2]:
            draw.text((x + adj_x, y + adj_y), current_time, font=font, fill=outline_color)
    draw.text((x, y), current_time, font=font, fill="red")
    output = io.BytesIO()
    img.save(output, format="JPEG")
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
        response = requests.get(url)
        return response.status_code == 200
    except Exception:
        return False

# ==========================================
# 介面層：Streamlit UI
# ==========================================
st.set_page_config(page_title="貨品異常報告系統", page_icon="📦")
st.title("📦 批量異常/損壞報告")

target_options = ["全部通知 (All)"] + list(CS_CONTACTS.keys())
selected_target = st.selectbox("請選擇通知對象 (發送時生效)：", target_options)

st.divider()
st.subheader("1. 新增項目")

damage_reasons = [
    "包裝嚴重破損 / 外箱變形",
    "產品滲漏 / 液體流出",
    "封口破裂 / 失去真空",
    "溫度異常 / 懷疑變質",
    "產品外觀凹陷 / 刮花",
    "實際入庫數量和預報不符"
]
selected_reason = st.selectbox("請選擇情況：", damage_reasons)

discrepancy_type = ""
discrepancy_qty = 0

if selected_reason == "實際入庫數量和預報不符":
    st.info("⚠️ 數量差異詳情")
    discrepancy_type = st.radio("類型：", ["多收", "少收"], horizontal=True)
    discrepancy_qty = st.number_input(f"{discrepancy_type}數量：", min_value=1, step=1)

# 使用動態 Key，讓加入清單後能自動清空上傳框
uploaded_files = st.file_uploader("拍攝或上傳照片 (此 SKU 限定最多 3 張)", type=['png', 'jpg', 'jpeg'], accept_multiple_files=True, key=f"uploader_{st.session_state.uploader_key}")

if st.button("➕ 處理並加入清單", use_container_width=True, type="primary"):
    if not uploaded_files:
        st.warning("⚠️ 請至少上傳一張照片！")
    else:
        with st.spinner("處理中：讀取條碼與上傳照片至 Cloudinary..."):
            files_to_process = uploaded_files[:3]
            image_urls = []
            detected_barcode = None

            for file in files_to_process:
                original_bytes = file.getvalue()
                if not detected_barcode:
                    detected_barcode = extract_barcode(original_bytes)
                
                watermarked_bytes = process_image_with_watermark(original_bytes)
                img_url = upload_image_to_cloudinary(watermarked_bytes)
                if img_url:
                    image_urls.append(img_url)
            
            if image_urls:
                final_reason = f"{selected_reason} ({discrepancy_type} {discrepancy_qty} 件)" if selected_reason == "實際入庫數量和預報不符" else selected_reason
                barcode_text = f"{detected_barcode}" if detected_barcode else "未偵測到條碼"
                
                # 寫入購物車清單
                st.session_state.cart.append({
                    "barcode": barcode_text,
                    "reason": final_reason,
                    "images": image_urls
                })
                
                # 更新 uploader_key 以清空檔案上傳區
                st.session_state.uploader_key += 1
                st.rerun()
            else:
                st.error("❌ 照片上傳至 Cloudinary 失敗，請重試。")

st.divider()
st.subheader(f"2. 待發送清單 ({len(st.session_state.cart)} 項)")

if not st.session_state.cart:
    st.info("清單目前是空的。請在上方新增項目。")
else:
    for idx, item in enumerate(st.session_state.cart, 1):
        st.markdown(f"**項目 {idx}** | 條碼：`{item['barcode']}` | 狀態：{item['reason']} | 附圖：{len(item['images'])} 張")
    
    if st.button("🗑️ 清空清單"):
        st.session_state.cart = []
        st.rerun()

    if st.button("📤 一次過發送所有報告 (消耗 1 次 API)", use_container_width=True):
        with st.spinner("正在合併報告並發送至 WhatsApp..."):
            msg_lines = [f"🚨 [批量異常/損壞報告] (共 {len(st.session_state.cart)} 項)\n"]
            
            for idx, item in enumerate(st.session_state.cart, 1):
                msg_lines.append(f"--- 項目 {idx} ---")
                msg_lines.append(f"單號/條碼：{item['barcode']}")
                msg_lines.append(f"狀態：{item['reason']}")
                msg_lines.append("照片：")
                for img_idx, url in enumerate(item['images'], 1):
                    msg_lines.append(f"圖 {img_idx}: {url}")
                msg_lines.append("") # 空行分隔
            
            msg_lines.append("⚠️ 聲明 / Declaration:")
            msg_lines.append(WARNING_TEXT_ZH)
            msg_lines.append(WARNING_TEXT_EN)

            whatsapp_message = "\n".join(msg_lines)
            
            targets_to_send = list(CS_CONTACTS.values()) if selected_target == "全部通知 (All)" else [CS_CONTACTS[selected_target]]
            
            all_success = True
            for contact in targets_to_send:
                if not send_whatsapp_alert(whatsapp_message, contact["phone"], contact["apikey"]):
                    all_success = False
            
            if all_success:
                st.success("✅ 批量報告已成功發送！")
                st.balloons()
                st.session_state.cart = [] # 發送成功後清空購物車
                st.session_state.uploader_key += 1
            else:
                st.warning("⚠️ 部分發送失敗，請確認 CallMeBot 設定或 API 額度。")
