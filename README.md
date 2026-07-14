# Steam Market Monitor

Skrip ini memantau 3 item Steam Market setiap 30 menit dan mengirimkan harga terbaru ke Discord.

## Cara pakai

1. Siapkan webhook Discord.
2. Buat secret GitHub dengan nama `DISCORD_WEBHOOK_URL`.
3. Push file ini ke repository GitHub.
4. Workflow akan berjalan otomatis setiap 30 menit.

## Variabel lingkungan

- `DISCORD_WEBHOOK_URL`: webhook Discord untuk mengirim notifikasi.
- `IDR_EXCHANGE_RATE`: nilai tukar USD ke IDR opsional. Jika tidak diisi, skrip akan mengambil nilai dari API exchangerate.host.

## Jalankan lokal (opsional)

```bash
python app.py --once
```

Untuk menjalankan terus-menerus setiap 30 menit lokal:

```bash
python app.py
```
