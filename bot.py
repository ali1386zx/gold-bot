#!/usr/bin/env python3
"""
╔═══════════════════════════════════════╗
║     ربات تلگرام «الان یا الان»       ║
║   نرخ لحظه‌ای طلا، سکه و ارز        ║
╚═══════════════════════════════════════╝
"""

import asyncio
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, ContextTypes,
)
import aiohttp

# ════════════════ تنظیمات ════════════════
BOT_TOKEN = "8258040402:AAEm2ILb64P4p_ScLl2uKF4dVzrPEzWwoCc"
WEBAPP_URL = "https://heydari-86.ir/app.html"
API_KEY = "Z0xpaVRSZqJxL1GO0Nf1X9TAWGJcD0QRMXGRi3uZgY"
GOLD_URL = "https://api.nerkh.io/v1/prices/json/gold"
CURR_URL = "https://api.nerkh.io/v1/prices/json/currency"
DEV_TELEGRAM = "https://t.me/heydari86io"
PROXY_URL = ""

logging.basicConfig(format="%(asctime)s [%(levelname)s] %(message)s", level=logging.INFO)
log = logging.getLogger(__name__)

# ════════════════ آیتم‌ها ════════════════
GOLD_ITEMS = [
    {"key": "GOLD18K", "label": "طلای ۱۸ عیار", "icon": "✦", "unit": "تومان"},
    {"key": "GOLD24K", "label": "طلای ۲۴ عیار", "icon": "◆", "unit": "تومان"},
    {"key": "OUNCE",   "label": "انس طلا",     "icon": "⚖", "unit": "دلار"},
    {"key": "MAZANEH", "label": "مثقال طلا",   "icon": "◎", "unit": "تومان"},
]
COIN_ITEMS = [
    {"key": "SEKE_EMAMI",  "label": "سکه امامی",    "icon": "●"},
    {"key": "SEKE_BAHAR",  "label": "بهار آزادی",  "icon": "◎"},
    {"key": "SEKE_NIM",    "label": "نیم سکه",      "icon": "◐"},
    {"key": "SEKE_ROB",    "label": "ربع سکه",      "icon": "◑"},
    {"key": "SEKE_1G",     "label": "سکه یک گرمی", "icon": "⚬"},
    {"key": "SEKE_PRS100", "label": "پارسیان ۱۰۰",  "icon": "◈"},
    {"key": "SEKE_PRS200", "label": "پارسیان ۲۰۰",  "icon": "◈"},
    {"key": "SEKE_PRS400", "label": "پارسیان ۴۰۰",  "icon": "◈"},
    {"key": "SEKE_PRS500", "label": "پارسیان ۵۰۰",  "icon": "◈"},
    {"key": "SEKE_PRS700", "label": "پارسیان ۷۰۰",  "icon": "◈"},
]
CURR_ITEMS = [
    {"key": "USD", "label": "دلار آمریکا", "icon": "$", "unit": "تومان"},
    {"key": "EUR", "label": "یورو",         "icon": "€", "unit": "تومان"},
    {"key": "GBP", "label": "پوند انگلیس", "icon": "£", "unit": "تومان"},
]

DB = {"gold": None, "curr": None, "date": ""}

# ════════════════ توابع کمکی ════════════════
FA = "۰۱۲۳۴۵۶۷۸۹"

def to_n(v) -> int:
    try:
        return int(str(v or "0").replace(",", "")) or 0
    except (ValueError, TypeError):
        return 0

def fmt(n) -> str:
    return "".join(FA[int(c)] if c.isdigit() else c for c in f"{to_n(n):,}")

def pct(cur, ref) -> tuple:
    c, r = to_n(cur), to_n(ref)
    if not c or not r:
        return "۰.۰۰", "nt"
    d = c - r
    return f"{abs(d / r * 100):.2f}", ("up" if d > 0 else "dn" if d < 0 else "nt")

def arrow(d: str) -> str:
    return "▲" if d == "up" else "▼" if d == "dn" else "─"

def badge(d: str, v: str) -> str:
    """نشان تغییرات رنگی"""
    if d == "up":
        return f"🟢 +{v}%"
    elif d == "dn":
        return f"🔴 -{v}%"
    return f"⚪ {v}%"

