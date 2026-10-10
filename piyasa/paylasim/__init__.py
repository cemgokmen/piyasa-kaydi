"""
Sosyal medyada otomatik paylaşım (X): sitenin topladığı bildirimlerden kayda değer olanlar,
haber dilinde kısa gönderiler olarak paylaşılır.

  secim.py   hangi bildirimler paylaşılır, önem sırası
  metin.py   gönderi metinleri (haber dili; yatırım tavsiyesi içermez)
  x.py       X API (OAuth 1.0a ile gönderi)
  calistir   kurallar: gece paylaşım yok, günlük sınır, gönderiler arası bekleme, tekrar yok

Çalıştırmak için:
    python -m piyasa paylas              deneme: paylaşılacakları listeler, hiçbir şey göndermez
    python -m piyasa paylas --gercek     sıradaki gönderiyi X'te paylaşır (kurallar uygunsa)
"""
