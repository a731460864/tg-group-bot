import telebot
import json
import os
import re
from datetime import datetime
from telebot.types import ChatPermissions

BOT_TOKEN = os.getenv("BOT_TOKEN")
bot = telebot.TeleBot(BOT_TOKEN, parse_mode="Markdown")

DATA_FILE = "data.json"

def init_data():
    if not os.path.exists(DATA_FILE):
        data = {
            "groups": {},
            "operators": {},
            "records": {},
            "rate": {"default": 7.0},
            "fee": {"default": 0},
            "timer": {},
            "day_cut": {},
            "all_permission": {}
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

def check_permission(chat_id, user_id, username):
    chat_id = str(chat_id)
    user_id = str(user_id)
    if data.get("all_permission", {}).get(chat_id, False):
        return True
    if chat_id not in data.get("operators", {}):
        return False
    return user_id in data["operators"][chat_id] or username in data["operators"][chat_id]

def get_username(msg):
    if msg.from_user.username:
        return "@" + msg.from_user.username
    return str(msg.from_user.id)

@bot.message_handler(func=lambda m: m.text and "开始记账" in m.text)
def start_book(msg):
    chat_id = str(msg.chat.id)
    if msg.chat.type not in ["group", "supergroup"]:
        bot.reply_to(msg, "❌ 请在群聊中使用！")
        return
    if chat_id not in data["groups"]:
        data["groups"][chat_id] = {"name": msg.chat.title}
        data["operators"][chat_id] = []
        data["records"][chat_id] = []
        data["day_cut"][chat_id] = "0"
        save_data(data)
    bot.reply_to(msg, "✅ 群记账已开启！请设置管理员后使用")

@bot.message_handler(func=lambda m: m.text and m.text.startswith("设置操作人"))
def add_operator(msg):
    chat_id = str(msg.chat.id)
    text = msg.text.strip()
    match = re.search(r'@\w+', text)
    if not match:
        bot.reply_to(msg, "❌ 格式：设置操作人 @张三")
        return
    target = match.group(0)
    if chat_id not in data["operators"]:
        data["operators"][chat_id] = []
    if target not in data["operators"][chat_id]:
        data["operators"][chat_id].append(target)
        save_data(data)
        bot.reply_to(msg, f"✅ 已添加操作人：{target}")

@bot.message_handler(func=lambda m: m.text and m.text.startswith("删除操作人"))
def del_operator(msg):
    chat_id = str(msg.chat.id)
    text = msg.text.strip()
    match = re.search(r'@\w+', text)
    if not match:
        bot.reply_to(msg, "❌ 格式：删除操作人 @张三")
        return
    target = match.group(0)
    if chat_id in data["operators"] and target in data["operators"][chat_id]:
        data["operators"][chat_id].remove(target)
        save_data(data)
        bot.reply_to(msg, f"✅ 已删除操作人：{target}")

@bot.message_handler(func=lambda m: m.text and m.text == "显示操作人")
def show_operators(msg):
    chat_id = str(msg.chat.id)
    ops = data["operators"].get(chat_id, [])
    if not ops:
        bot.reply_to(msg, "❌ 暂无操作人")
        return
    bot.reply_to(msg, "👥 当前操作人：\n" + "\n".join(ops))

@bot.message_handler(func=lambda m: m.text and m.text == "删除所有人")
def del_all_ops(msg):
    chat_id = str(msg.chat.id)
    data["operators"][chat_id] = []
    save_data(data)
    bot.reply_to(msg, "✅ 已清空所有操作人")

@bot.message_handler(func=lambda m: m.text and m.text == "设置所有人")
def set_all_permission(msg):
    chat_id = str(msg.chat.id)
    data["all_permission"][chat_id] = True
    save_data(data)
    bot.reply_to(msg, "✅ 群内所有人均可使用记账")

@bot.message_handler(func=lambda m: m.text == "删除账单")
def clear_bill(msg):
    chat_id = str(msg.chat.id)
    data["records"][chat_id] = []
    save_data(data)
    bot.reply_to(msg, "✅ 账单已清空")

@bot.message_handler(func=lambda m: m.text)
def handle_money(msg):
    chat_id = str(msg.chat.id)
    text = msg.text.strip()
    username = get_username(msg)
    if not check_permission(chat_id, msg.from_user.id, username):
        return

    if text.startswith("+"):
        num_str = re.findall(r'\+([\d\.]+)', text)
        if not num_str:
            return
        money = float(num_str[0])
        coin = "USDT" if "u" in text.lower() else "CNY"
        data["records"][chat_id].append({
            "type": "入款", "money": money, "coin": coin,
            "user": username, "time": datetime.now().strftime("%m-%d %H:%M")
        })
        save_data(data)
        bot.reply_to(msg, f"✅ 入款成功：{money}{coin}")
        return

    if text.startswith("下发"):
        num_str = re.findall(r'([\d\.]+)', text)
        if not num_str:
            return
        money = float(num_str[0])
        coin = "USDT" if "u" in text.lower() else "CNY"
        data["records"][chat_id].append({
            "type": "下发", "money": money, "coin": coin,
            "user": username, "time": datetime.now().strftime("%m-%d %H:%M")
        })
        save_data(data)
        bot.reply_to(msg, f"✅ 下发成功：{money}{coin}")
        return

    if "入款-" in text:
        num_str = re.findall(r'入款-([\d\.]+)', text)
        if num_str:
            money = float(num_str[0])
            data["records"][chat_id].append({
                "type": "修正入款", "money": -money, "coin": "CNY",
                "user": username, "time": datetime.now().strftime("%m-%d %H:%M")
            })
            save_data(data)
            bot.reply_to(msg, f"✅ 入款减少：{money}")
        return

    if "下发-" in text:
        num_str = re.findall(r'下发-([\d\.]+)', text)
        if num_str:
            money = float(num_str[0])
            data["records"][chat_id].append({
                "type": "修正下发", "money": -money, "coin": "CNY",
                "user": username, "time": datetime.now().strftime("%m-%d %H:%M")
            })
            save_data(data)
            bot.reply_to(msg, f"✅ 下发减少：{money}")
        return

@bot.message_handler(func=lambda m: m.text == "显示账单")
def show_bill(msg):
    chat_id = str(msg.chat.id)
    records = data["records"].get(chat_id, [])
    in_cny = in_usdt = out_cny = out_usdt = 0
    for r in records:
        if r["type"] == "入款":
            if r["coin"] == "CNY":
                in_cny += r["money"]
            else:
                in_usdt += r["money"]
        if r["type"] == "下发":
            if r["coin"] == "CNY":
                out_cny += r["money"]
            else:
                out_usdt += r["money"]
    res = f"📊 总账单\n入款：{in_cny}CNY / {in_usdt}USDT\n下发：{out_cny}CNY / {out_usdt}USDT"
    bot.reply_to(msg, res)

@bot.message_handler(func=lambda m: m.text == "z0")
def show_rate(msg):
    r = data["rate"]["default"]
    bot.reply_to(msg, f"💱 当前汇率 1USDT = {r} CNY")

@bot.message_handler(func=lambda m: m.text.startswith("z"))
def z_convert(msg):
    num_str = re.findall(r'z([\d\.]+)', msg.text)
    if not num_str:
        return
    cny = float(num_str[0])
    rate = data["rate"]["default"]
    usdt = round(cny / rate, 2)
    bot.reply_to(msg, f"💱 {cny}CNY = {usdt}USDT")

@bot.message_handler(func=lambda m: m.text.startswith("设置汇率"))
def set_rate(msg):
    num_str = re.findall(r'([\d\.]+)', msg.text)
    if num_str:
        data["rate"]["default"] = float(num_str[0])
        save_data(data)
        bot.reply_to(msg, f"✅ 汇率已设为：{num_str[0]}")

@bot.message_handler(func=lambda m: m.text.startswith("设置费率"))
def set_fee(msg):
    num_str = re.findall(r'([-\d\.]+)', msg.text)
    if num_str:
        data["fee"]["default"] = float(num_str[0])
        save_data(data)
        bot.reply_to(msg, f"✅ 费率已设为：{num_str[0]}%")

@bot.message_handler(func=lambda m: m.text == "撤销入款")
def undo_in(msg):
    chat_id = str(msg.chat.id)
    recs = [r for r in data["records"][chat_id] if r["type"] == "入款"]
    if recs:
        data["records"][chat_id].remove(recs[-1])
        save_data(data)
        bot.reply_to(msg, "✅ 已撤销最近一笔入款")

@bot.message_handler(func=lambda m: m.text == "撤销下发")
def undo_out(msg):
    chat_id = str(msg.chat.id)
    recs = [r for r in data["records"][chat_id] if r["type"] == "下发"]
    if recs:
        data["records"][chat_id].remove(recs[-1])
        save_data(data)
        bot.reply_to(msg, "✅ 已撤销最近一笔下发")

@bot.message_handler(func=lambda m: "开始计时打卡" in m.text)
def start_timer(msg):
    chat_id = str(msg.chat.id)
    data["timer"][chat_id] = datetime.now().strftime("%m-%d %H:%M")
    save_data(data)
    bot.reply_to(msg, "✅ 计时已开始")

@bot.message_handler(func=lambda m: "停止计时打卡" in m.text)
def stop_timer(msg):
    chat_id = str(msg.chat.id)
    t = data["timer"].get(chat_id, "未开始")
    bot.reply_to(msg, f"✅ 计时停止\n开始时间：{t}")

@bot.message_handler(func=lambda m: m.text == "@所有人")
def at_all(msg):
    bot.send_message(msg.chat.id, "📢 @all")

@bot.message_handler(func=lambda m: m.text.startswith("日切#"))
def set_day_cut(msg):
    chat_id = str(msg.chat.id)
    val = msg.text.split("#")[-1]
    data["day_cut"][chat_id] = val
    save_data(data)
    bot.reply_to(msg, f"✅ 日切已设为：{val}")

@bot.message_handler(commands=["我"])
def my_bill(msg):
    chat_id = str(msg.chat.id)
    user = get_username(msg)
    recs = [r for r in data["records"].get(chat_id, []) if r["user"] == user]
    in_sum = sum(r["money"] for r in recs if r["type"] == "入款")
    out_sum = sum(r["money"] for r in recs if r["type"] == "下发")
    bot.reply_to(msg, f"👤 个人账单\n入款：{in_sum}\n下发：{out_sum}")

@bot.message_handler(func=lambda m: m.text == "上课")
def class_open(msg):
    bot.set_chat_permissions(msg.chat.id, ChatPermissions(can_send_messages=True))
    bot.reply_to(msg, "✅ 上课，解除禁言")

@bot.message_handler(func=lambda m: m.text == "下课")
def class_close(msg):
    bot.set_chat_permissions(msg.chat.id, ChatPermissions(can_send_messages=False))
    bot.reply_to(msg, "✅ 下课，全员禁言")

@bot.message_handler(func=lambda m: m.text and len(m.text.split()) >= 2)
def name_record(msg):
    chat_id = str(msg.chat.id)
    parts = msg.text.split()
    if len(parts) < 2:
        return
    name = parts[0]
    act = parts[1]
    if act.startswith("+"):
        money = float(act[1:])
        data["records"][chat_id].append({
            "type": "入款", "money": money, "user": name,
            "time": datetime.now().strftime("%m-%d %H:%M")
        })
        save_data(data)
        bot.reply_to(msg, f"✅ {name} 入款 {money}")
        return
    if act == "下发" and len(parts) >= 3:
        money = float(parts[2])
        data["records"][chat_id].append({
            "type": "下发", "money": money, "user": name,
            "time": datetime.now().strftime("%m-%d %H:%M")
        })
        save_data(data)
        bot.reply_to(msg, f"✅ {name} 下发 {money}")
        return

@bot.message_handler(func=lambda m: m.text and any(c in m.text for c in "+-*/"))
def calc(msg):
    try:
        exp = msg.text.replace("×", "*").replace("÷", "/")
        res = eval(exp)
        bot.reply_to(msg, f"🧮 结果：{res}")
    except:
        return

if __name__ == "__main__":
    print("机器人启动成功 ✅")
    bot.infinity_polling()