def norm(raw) -> dict | None:
    if not raw:
        return None
    mn = raw.get("min") or {}
    mx = raw.get("max") or {}
    return {
        "c":   to_n(raw.get("current")),
        "n1":  to_n(raw.get("min1", mn.get("1hour"))),
        "x1":  to_n(raw.get("max1", mx.get("1hour"))),
        "n12": to_n(raw.get("min12", mn.get("12hour"))),
        "x12": to_n(raw.get("max12", mx.get("12hour"))),
        "u":   raw.get("update", ""),
    }

def piv(d: dict) -> dict | None:
    if not d or not d["c"]:
        return None
    H, L, C = d["x12"] or d["x1"], d["n12"] or d["n1"], d["c"]
    P = (H + L + C) / 3
    return {"P": P, "R1": 2*P - L, "S1": 2*P - H, "R2": P + H - L, "S2": P - H + L}

def bar(d: dict) -> str:
    if not d or d["x1"] <= d["n1"]:
        return "▮" * 10 + f"  ٪۵۰"
    p = (d["c"] - d["n1"]) / (d["x1"] - d["n1"])
    f = round(p * 10)
    return "▮" * f + "▯" * (10 - f) + f"  ٪{round(p * 100)}"


# ════════════════ دریافت داده ════════════════
async def fetch_data():
    hdr = {"Authorization": f"Bearer {API_KEY}"}
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get(GOLD_URL, headers=hdr, timeout=aiohttp.ClientTimeout(total=10)) as r:
                if r.status == 200:
                    j = await r.json()
                    if j.get("data", {}).get("prices"):
                        DB["gold"] = j["data"]["prices"]
                        DB["date"] = j["data"].get("date", "")
            async with s.get(CURR_URL, headers=hdr, timeout=aiohttp.ClientTimeout(total=10)) as r:
                if r.status == 200:
                    j = await r.json()
                    if j.get("data", {}).get("prices"):
                        DB["curr"] = j["data"]["prices"]
        log.info("✅ بروزرسانی شد")
    except Exception as e:
        log.error(f"❌ خطا در دریافت: {e}")


# ════════════════ کیبوردها ════════════════
def home_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🏠 خانه", callback_data="n:home")],
    ])

def nav_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💎 طلا",       callback_data="n:gold"),
         InlineKeyboardButton("🪙 سکه",       callback_data="n:coins"),
         InlineKeyboardButton("💱 ارز",       callback_data="n:curr")],
        [InlineKeyboardButton("🧮 محاسبه‌گر", callback_data="n:calc"),
         InlineKeyboardButton("📊 بازار",     callback_data="n:market"),
         InlineKeyboardButton("⚙️ تنظیمات",   callback_data="n:set")],
        [InlineKeyboardButton("🏠 خانه",      callback_data="n:home")],
    ])


