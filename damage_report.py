import streamlit as st
import requests
import urllib.parse

# ==========================================
# 參數配置區
# ==========================================
IMGBB_API_KEY = st.secrets["IMGBB_API_KEY"]

# 設定多組 CS 聯絡人資料
CS_CONTACTS = {
    "CS_1": {"phone": "85254494485", "apikey": "7932406"},
    "CS_2": {"phone": "85293487111", "apikey": "5290226"},
    "CS_CHINA": {"phone": "85296488174", "apikey": "4339950"}
}

# ==========================================
# 服務層：API 處理
# ==========================================
def upload_image_to_imgbb(image_bytes):
    """將圖片上傳至 ImgBB 並取得公開 URL"""
    url = "https://api.imgbb.com/1/upload"
    payload = {"key": IMGBB_API_KEY}
    files = {"image": image_bytes}
    try:
        response = requests.post(url, data=payload, files=files)
        if response.status_code == 200:
            return response.json()["data"]["url"]
        return None
    except Exception as e:
        st.error(f"圖片上傳失敗: {e}")
        return None

def send_whatsapp_alert(message, phone, apikey):
    """透過 CallMeBot 發送 WhatsApp 訊息給指定對象"""
    encoded_msg = urllib.parse.quote(message)
    url = f"https://api.callmebot.com/whatsapp.php?phone={phone}&text={encoded_msg}&apikey={apikey}"
    try:
        response = requests.get(url)
        return response.status_code == 200
    except Exception as e:
        st.error(f"WhatsApp 發送失敗 ({phone}): {e}")
        return False

# ==========================================
# 介面層：Streamlit UI
# ==========================================
st.set_page_config(page_title="貨品損壞報告系統", page_icon="📦")
st.title("📦 快速損壞報告")

# 通知對象選擇
target_options = ["全部通知 (All)"] + list(CS_CONTACTS.keys())
selected_target = st.selectbox("請選擇通知對象：", target_options)

# 5 個常見的損壞原因下拉選單
damage_reasons = [
    "包裝嚴重破損 / 外箱變形",
    "產品滲漏 / 液體流出",
    "封口破裂 / 失去真空",
    "溫度異常 / 懷疑變質",
    "產品外觀凹陷 / 刮花"
]
selected_reason = st.selectbox("請選擇損壞情況：", damage_reasons)

# 啟動手機相機拍照
captured_image = st.camera_input("拍攝損壞照片 (請盡量拍到單號或標籤)")

if captured_image is not None:
    if st.button("📤 提交並通知", use_container_width=True):
        with st.spinner("系統處理中，圖片上傳與發送訊息..."):
            image_url = upload_image_to_imgbb(captured_image.getvalue())
            
            if image_url:
                whatsapp_message = f"🚨 [損壞報告]\n狀態：{selected_reason}\n照片：{image_url}"
                
                # 決定發送名單
                targets_to_send = []
                if selected_target == "全部通知 (All)":
                    targets_to_send = list(CS_CONTACTS.values())
                else:
                    targets_to_send = [CS_CONTACTS[selected_target]]
                
                # 執行批量或單次發送
                all_success = True
                for contact in targets_to_send:
                    success = send_whatsapp_alert(whatsapp_message, contact["phone"], contact["apikey"])
                    if not success:
                        all_success = False
                
                if all_success:
                    st.success("✅ 報告已成功發送！")
                    st.balloons()
                else:
                    st.warning("⚠️ 部分或全部 WhatsApp 發送失敗，請檢查 API 設定。")
            else:
                st.error("❌ 圖片上傳圖床失敗，請稍後再試。")
