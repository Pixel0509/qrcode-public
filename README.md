# QR Generator

> Dự án cá nhân — chỉ để test vui. Không dùng cho mục đích thương mại.  
> Personal project — just for fun. Not for commercial use.

**Version:** 26.09.27  
**GitHub:** https://github.com/Pixel0509/qrcode-public

---

## Tiếng Việt

Ứng dụng web tạo mã QR hỗ trợ 6 loại nội dung: Ảnh, Văn bản, URL, Email, Wi-Fi, Sự kiện. Hỗ trợ 2 ngôn ngữ: Tiếng Việt (`/vi/qrcode`) và Tiếng Anh (`/en/qrcode`).

### Tính năng

- Tab Ảnh: nhập API key ImgBB → upload ảnh → tạo QR chứa link ảnh
- Tab Văn bản: mã hóa text tùy ý (tối đa 4096 ký tự, có đếm ký tự)
- Tab URL: tạo QR từ địa chỉ web
- Tab Email: tạo QR kích hoạt soạn email (to, subject, body)
- Tab Wi-Fi: tạo QR kết nối mạng không dây
- Tab Sự kiện: tạo QR lịch iCalendar (tiêu đề, địa điểm, ngày bắt đầu/kết thúc, mô tả)
- Tab Quét QR: đọc QR từ ảnh upload / dán / URL
- Tải mã QR: PNG, SVG, JPEG, Sao chép vào clipboard
- Giao diện sáng/tối, responsive
- Chống spam server-side bằng HMAC token (không thể bypass bằng F12/xóa localStorage)
- Cooldown: tab Ảnh 2 phút/lượt, các tab còn lại 30 giây/lượt
- Nút chuyển ngôn ngữ hiển thị cờ quốc kỳ

### Cấu trúc

```
qr-generator/
├── app.py
├── requirements.txt
├── vercel.json
├── README.md
├── templates/
│   ├── vi/
│   │   └── index.html
│   ├── en/
│   │   └── index.html
│   └── 404.html
└── static/
    ├── favicon/
    │   └── favicon.png
    └── icons/
        ├── github.svg
        ├── tiktok.svg
        ├── vi.webp
        └── en.webp
```

### Cài đặt & chạy local

```bash
pip install -r requirements.txt
python app.py
```

Mở `http://localhost:5000`.

### Deploy Vercel

```bash
npm i -g vercel
vercel
```

### Biến môi trường

| Tên | Mô tả | Bắt buộc |
|-----|-------|----------|
| `IMGBB_API_KEY` | Fallback API key ImgBB nếu người dùng không nhập | Không |
| `QR_SECRET` | Secret key để ký HMAC cooldown token | Khuyến nghị |

### Cơ chế chống spam

Cooldown thực thi server-side bằng HMAC-SHA256 token. Sau mỗi lần tạo QR thành công, server trả về `cd_token` (`kind:timestamp:hmac`), client lưu và gửi kèm lần sau. Server verify chữ ký + thời gian — xóa localStorage không có tác dụng.

### Lưu ý

- Ảnh tải lên lưu trên tài khoản ImgBB của người dùng
- Link ảnh là **công khai** — bất kỳ ai có link đều xem được
- Tuyệt đối không tải ảnh riêng tư, CCCD, tài liệu nhạy cảm

---

## English

A web app for generating QR codes supporting 6 content types: Image, Text, URL, Email, Wi-Fi, Event. Available in two languages: Vietnamese (`/vi/qrcode`) and English (`/en/qrcode`).

### Features

- Image tab: enter your ImgBB API key → upload image → generate QR containing the image link
- Text tab: encode arbitrary text (up to 4096 characters, with character counter)
- URL tab: generate QR from a web address
- Email tab: generate QR that opens a compose window (to, subject, body)
- Wi-Fi tab: generate QR to connect to a wireless network
- Event tab: generate iCalendar QR (title, location, start/end date, description)
- Scan QR tab: read QR from uploaded image / clipboard paste / URL
- Download QR: PNG, SVG, JPEG, Copy to clipboard
- Light/dark theme, responsive layout
- Server-side anti-spam via HMAC token (cannot be bypassed via DevTools or clearing localStorage)
- Cooldown: Image tab 2 min/request, all other tabs 30 sec/request
- Language toggle button shows national flag

### Project Structure

```
qr-generator/
├── app.py
├── requirements.txt
├── vercel.json
├── README.md
├── templates/
│   ├── vi/
│   │   └── index.html
│   ├── en/
│   │   └── index.html
│   └── 404.html
└── static/
    ├── favicon/
    │   └── favicon.png
    └── icons/
        ├── github.svg
        ├── tiktok.svg
        ├── vi.webp
        └── en.webp
```

### Installation & local run

```bash
pip install -r requirements.txt
python app.py
```

Open `http://localhost:5000`.

### Deploy to Vercel

```bash
npm i -g vercel
vercel
```

### Environment variables

| Name | Description | Required |
|------|-------------|----------|
| `IMGBB_API_KEY` | Fallback ImgBB API key if user doesn't provide one | No |
| `QR_SECRET` | Secret key for signing HMAC cooldown tokens | Recommended |

### Anti-spam mechanism

Cooldown is enforced server-side using HMAC-SHA256 tokens. After each successful QR generation, the server returns a `cd_token` (`kind:timestamp:hmac`), which the client stores and sends with subsequent requests. The server verifies the signature and timestamp — clearing localStorage has no effect.

### Notes

- Uploaded images are stored on the user's own ImgBB account
- Image links are **public** — anyone with the link can view them
- Never upload private photos, ID cards, or sensitive documents

---

## License

Personal project, no license. Use freely at your own risk.