# ════════════════ صفحه خانه ════════════════
def pg_home() -> tuple:
    g, c = DB.get("gold"), DB.get("curr")
    if not g and not c:
        return ("⏳ در حال بارگذاری...\nلطفاً چند ثانیه صبر کنید.", nav_kb())

    t = "✦ *الان یا الان*\n"
    t += "━" * 22 + "\n\n"

    # ── طلای ۱۸ عیار (هیرو) ──
    d = norm(g.get("GOLD18K")) if g else None
    if d:
        v1, d1 = pct(d["c"], d["n1"])
        v12, d12 = pct(d["c"], d["n12"])
        t += f"✦  *طلای ۱۸ عیار*\n"
        t += f"   `{fmt(d['c'])}` تومان\n"
        t += f"   ۱ساعته {badge(d1, v1)}  ·  ۱۲ساعته {badge(d12, v12)}\n"
        t += "   " + bar(d) + "\n\n"

    # ── سایر طلاها ──
    t += "━ *طلا و فلزات* ━━━━━━━━\n"
    for it in GOLD_ITEMS[1:]:
        dd = norm(g.get(it["key"])) if g else None
        if dd:
            v, dr = pct(dd["c"], dd["n1"])
            t += f"  {it['icon']} {it['label']}  │  `{fmt(dd['c'])}` {it['unit']}  │  {badge(dr, v)}\n"

    # ── سکه‌ها ──
    t += "\n━ *سکه* ━━━━━━━━━━━━━━\n"
    for it in COIN_ITEMS[:5]:
        dd = norm(g.get(it["key"])) if g else None
        if dd:
            v, dr = pct(dd["c"], dd["n1"])
            t += f"  {it['icon']} {it['label']}  │  `{fmt(dd['c'])}`  │  {badge(dr, v)}\n"

    # ── ارز ──
    t += "\n━ *ارز* ━━━━━━━━━━━━━━\n"
    for it in CURR_ITEMS:
        dd = norm(c.get(it["key"])) if c else None
        if dd:
            v, dr = pct(dd["c"], dd["n1"])
            t += f"  {it['icon']} {it['label']}  │  `{fmt(dd['c'])}` {it['unit']}  │  {badge(dr, v)}\n"

    if DB.get("date"):
        t += f"\n ━━━━━━━━━━━━━━━━━━━━━\n"
        t += f" 📅 {DB['date']}"

    rows = [
        [InlineKeyboardButton("💎 طلا",       callback_data="n:gold"),
         InlineKeyboardButton("🪙 سکه",       callback_data="n:coins"),
         InlineKeyboardButton("💱 ارز",       callback_data="n:curr")],
        [InlineKeyboardButton("🧮 محاسبه‌گر", callback_data="n:calc"),
         InlineKeyboardButton("📊 بازار",     callback_data="n:market"),
         InlineKeyboardButton("⚙️ تنظیمات",   callback_data="n:set")],
    ]
    if WEBAPP_URL:
        rows.append([InlineKeyboardButton("🌐 نسخه وب اپلیکیشن", web_app=WebAppInfo(url=WEBAPP_URL))])
    rows.append([InlineKeyboardButton("🔄 بروزرسانی", callback_data="ref")])
    return t, InlineKeyboardMarkup(rows)


# ════════════════ صفحه طلا ════════════════
def pg_gold() -> tuple:
    g = DB.get("gold")
    if not g:
        return ("❌ اتصال برقرار نشد.", nav_kb())

    h = GOLD_ITEMS[0]
    d = norm(g.get(h["key"]))
    if not d:
        return ("❌ داده موجود نیست.", nav_kb())

    v1, d1 = pct(d["c"], d["n1"])
    v12, d12 = pct(d["c"], d["n12"])

    t = "💎 *طلای ۱۸ عیار*\n"
    t += "━" * 22 + "\n\n"
    t += f"  `{fmt(d['c'])}` *تومان*\n\n"
    t += f"  ۱ ساعته  {badge(d1, v1)}\n"
    t += f"  ۱۲ ساعته {badge(d12, v12)}\n\n"

    t += "  *موقعیت قیمت ۱ ساعته*\n"
    t += "  " + bar(d) + "\n"
    t += f"  کف `{fmt(d['n1'])}`  ─  سقف `{fmt(d['x1'])}`\n\n"

    lv = piv(d)
    if lv:
        t += "  *سطوح کلیدی*\n"
        t += f"  🔴 مقاومت ۲  `{fmt(lv['R2'])}`\n"
        t += f"  🟠 مقاومت ۱  `{fmt(lv['R1'])}`\n"
        t += f"  🟡 پیووت      `{fmt(lv['P'])}`\n"
        t += f"  🟢 حمایت ۱    `{fmt(lv['S1'])}`\n"
        t += f"  🟢 حمایت ۲    `{fmt(lv['S2'])}`\n\n"

    t += "━ *سایر اقلام طلایی* ━━━\n"
    for it in GOLD_ITEMS[1:]:
        dd = norm(g.get(it["key"]))
        if dd:
            v, dr = pct(dd["c"], dd["n1"])
            t += f"  {it['icon']} {it['label']}\n"
            t += f"     `{fmt(dd['c'])}` {it['unit']}  {badge(dr, v)}\n"

    rows = [
        [InlineKeyboardButton("🔍 جزئیات بیشتر", callback_data=f"d:GOLD18K:g:gold")],
        [InlineKeyboardButton("🪙 سکه", callback_data="n:coins"),
         InlineKeyboardButton("💱 ارز", callback_data="n:curr")],
        [InlineKeyboardButton("🏠 خانه", callback_data="n:home"),
         InlineKeyboardButton("🔄 بروزرسانی", callback_data="ref")],
    ]
    return t, InlineKeyboardMarkup(rows)


