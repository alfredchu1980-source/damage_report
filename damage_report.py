import streamlit as st
import requests
import urllib.parse
from PIL import Image
from pyzbar.pyzbar import decode
import io

# ==========================================
# 參數配置區
# ==========================================
try:
    IMGBB_API_KEY = st.secrets["IMGBB_API_KEY"]
except:
    IMGBB_API_KEY = "18af620f9ae7d13d7f46eedc8d2a1664" # 本地測試備用

CS_CONTACTS = {
    "CS_1": {"phone": "85254494485", "apikey": "7932406"},
    "CS_2": {"phone": "85293487111", "apikey": "5290226"},
    "CS_CHINA": {"phone": "85296488174", "apikey": "4339950"}
}

WARNING_TEXT_ZH = "如果兩日內 貴公司未有對有關貨物的處理，向本公司作出任何指示，本公司將會銷售(處理)有關貨物，日後亦不作出任何形式的賠償。"
WARNING_TEXT_EN = "If your company does not provide any instructions regarding the handling of the goods within two days, our company will dispose of/sell the goods and will not provide any form of compensation in the future."

# ==========================================
# 服務層：API 處理與條碼識別
# ==========================================
def upload_image_to_imgbb(image_bytes):
    url = "https://api.imgbb.com/1/upload"
    payload = {"key": IMGBB_API_KEY}
    files = {"image": image_bytes}
    try:
        response = requests.post(url, data=payload, files=files)
        if response.status_code == 200:
            return response.json()["data"]["url"]
        return None
    except Exception as e:
        return None

def extract_barcode(image_bytes):
    """從圖片位元組中擷取條碼"""
    try:
        img = Image.open(io.BytesIO(image_bytes))
        decoded_objects = decode(img)
        if decoded_objects:
            return decoded_objects[0].data.decode("utf-8")
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
st.set_page_config(page_title="貨品損壞報告系統", page_icon="📦")
st.title("📦 快速損壞報告")

target_options = ["全部通知 (All)"] + list(CS_CONTACTS.keys())
selected_target = st.selectbox("請選擇通知對象：", target_options)

damage_reasons = [
    "包裝嚴重破損 / 外箱變形",
    "產品滲漏 / 液體流出",
    "封口破裂 / 失去真空",
    "溫度異常 / 懷疑變質",
    "產品外觀凹陷 / 刮花"
]
selected_reason = st.selectbox("請選擇損壞情況：", damage_reasons)

# 改用 file_uploader 支援多檔與手機原生相機/相簿選擇
uploaded_files = st.file_uploader("拍攝或上傳照片 (最多 3 張，系統將自動掃描條碼)", type=['png', 'jpg', 'jpeg'], accept_multiple_files=True)

if uploaded_files:
    if len(uploaded_files) > 3:
        st.warning("⚠️ 最多只能上傳 3 張照片，系統將只處理前 3 張。")
        uploaded_files = uploaded_files[:3]

    if st.button("📤 提交並通知", use_container_width=True):
        with st.spinner("系統處理中：掃描條碼、上傳圖片與發送訊息..."):
            image_urls = []
            detected_barcode = None

            # 處理每一張照片
            for file in uploaded_files:
                file_bytes = file.getvalue()
                
                # 若尚未找到條碼，則嘗試從當前圖片中讀取
                if not detected_barcode:
                    detected_barcode = extract_barcode(file_bytes)
                
                # 上傳至 ImgBB
                img_url = upload_image_to_imgbb(file_bytes)
                if img_url:
                    image_urls.append(img_url)

            if image_urls:
                # 組合 WhatsApp 訊息
                barcode_text = f"{detected_barcode}" if detected_barcode else "未偵測到條碼"
                
                msg_lines = [
                    "🚨 [損壞報告]",
                    f"單號/條碼：{barcode_text}",
                    f"狀態：{selected_reason}",
                    "照片連結："
                ]
                
                for idx, url in enumerate(image_urls, 1):
                    msg_lines.append(f"圖 {idx}: {url}")
                
                msg_lines.append("\n⚠️ 聲明 / Declaration:")
                msg_lines.append(WARNING_TEXT_ZH)
                msg_lines.append(WARNING_TEXT_EN)

                whatsapp_message = "\n".join(msg_lines)
                
                # 決定發送名單
                targets_to_send = list(CS_CONTACTS.values()) if selected_target == "全部通知 (All)" else [CS_CONTACTS[selected_target]]
                
                all_success = True
                for contact in targets_to_send:
                    if not send_whatsapp_alert(whatsapp_message, contact["phone"], contact["apikey"]):
                        all_success = False
                
                if all_success:
                    st.success(f"✅ 報告已成功發送！(找到條碼：{barcode_text})")
                    st.balloons()
                else:
                    st.warning("⚠️ 部分 WhatsApp 發送失敗。")
            else:
                st.error("❌ 圖片上傳圖床失敗。")
