import streamlit as st
import requests
import time

# --- CẤU HÌNH TRANG WEB ---
st.set_page_config(page_title="Test API SSI", layout="wide")
st.title("🔥 THỬ NGHIỆM LẤY DỮ LIỆU SSI REAL-TIME")

# --- HÀM LẤY DỮ LIỆU TỪ SSI ---
def get_vn30f_data(symbol="VN30F1M", resolution="1"):
    url = "https://iboard.ssi.com.vn/dchart/api/1.1/chart/history"
    
    # API SSI thường yêu cầu khoảng thời gian (from, to) tính bằng giây (UNIX timestamp)
    now = int(time.time())
    from_time = now - (24 * 60 * 60) # Lấy lùi lại 1 ngày (24h)
    
    # Các tham số đầy đủ (thay thế cho dấu ... bị lỗi)
    params = {
        "symbol": symbol,
        "resolution": resolution,
        "from": from_time,
        "to": now
    }
    
    # Thêm Header giả lập trình duyệt để SSI không chặn
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    try:
        # Thực hiện việc "gõ cửa" SSI
        r = requests.get(url, params=params, headers=headers)
        return r.json() # Trả về dữ liệu dạng JSON
    except Exception as e:
        return {"error": f"Có lỗi xảy ra: {str(e)}"}

# --- GIAO DIỆN HIỂN THỊ ---
st.write("Đang kết nối vào hệ thống của SSI...")

# Nút bấm để tải lại dữ liệu mới nhất
if st.button("🔄 Lấy dữ liệu ngay lúc này"):
    data = get_vn30f_data(symbol="VN30F1M", resolution="1")
    
    if data and "s" in data and data["s"] == "ok":
        st.success("✅ Đã lấy dữ liệu thành công!")
        
        # In toàn bộ dữ liệu thô ra màn hình để bạn xem cấu trúc
        st.write("Dữ liệu thô trả về từ SSI:")
        st.json(data)
    else:
        st.error("❌ SSI từ chối trả dữ liệu hoặc sai cú pháp.")
        st.write(data)