# ════════════════ صفحه سکه ════════════════
def pg_coins() -> tuple:
    g = DB.get("gold")
    if not g:
        return ("❌ اتصال برقرار نشد.", nav_kb())

    t = "🪙 *نرخ سکه*\n"
    t += "━" * 22 + "\n\n"

    for it in COIN_ITEMS:
        d = norm(g.get(it["key"]))
        if d:
            v, dr = pct(d["c"], d["n1"])
            t += f"  {it['icon']} *{it['label']}*\n"
            t += f"     `{fmt(d['c'])}` تومان  {badge(dr, v)}\n\n"

    rows = []
    row = []
    for it in COIN_ITEMS:
        row.append(InlineKeyboardButton(it["icon"], callback_data=f"d:{it['key']}:g:coins"))
        if len(row) == 5:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([InlineKeyboardButton("💎 طلا", callback_data="n:gold"),
                 InlineKeyboardButton("💱 ارز", callback_data="n:curr")])
    rows.append([InlineKeyboardButton("🏠 خانه", callback_data="n:home"),
                 InlineKeyboardButton("🔄 بروزرسانی", callback_data="ref")])
    return t, InlineKeyboardMarkup(rows)


# ════════════════ صفحه ارز ════════════════
def pg_currency() -> tuple:
    c = DB.get("curr")
    if not c:
        return ("❌ داده‌ای دریافت نشد.", nav_kb())

    t = "💱 *نرخ ارز*\n"
    t += "━" * 22 + "\n\n"

    for it in CURR_ITEMS:
        d = norm(c.get(it["key"]))
        if d:
            v1, d1 = pct(d["c"], d["n1"])
            v12, d12 = pct(d["c"], d["n12"])
            t += f"  {it['icon']} *{it['label']}*\n"
            t += f"     `{fmt(d['c'])}` {it['unit']}\n"
            t += f"     ۱ساعته {badge(d1, v1)}  ·  ۱۲ساعته {badge(d12, v12)}\n\n"

    rows = [[InlineKeyboardButton(f"🔍 {it['label']}", callback_data=f"d:{it['key']}:c:curr") for it in CURR_ITEMS]]
    rows.append([InlineKeyboardButton("💎 طلا", callback_data="n:gold"),
                 InlineKeyboardButton("🪙 سکه", callback_data="n:coins")])
    rows.append([InlineKeyboardButton("🏠 خانه", callback_data="n:home"),
                 InlineKeyboardButton("🔄 بروزرسانی", callback_data="ref")])
    return t, InlineKeyboardMarkup(rows)


# ════════════════ صفحه بازار ════════════════
def pg_market() -> tuple:
    items = []
    g, c = DB.get("gold"), DB.get("curr")
    for it in GOLD_ITEMS:
        if g:
            d = norm(g.get(it["key"]))
            if d:
                items.append({**it, "d": d, "src": "g"})
    for it in COIN_ITEMS:
        if g:
            d = norm(g.get(it["key"]))
            if d:
                items.append({"key": it["key"], "label": it["label"], "icon": it["icon"], "unit": "تومان", "d": d, "src": "g"})
    for it in CURR_ITEMS:
        if c:
            d = norm(c.get(it["key"]))
            if d:
                items.append({**it, "d": d, "src": "c"})

    items.sort(key=lambda x: float(pct(x["d"]["c"], x["d"]["n1"])[0]), reverse=True)

    t = "📊 *بازار*\n"
    t += "━" * 22 + "\n"
    t += "  مرتب بر اساس تغییرات ۱ ساعته\n\n"

    for i, it in enumerate(items, 1):
        v, dr = pct(it["d"]["c"], it["d"]["n1"])
        t += f"  *{i}.* {it['icon']} {it['label']}\n"
        t += f"      `{fmt(it['d']['c'])}`  {badge(dr, v)}\n\n"

    rows = [[InlineKeyboardButton(f"{i}. {it['label']}", callback_data=f"d:{it['key']}:{it['src']}:market")
             for i, it in enumerate(items[:12], 1)]]
    rows.append([InlineKeyboardButton("🏠 خانه", callback_data="n:home"),
                 InlineKeyboardButton("🔄 بروزرسانی", callback_data="ref")])
    return t, InlineKeyboardMarkup(rows)


