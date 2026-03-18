import telebot
import json
import os
import re
import requests
from datetime import datetime, timedelta, timezone
from telebot.types import ChatPermissions
from dotenv import load_dotenv

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
bot = telebot.TeleBot(BOT_TOKEN, parse_mode="Markdown")

DATA_FILE = "data.json"

def get_beijing_time():
    utc_now = datetime.utcnow()
    beijing_tz = timezone(timedelta(hours=8))
    beijing_now = utc_now.astimezone(beijing_tz)
    return beijing_now.strftime("%m-%d %H:%M:%S"), beijing_now.strftime("%H")

def get_okx_best_price():
    try:
        url = "https://www.okx.com/api/v5/trade/order-book?instId=USDT-C2C"
        res = requests.get(url, timeout=5).json()
        if res.get("code") == "0" and res.get("data"):
            for bid in res["data"]:
                if bid["side"] == "buy":
                    return float(bid["px"])
    except:
        pass
    return 6.93

def init_data():
    if not os.exists(DATA_FILE):
        data = {
            "groups": {}, "operators": {}, "records": {},
            "rate": {"default": 6.93}, "fee": {"default": 0},
            "timer": {}, "day_cut": {}, "all_permission": {},
            "last_day_cut": {}
        }
        save_data(data)
    return load_data()

def load_data():
    if not os.path.exists(DATA_FILE):
        return {}
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

data = init_data()

def check_day_cut(chat_id):
    chat_id = str(chat_id)
    day_cut_hour = data.get("day_cut", {}).get(chat_id, "-1")
    if day_cut_hour == "-1":
        return
    now_time, now_hour = get_beijing_time()
    last = data.get("last_day_cut", {}).get(chat_id, "")
    if last != now_hour and now_hour == day_cut_hour:
        data["records"][chat_id] = []
        if "last_day_cut" not in data:
            data["last_day_cut"] = {}
        data["last_day_cut"][chat_id] = now_hour
        save_data(data)

def show_final_format(chat_id):
    chat_id = str(chat_id)
    check_day_cut(chat_id)
    records = data["records"].get(chat_id, [])
    rate = data["rate"]["default"]
    fee = data["fee"]["default"] / 100

    in_list = []
    out_list = []
    total_in_cny = 0.0
    total_out_cny = 0.0

    for r in records:
        time_str = r.get("time", "00:00:00")
        real_time = time_str.split()[1] if " " in time_str else time_str

        if r["type"] == "入款":
            money = r["money"]
            total_in_cny += money
            usdt = round(money / rate, 2) if rate != 0 else 0
            in_list.append(f"{real_time}  {money}/{rate}={usdt}  {r['user']}")

        if r["type"] == "下发":
            money = r["money"]
            cny = round(money * rate, 2)
            total_out_cny += cny
            out_list.append(f"{real_time}  {money}U（{cny}R）  {r['user']}")

    in_show = "\n".join(in_list[-3:]) if in_list else "暂无记录"
    out_show = "\n".join(out_list[-3:]) if out_list else "暂无记录"

    should_cny = total_in_cny * (1 - fee)
    should_usdt = round(should_cny / rate, 2) if rate != 0 else 0
    already_cny = total_out_cny
    already_usdt = round(already_cny / rate, 2) if rate != 0 else 0
    remain_cny = round(should_cny - already_cny, 2)
    remain_usdt = round(remain_cny / rate, 2) if rate != 0 else 0

    return f"""✅今日入款（最近3笔）：
{in_show}

✅今日下发（最近3笔）：
{out_show}

📌设置汇率：{rate}

📊 总账单
应下发：{should_cny}CNY / {should_usdt}USDT
已下发：{already_cny}CNY / {already_usdt}USDT
未下发：{remain_cny}CNY / {remain_usdt}USDT"""

def check_permission(chat_id, user_id, username):
    chat_id = str(chat_id)
    if data.get("all_permission", {}).get(chat_id):
        return True
    return username in data.get("operators", {}).get(chat_id, [])

def get_username(msg):
    return f"@{msg.from_user.username}" if msg.from_user.username else str(msg.from_user.id)

