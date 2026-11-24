"""
پێناسەی تایبەتمەندییەکانی مۆبایل (Feature schema).

ئەم فایلە تاکە شوێنە کە تایبەتمەندییەکان تێیدا پێناسە دەکرێن.
- مۆدێلی Machine Learning لێرەوە دەزانێت کام ستوونانە بەکاربهێنێت.
- Frontend فۆرمی پێشبینی لێرەوە دروست دەکات (لە ڕێگەی /api/features).
- Backend داتای هاتوو لێرەوە دەپشکنێت.

ئەگەر داتاکەت گۆڕا، تەنها ئەم فایلە دەستکاری بکە.
"""

TARGET = "price_usd"

# هەر تایبەتمەندییەک:
#   name   : ناوی ستوون لە CSV
#   kind   : numeric | binary | categorical
#   label  : ناو بە کوردی، عەرەبی و ئینگلیزی
#   group  : بەش لە فۆرمەکەدا
#   min/max/step/unit : بۆ ژمارەکان
#   options: بۆ لیستەکان (ئەگەر None بێت لە داتاکەوە وەردەگیرێت)
#   choices: بژاردە پێشنیارکراوەکان (بۆ دوگمەکانی RAM و بیرگە)
FEATURES = [
    {"name": "brand", "kind": "categorical", "group": "basic",
     "label": {"ku": "براند", "ar": "العلامة التجارية", "en": "Brand"}, "options": None},
    {"name": "release_year", "kind": "numeric", "group": "basic",
     "label": {"ku": "ساڵی دەرچوون", "ar": "سنة الإصدار", "en": "Release year"},
     "min": 2015, "max": 2030, "step": 1, "unit": ""},
    {"name": "ram_gb", "kind": "numeric", "group": "memory",
     "label": {"ku": "RAM", "ar": "الرام", "en": "RAM"},
     "min": 1, "max": 24, "step": 1, "unit": "GB", "choices": [3, 4, 6, 8, 12, 16]},
    {"name": "storage_gb", "kind": "numeric", "group": "memory",
     "label": {"ku": "بیرگە", "ar": "السعة", "en": "Storage"},
     "min": 16, "max": 2048, "step": 1, "unit": "GB", "choices": [64, 128, 256, 512, 1024]},
    {"name": "chipset_tier", "kind": "numeric", "group": "performance",
     "label": {"ku": "ئاستی پرۆسێسەر", "ar": "مستوى المعالج", "en": "Chipset tier"},
     "min": 1, "max": 5, "step": 1, "unit": "",
     "tiers": {
         "ku": ["سەرەتایی", "مامناوەندی نزم", "مامناوەندی", "مامناوەندی بەرز", "پێشەنگ"],
         "ar": ["اقتصادي", "متوسط منخفض", "متوسط", "متوسط مرتفع", "رائد"],
         "en": ["Entry", "Lower mid", "Mid", "Upper mid", "Flagship"]}},
    {"name": "main_camera_mp", "kind": "numeric", "group": "camera",
     "label": {"ku": "کامێرای سەرەکی", "ar": "الكاميرا الرئيسية", "en": "Main camera"},
     "min": 2, "max": 250, "step": 1, "unit": "MP"},
    {"name": "front_camera_mp", "kind": "numeric", "group": "camera",
     "label": {"ku": "کامێرای پێشەوە", "ar": "الكاميرا الأمامية", "en": "Front camera"},
     "min": 1, "max": 60, "step": 1, "unit": "MP"},
    {"name": "battery_mah", "kind": "numeric", "group": "battery",
     "label": {"ku": "پاتری", "ar": "البطارية", "en": "Battery"},
     "min": 1000, "max": 10000, "step": 50, "unit": "mAh"},
    {"name": "fast_charge_w", "kind": "numeric", "group": "battery",
     "label": {"ku": "شەحنی خێرا", "ar": "الشحن السريع", "en": "Fast charging"},
     "min": 5, "max": 240, "step": 1, "unit": "W"},
    {"name": "screen_inch", "kind": "numeric", "group": "display",
     "label": {"ku": "قەبارەی شاشە", "ar": "حجم الشاشة", "en": "Screen size"},
     "min": 4.0, "max": 10.5, "step": 0.1, "unit": "inch"},  # مۆبایلی سێ-پێچ (TriFold) تا 10.2
    {"name": "refresh_rate_hz", "kind": "numeric", "group": "display",
     "label": {"ku": "خێرایی شاشە", "ar": "معدل التحديث", "en": "Refresh rate"},
     "min": 60, "max": 165, "step": 1, "unit": "Hz", "choices": [60, 90, 120, 144]},
    {"name": "display_type", "kind": "categorical", "group": "display",
     "label": {"ku": "جۆری شاشە", "ar": "نوع الشاشة", "en": "Display type"}, "options": ["LCD", "OLED"]},
    {"name": "weight_g", "kind": "numeric", "group": "body",
     "label": {"ku": "کێش", "ar": "الوزن", "en": "Weight"},
     "min": 100, "max": 350, "step": 1, "unit": "g"},
    {"name": "os", "kind": "categorical", "group": "body",
     "label": {"ku": "سیستەم", "ar": "نظام التشغيل", "en": "OS"}, "options": ["Android", "iOS"]},
    {"name": "has_5g", "kind": "binary", "group": "connectivity",
     "label": {"ku": "5G", "ar": "5G", "en": "5G"}},
    {"name": "has_nfc", "kind": "binary", "group": "connectivity",
     "label": {"ku": "NFC", "ar": "NFC", "en": "NFC"}},
]

GROUPS = {
    "basic": {"ku": "زانیاریی گشتی", "ar": "معلومات عامة", "en": "Basics"},
    "memory": {"ku": "بیرگە", "ar": "الذاكرة", "en": "Memory"},
    "performance": {"ku": "کارایی", "ar": "الأداء", "en": "Performance"},
    "camera": {"ku": "کامێرا", "ar": "الكاميرا", "en": "Camera"},
    "battery": {"ku": "پاتری", "ar": "البطارية", "en": "Battery"},
    "display": {"ku": "شاشە", "ar": "الشاشة", "en": "Display"},
    "body": {"ku": "جەستە و سیستەم", "ar": "الهيكل والنظام", "en": "Body & OS"},
    "connectivity": {"ku": "پەیوەندی", "ar": "الاتصال", "en": "Connectivity"},
}

# ستوونەکانی تر کە لە CSV دا هەن بەڵام بۆ ڕاهێنان بەکارناهێنرێن
# (تەنها بۆ گەڕان و پیشاندان)
META_COLUMNS = ["model", "chipset"]


def names(kind=None):
    return [f["name"] for f in FEATURES if kind is None or f["kind"] == kind]


NUMERIC = names("numeric")
BINARY = names("binary")
CATEGORICAL = names("categorical")
ALL = names()


def by_name(name):
    for f in FEATURES:
        if f["name"] == name:
            return f
    raise KeyError(name)