# ════════════════ محاسبه‌گر ════════════════
def pg_calc(ctx: ContextTypes.DEFAULT_TYPE) -> tuple:
    g = DB.get("gold")
    if not g:
        return ("❌ اتصال برقرار نشد.", nav_kb())
    d = norm(g.get("GOLD18K"))
    if not d:
        return ("❌ داده موجود نیست.", nav_kb())

    ca = ctx.user_data.get("calc", {"w": 1.0, "e": 5.0, "s": 7.0, "vat": True})
    w, e, s, vat = ca["w"], ca["e"], ca["s"], ca["vat"]
    p = d["c"]

    raw = w * p
    ejr = raw * e / 100
    base = raw + ejr
    sud = base * s / 100
    sub = base + sud
    tax = sub * 0.09 if vat else 0
    total = sub + tax
    sell = w * p

    t = "🧮 *محاسبه‌گر طلا*\n"
    t += "━" * 22 + "\n\n"
    t += f"  قیمت هر گرم ۱۸ عیار\n  `{fmt(p)}` تومان\n\n"
    t += "  *مشخصات*\n"
    t += f"  ⚖️ وزن      {w} گرم\n"
    t += f"  🔧 اجرت     {e}٪\n"
    t += f"  🏪 سود       {s}٪\n"
    t += f"  🧾 مالیات ۹٪  {'✅' if vat else '❌'}\n\n"
    t += "  *صورتحساب*\n"
    t += f"  قیمت خام   `{fmt(raw)}`\n"
    t += f"  اجرت ساخت  `{fmt(ejr)}`\n"
    t += f"  سود مغازه  `{fmt(sud)}`\n"
    t += f"  مالیات      `{fmt(tax)}`\n"
    t += "  ─────────────────\n"
    t += f"  💰 *قیمت خرید*  `{fmt(total)}`\n"
    t += f"  🟢 *قیمت فروش*  `{fmt(sell)}`\n"

    rows = [
        [InlineKeyboardButton("−", callback_data="c:w:-"),
         InlineKeyboardButton(f"⚖️ {w}g", callback_data="c:w:0"),
         InlineKeyboardButton("+", callback_data="c:w:+")],
        [InlineKeyboardButton("−", callback_data="c:e:-"),
         InlineKeyboardButton(f"🔧 اجرت {e}%", callback_data="c:e:0"),
         InlineKeyboardButton("+", callback_data="c:e:+")],
        [InlineKeyboardButton("−", callback_data="c:s:-"),
         InlineKeyboardButton(f"🏪 سود {s}%", callback_data="c:s:0"),
         InlineKeyboardButton("+", callback_data="c:s:+")],
        [InlineKeyboardButton(f"🧾 مالیات ۹٪  {'✅' if vat else '❌'}", callback_data="c:vat")],
        [InlineKeyboardButton("🏠 خانه", callback_data="n:home"),
         InlineKeyboardButton("🔄 بروزرسانی", callback_data="ref")],
    ]
    return t, InlineKeyboardMarkup(rows)


