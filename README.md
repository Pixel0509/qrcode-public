# QR Generator

> Dự án cá nhân — chỉ để test vui. Không dùng cho mục đích thương mại.

**Version:** 26.09.27

Ứng dụng web tạo mã QR hỗ trợ 6 loại nội dung: Ảnh, Văn bản, URL, Email, Wi-Fi, Sự kiện. Hỗ trợ 2 ngôn ngữ: Tiếng Việt (`/vi/qrcode`) và Tiếng Anh (`/en/qrcode`).

## Tính năng

- Tab Ảnh: nhập API key ImgBB của bạn → upload ảnh → tạo QR chứa link ảnh
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
- Nút chuyển ngôn ngữ hiển thị cờ quốc kỳ (`static/icons/vi.webp`, `static/icons/en.webp`)
- Mã nguồn công khai tại GitHub

## Cấu trúc

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
        ├── tiktok.svg
        ├── vi.webp
        └── en.webp
```

## Cài đặt & chạy local

```bash
pip install -r requirements.txt
python app.py
```

Mở `http://localhost:5000`.

## Deploy Vercel

```bash
npm i -g vercel
vercel
```

## Biến môi trường

| Tên | Mô tả | Bắt buộc |
|-----|-------|----------|
| `IMGBB_API_KEY` | Fallback API key ImgBB nếu người dùng không nhập | Không |
| `QR_SECRET` | Secret key để ký HMAC cooldown token | Khuyến nghị |

`QR_SECRET` nên được đặt trong Vercel Dashboard → Settings → Environment Variables.

## API key ImgBB

Tab Ảnh yêu cầu API key ImgBB. Mỗi người dùng tự nhập key tại `https://api.imgbb.com/`. Key lưu trong localStorage trên thiết bị và gửi lên server mỗi khi upload — server dùng key đó gọi ImgBB, không lưu lại.

## Cơ chế chống spam

Cooldown được thực thi server-side bằng HMAC-SHA256 token. Sau mỗi lần tạo QR thành công, server trả về `cd_token` (gồm `kind:timestamp:hmac`), client lưu và gửi kèm lần sau. Server verify chữ ký + thời gian — xóa localStorage không có tác dụng vì token không hợp lệ sẽ bị từ chối.

## Mã nguồn

GitHub: https://github.com/Pixel0509/qrcode-public

## Lưu ý

- Ảnh tải lên lưu trên tài khoản ImgBB của người dùng
- Link ảnh là **công khai** — bất kỳ ai có link đều xem được
- Tuyệt đối không tải ảnh riêng tư, CCCD, tài liệu nhạy cảm

## License

Dự án cá nhân, không có license. Dùng tùy ý nhưng tự chịu trách nhiệm.