@bot.message_handler(func=lambda m: "开始记账" in m.text)
def start_book(msg):
    cid = str(msg.chat.id)
    if msg.chat.type not in ["group", "supergroup"]:
        return bot.reply_to(msg, "❌ 请在群聊使用")
    if cid not in data["groups"]:
        data["groups"][cid] = {"name": msg.chat.title}
        data["operators"][cid] = []
        data["records"][cid] = []
        data["day_cut"][cid] = "-1"
        save_data(data)
    bot.reply_to(msg, "✅ 记账已永久开启")

@bot.message_handler(func=lambda m: m.text.startswith("设置操作人"))
def add_op(msg):
    cid = str(msg.chat.id)
    match = re.search(r'@\w+', msg.text)
    if not match:
        return bot.reply_to(msg, "格式：设置操作人 @xxx")
    u = match.group(0)
    if cid not in data["operators"]:
        data["operators"][cid] = []
    if u not in data["operators"][cid]:
        data["operators"][cid].append(u)
        save_data(data)
    bot.reply_to(msg, f"✅ 已添加 {u}")

@bot.message_handler(func=lambda m: m.text == "设置实时汇率")
def set_realtime_rate(msg):
    price = get_okx_best_price()
    data["rate"]["default"] = price
    save_data(data)
    bot.reply_to(msg, f"✅ 已自动同步欧意实时价格：{price}")

@bot.message_handler(func=lambda m: m.text.startswith("设置费率"))
def set_fee(msg):
    match = re.search(r'([-\d\.]+)', msg.text)
    if match:
        data["fee"]["default"] = float(match.group(1))
        save_data(data)
        bot.reply_to(msg, f"✅ 费率已设为：{match.group(1)}%")

@bot.message_handler(func=lambda m: m.text.startswith("日切#"))
def set_day_cut(msg):
    cid = str(msg.chat.id)
    h = msg.text.split("#")[-1]
    data["day_cut"][cid] = h
    save_data(data)
    bot.reply_to(msg, f"✅ 日切时间已设为：{h}点")

@bot.message_handler(func=lambda m: m.text == "z0")
def z0(msg):
    p = get_okx_best_price()
    bot.reply_to(msg, f"💱 欧意实时收U价格：{p}")

@bot.message_handler(func=lambda m: m.text)
def all_msgs(msg):
    cid = str(msg.chat.id)
    text = msg.text.strip()
    user = get_username(msg)
    if not check_permission(cid, msg.from_user.id, user):
        return

    t, _ = get_beijing_time()

    if any(c in text for c in "+-*/") and not any(k in text for k in ["设置","下发","入款","@","#"]):
        try:
            r = eval(text.replace("×","*").replace("÷","/"))
            bot.reply_to(msg, f"🧮 结果：{r}")
        except:
            pass
        return

    if text.startswith("+"):
        n = re.findall(r'\+([\d\.]+)', text)
        if n:
            data["records"][cid].append({"type":"入款","money":float(n[0]),"user":user,"time":t})
            save_data(data)
            bot.reply_to(msg, show_final_format(cid))
        return

    if text.startswith("下发"):
        n = re.findall(r'([\d\.]+)', text)
        if n:
            data["records"][cid].append({"type":"下发","money":float(n[0]),"user":user,"time":t})
            save_data(data)
            bot.reply_to(msg, show_final_format(cid))
        return

    if "入款-" in text:
        n = re.findall(r'入款-([\d\.]+)', text)
        if n:
            data["records"][cid].append({"type":"入款","money":-float(n[0]),"user":user,"time":t})
            save_data(data)
            bot.reply_to(msg, show_final_format(cid))
        return

    if "下发-" in text:
        n = re.findall(r'下发-([\d\.]+)', text)
        if n:
            data["records"][cid].append({"type":"下发","money":-float(n[0]),"user":user,"time":t})
            save_data(data)
            bot.reply_to(msg, show_final_format(cid))
        return

if __name__ == "__main__":
    print("✅ 机器人本地启动成功（北京时间）")
    bot.infinity_polling()