# ════════════════ جزئیات ════════════════
def pg_detail(key: str, src: str, back: str) -> tuple:
    data = DB.get("gold" if src == "g" else "curr")
    if not data:
        return ("❌ داده‌ای موجود نیست.", home_kb())

    all_items = (GOLD_ITEMS
                 + [{"key": i["key"], "label": i["label"], "icon": i["icon"], "unit": "تومان"} for i in COIN_ITEMS]
                 + CURR_ITEMS)
    item = next((i for i in all_items if i["key"] == key), None)
    if not item:
        item = {"key": key, "label": key, "icon": "📊", "unit": "تومان"}

    d = norm(data.get(key))
    if not d:
        return (f"❌ داده‌ای برای {item['label']} یافت نشد.", home_kb())

    v1, d1 = pct(d["c"], d["n1"])
    v12, d12 = pct(d["c"], d["n12"])

    t = f"{item['icon']}  *{item['label']}*\n"
    t += "━" * 22 + "\n\n"
    t += f"  `{fmt(d['c'])}` {item.get('unit', 'تومان')}\n\n"
    t += "  *تغییرات*\n"
    t += f"  ۱ ساعته   {badge(d1, v1)}\n"
    t += f"  ۱۲ ساعته  {badge(d12, v12)}\n\n"
    t += "  *محدوده ۱ ساعته*\n"
    t += f"  بالاترین  `{fmt(d['x1'])}`\n"
    t += f"  پایین‌ترین `{fmt(d['n1'])}`\n"
    t += "  " + bar(d) + "\n\n"
    t += "  *محدوده ۱۲ ساعته*\n"
    t += f"  بالاترین  `{fmt(d['x12'])}`\n"
    t += f"  پایین‌ترین `{fmt(d['n12'])}`\n\n"

    lv = piv(d)
    if lv:
        t += "  *سطوح پیووت*\n"
        t += f"  🔴 مقاومت ۲  `{fmt(lv['R2'])}`\n"
        t += f"  🟠 مقاومت ۱  `{fmt(lv['R1'])}`\n"
        t += f"  🟡 پیووت      `{fmt(lv['P'])}`\n"
        t += f"  🟢 حمایت ۱    `{fmt(lv['S1'])}`\n"
        t += f"  🟢 حمایت ۲    `{fmt(lv['S2'])}`\n\n"

    if d["u"]:
        t += f"  🕐 {d['u']}"

    return t, InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 بازگشت", callback_data=f"b:{back}")],
        [InlineKeyboardButton("🏠 خانه", callback_data="n:home")],
    ])


# ════════════════ تنظیمات ════════════════
def pg_settings() -> tuple:
    t = "⚙️  *تنظیمات*\n"
    t += "━" * 22 + "\n\n"
    t += "  🤖 *الان یا الان*\n"
    t += "  نسخه ۱.۰.۰\n\n"
    t += "  📡 منبع  `nerkh.io`\n"
    t += "  🔄 بروزرسانی  هر ۶۰ ثانیه\n\n"
    t += "  👨‍💻 *توسعه‌دهنده*\n"
    t += "  علی حیدری\n"
    t += "  برنامه‌نویس فرانت‌اند\n"

    rows = [
        [InlineKeyboardButton("🔄 بروزرسانی دستی", callback_data="ref")],
    ]
    if WEBAPP_URL:
        rows.append([InlineKeyboardButton("🌐 نسخه وب", web_app=WebAppInfo(url=WEBAPP_URL))])
    rows.append([InlineKeyboardButton("💬 تلگرام", url=DEV_TELEGRAM)])
    rows.append([InlineKeyboardButton("🏠 خانه", callback_data="n:home")])
    return t, InlineKeyboardMarkup(rows)


# ════════════════ نگاشت ════════════════
PAGES = {
    "home": pg_home, "gold": pg_gold, "coins": pg_coins,
    "curr": pg_currency, "market": pg_market, "set": pg_settings,
}

def render(page: str, ctx: ContextTypes.DEFAULT_TYPE = None) -> tuple:
    if page == "calc" and ctx:
        return pg_calc(ctx)
    return PAGES.get(page, pg_home)()


# ════════════════ هندلر کال‌بک ════════════════
async def on_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    cd = q.data

    try:
        if cd.startswith("n:") or cd.startswith("b:"):
            page = cd.split(":")[1]
            ctx.user_data["page"] = page
            text, kb = render(page, ctx)
            await q.edit_message_text(text, reply_markup=kb, parse_mode="Markdown")

        elif cd.startswith("d:"):
            parts = cd.split(":")
            text, kb = pg_detail(parts[1], parts[2], parts[3])
            await q.edit_message_text(text, reply_markup=kb, parse_mode="Markdown")

        elif cd == "ref":
            await q.edit_message_text("⏳ بروزرسانی...")
            await fetch_data()
            page = ctx.user_data.get("page", "home")
            text, kb = render(page, ctx)
            await q.edit_message_text(text, reply_markup=kb, parse_mode="Markdown")

        elif cd.startswith("c:"):
            ca = ctx.user_data.get("calc", {"w": 1.0, "e": 5.0, "s": 7.0, "vat": True})
            parts = cd.split(":")
            if parts[1] == "vat":
                ca["vat"] = not ca["vat"]
            elif len(parts) == 3 and parts[2] in ("+", "-"):
                field, delta = parts[1], 1 if parts[2] == "+" else -1
                if field == "w":
                    step = 0.1 if ca["w"] < 1 else 0.5
                    ca["w"] = round(max(0.1, ca["w"] + step * delta), 1)
                elif field == "e":
                    ca["e"] = round(max(0, min(25, ca["e"] + 0.5 * delta)), 1)
                elif field == "s":
                    ca["s"] = round(max(0, min(25, ca["s"] + 0.5 * delta)), 1)
            ctx.user_data["calc"] = ca
            ctx.user_data["page"] = "calc"
            text, kb = pg_calc(ctx)
            await q.edit_message_text(text, reply_markup=kb, parse_mode="Markdown")

    except Exception as e:
        log.error(f"خطا در کال‌بک '{cd}': {e}")
        try:
            await q.edit_message_text("❌ خطا. دوباره تلاش کنید.", reply_markup=home_kb())
        except Exception:
            pass


