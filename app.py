from flask import Flask, request, jsonify
from flask_cors import CORS
import pandas as pd
import requests

app = Flask(__name__)
CORS(app)

# ======= Load Excel with multiple sheets =======
sheets = pd.read_excel("products.xlsx", sheet_name=None)

df_products = sheets.get("Sanpham")
df_promo = sheets.get("Khuyenmai")
df_contact = sheets.get("Lienhe")
df_faq = sheets.get("Hoidap")

# ======= AI Config (OpenRouter API) =======
OPENROUTER_API_KEY = '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'

def ai_generate_reply(message):
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "http://your-site.com",
        "X-Title": "Chatbot Assistant"
    }
    payload = {
        "model": "openai/gpt-3.5-turbo",
        "messages": [
            {"role": "system", "content": "Bạn là một trợ lý bán hàng thân thiện."},
            {"role": "user", "content": message}
        ]
    }
    try:
        response = requests.post(url, headers=headers, json=payload)
        result = response.json()
        if "choices" in result:
            return result['choices'][0]['message']['content']
        else:
            return "Xin lỗi, tôi không hiểu rõ yêu cầu của bạn."
    except Exception as e:
        return "Xin lỗi, đã xảy ra lỗi khi kết nối AI."

# ======= Các hàm xử lý =========
def top_selling(df):
    if "Số lượt bán" not in df.columns:
        return "Dữ liệu lượt bán chưa có."
    top = df.sort_values(by="Số lượt bán", ascending=False).head(3)
    return "Top sản phẩm bán chạy:\n" + "\n".join(
        f"- {row['Tên sản phẩm']} ({int(row['Số lượt bán'])} lượt)" for _, row in top.iterrows()
    )

def current_promos(df_promo):
    if df_promo is None or df_promo.empty:
        return "Hiện chưa có chương trình khuyến mãi nào."
    lines = []
    for _, row in df_promo.iterrows():
        lines.append(f"🎁 {row['TenChuongTrinh']}: {row['MoTa']} (Áp dụng cho: {row['SanPhamApDung']})")
    return "Các chương trình khuyến mãi hiện có:\n" + "\n".join(lines)

def promo_for_product(df_promo, message):
    for _, row in df_promo.iterrows():
        if str(row['SanPhamApDung']).lower() in message:
            return f"🎉 Sản phẩm bạn quan tâm đang nằm trong chương trình: {row['TenChuongTrinh']} - Giảm {row['MucGiam']} ({row['MoTa']})"
    return None

def suggest_by_category(df, message):
    if "Danh mục" not in df.columns:
        return None
    for cat in df["Danh mục"].dropna().unique():
        if str(cat).lower() in message:
            g = df[df["Danh mục"].str.lower() == cat.lower()]
            g = g.sort_values(by="Số lượt bán", ascending=False).head(3)
            return f"Gợi ý {cat}:\n" + "\n".join(f"- {r['Tên sản phẩm']} ({r['Giá']} VND)" for _, r in g.iterrows())
    return None

def detailed_product_info(df, message):
    for _, row in df.iterrows():
        ten_sp = str(row['Tên sản phẩm']).lower()
        if ten_sp in message:
            result = [f"Sản phẩm: {row['Tên sản phẩm']}"]
            if "giá" in message:
                result.append(f"Giá: {row['Giá']} VND")
            if "màu" in message:
                result.append(f"Màu: {row.get('Màu', 'Không rõ')}")
            if "size" in message or "kích cỡ" in message:
                result.append(f"Size: {row.get('Size', 'Không rõ')}")
            if "số lượng" in message:
                result.append(f"Số lượng còn: {row.get('Số lượng', 'Không rõ')}")
            if len(result) == 1:
                result.append(f"Giá: {row['Giá']} VND")
                result.append(f"Màu: {row.get('Màu', 'Không rõ')}")
                result.append(f"Size: {row.get('Size', 'Không rõ')}")
                result.append(f"Số lượng còn: {row.get('Số lượng', 'Không rõ')}")
            return "\n".join(result)
    return None

def faq_response(df_faq, message):
    if df_faq is None:
        return None
    for _, row in df_faq.iterrows():
        if str(row['CauHoiThuongGap']).lower() in message:
            return row['TraLoi']
    return None

def contact_info(df_contact, message):
    keywords = ['liên hệ', 'số điện thoại', 'email', 'hỗ trợ', 'địa chỉ']
    if any(k in message for k in keywords):
        contact_lines = []
        for _, row in df_contact.iterrows():
            thongtin = str(row.get("ThongTin", ""))
            noidung = str(row.get("NoiDung", ""))
            contact_lines.append(f"{thongtin}: {noidung}")
        return "Thông tin liên hệ:\n" + "\n".join(contact_lines)
    return None

# ======= Flask Route =======
@app.route("/chat", methods=["POST"])
def chat():
    message = request.json.get("message", "").lower()

    if "bán chạy" in message:
        return jsonify({"reply": top_selling(df_products)})

    if "khuyến mãi" in message or "giảm giá" in message:
        reply = promo_for_product(df_promo, message)
        if reply:
            return jsonify({"reply": reply})
        return jsonify({"reply": current_promos(df_promo)})

    # Ưu tiên tìm thông tin sản phẩm cụ thể (giá, màu, size,...)
    info = detailed_product_info(df_products, message)
    if info:
        return jsonify({"reply": info})

    suggestion = suggest_by_category(df_products, message)
    if suggestion:
        return jsonify({"reply": suggestion})

    faq = faq_response(df_faq, message)
    if faq:
        return jsonify({"reply": faq})

    contact = contact_info(df_contact, message)
    if contact:
        return jsonify({"reply": contact})

    return jsonify({"reply": ai_generate_reply(message)})

# ======= Start server =======
if __name__ == "__main__":
    app.run(debug=True)