# ════════════════ دستورات ════════════════
async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    t = "✦ *الان یا الان*\n"
    t += "━" * 22 + "\n"
    t += "  نرخ لحظه‌ای طلا، سکه و ارز\n"
    t += "  داده‌ها از *nerkh.io*\n\n"
    t += "  از منوی زیر استفاده کنید:"

    rows = []
    if WEBAPP_URL:
        rows.append([InlineKeyboardButton("🌐 باز کردن وب اپلیکیشن", web_app=WebAppInfo(url=WEBAPP_URL))])
    rows += [
        [InlineKeyboardButton("💎 طلا",       callback_data="n:gold"),
         InlineKeyboardButton("🪙 سکه",       callback_data="n:coins"),
         InlineKeyboardButton("💱 ارز",       callback_data="n:curr")],
        [InlineKeyboardButton("🧮 محاسبه‌گر", callback_data="n:calc"),
         InlineKeyboardButton("📊 بازار",     callback_data="n:market"),
         InlineKeyboardButton("⚙️ تنظیمات",   callback_data="n:set")],
    ]
    await update.message.reply_text(t, reply_markup=InlineKeyboardMarkup(rows), parse_mode="Markdown")


async def cmd_price(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data["page"] = "home"
    text, kb = pg_home()
    await update.message.reply_text(text, reply_markup=kb, parse_mode="Markdown")


async def cmd_help(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    t = """✦ *راهنمای ربات*

/start  ·  شروع
/price  ·  قیمت‌ها
/help   ·  راهنما

*صفحات:*
💎 طلا  ·  قیمت + سطوح پیووت
🪙 سکه  ·  تمام انواع سکه
💱 ارز  ·  دلار، یورو، پوند
🧮 محاسبه‌گر  ·  محاسبه با اجرت و سود
📊 بازار  ·  مرتب بر اساس تغییرات"""
    await update.message.reply_text(t, parse_mode="Markdown")


# ════════════════ خطا ════════════════
async def error_handler(update: object, ctx: ContextTypes.DEFAULT_TYPE):
    err = ctx.error
    name = type(err).__name__
    if "NetworkError" in name or "RemoteProtocolError" in name:
        log.warning(f"⚠️ قطعی موقت شبکه: {err}")
        return
    log.error(f"❌ {name}: {err}")


# ════════════════ بروزرسانی خودکار ════════════════
async def auto_refresh():
    while True:
        await asyncio.sleep(60)
        try:
            await fetch_data()
        except Exception as e:
            log.error(f"❌ خطا در بروزرسانی: {e}")


# ════════════════ اجرا ════════════════
def main():
    builder = Application.builder().token(BOT_TOKEN)
    if PROXY_URL:
        log.info(f"🌐 پروکسی: {PROXY_URL}")
        builder = builder.proxy(PROXY_URL).get_updates_proxy(PROXY_URL)

    app = builder.build()
    app.add_error_handler(error_handler)
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("price", cmd_price))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CallbackQueryHandler(on_callback))

    async def post_init(app):
        await fetch_data()
        log.info("🚀 ربات راه‌اندازی شد")
        asyncio.create_task(auto_refresh())

    app.post_init = post_init
    log.info("🔄 polling شروع...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()