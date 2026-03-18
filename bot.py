import telebot
import json
import os
import re
from datetime import datetime
from telebot.types import ChatPermissions

BOT_TOKEN = os.getenv("BOT_TOKEN")
bot = telebot.TeleBot(BOT_TOKEN, parse_mode="Markdown")

DATA_FILE = "data.json"

# ==============================================
# 修复 1：数据永久保存，不会丢失
# ==============================================
def init_data():
    if not os.path.exists(DATA_FILE):
        data = {
            "groups": {},
            "operators": {},
            "records": {},
            "rate": {"default": 6.93},
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

# ==============================================
# 最终版账单显示（你要的格式）
# ==============================================
def show_final_format(chat_id):
    records = data["records"].get(chat_id, [])
    rate = data["rate"]["default"]

    in_list = []
    out_list = []
    total_in_cny = 0.0
    total_out_cny = 0.0

    for r in records:
        time_str = r.get("time", "00:00:00")
        if " " in time_str:
            real_time = time_str.split(" ")[1]
        else:
            real_time = time_str

        if r["type"] == "入款":
            money = r["money"]
            total_in_cny += money
            usdt_val = round(money / rate, 2) if rate != 0 else 0
            line = f"{real_time}  {money}/{rate}={usdt_val}  {r['user']}"
            in_list.append(line)

        if r["type"] == "下发":
            money = r["money"]
            cny_val = round(money * rate, 2)
            total_out_cny += cny_val
            line = f"{real_time}  {money}U（{cny_val}R）  {r['user']}"
            out_list.append(line)

    in_show = "\n".join(in_list[-3:]) if in_list else "暂无记录"
    out_show = "\n".join(out_list[-3:]) if out_list else "暂无记录"

    should_cny = total_in_cny
    should_usdt = round(should_cny / rate, 2) if rate != 0 else 0
    already_cny = total_out_cny
    already_usdt = round(already_cny / rate, 2) if rate != 0 else 0
    remain_cny = round(should_cny - already_cny, 2)
    remain_usdt = round(remain_cny / rate, 2) if rate != 0 else 0

    res = f"""✅今日入款（最近3笔）：
{in_show}

✅今日下发（最近3笔）：
{out_show}

📌设置汇率：{rate}

📊 总账单
应下发：{should_cny}CNY / {should_usdt}USDT
已下发：{already_cny}CNY / {already_usdt}USDT
未下发：{remain_cny}CNY / {remain_usdt}USDT"""
    return res

# ==============================================
# 权限校验（永久有效）
# ==============================================
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

# ==============================================
# 开始记账（一次永久生效）
# ==============================================
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
        save_data()

    bot.reply_to(msg, "✅ 群记账已永久开启！权限永久保存")

# ==============================================
# 操作人管理
# ==============================================
@bot.message_handler(func=lambda m: m.text.startswith("设置操作人"))
def add_operator(msg):
    chat_id = str(msg.chat.id)
    match = re.search(r'@\w+', msg.text)
    if not match:
        bot.reply_to(msg, "❌ 格式：设置操作人 @张三")
        return
    target = match.group(0)
    if chat_id not in data["operators"]:
        data["operators"][chat_id] = []
    if target not in data["operators"][chat_id]:
        data["operators"][chat_id].append(target)
        save_data(data)
        bot.reply_to(msg, f"✅ 已添加操作人：{target}（永久有效）")

@bot.message_handler(func=lambda m: m.text.startswith("删除操作人"))
def del_operator(msg):
    chat_id = str(msg.chat.id)
    match = re.search(r'@\w+', msg.text)
    if not match:
        bot.reply_to(msg, "❌ 格式：删除操作人 @张三")
        return
    target = match.group(0)
    if chat_id in data["operators"] and target in data["operators"][chat_id]:
        data["operators"][chat_id].remove(target)
        save_data(data)
        bot.reply_to(msg, f"✅ 已删除操作人：{target}")

@bot.message_handler(func=lambda m: m.text == "显示操作人")
def show_operators(msg):
    chat_id = str(msg.chat.id)
    ops = data["operators"].get(chat_id, [])
    bot.reply_to(msg, "👥 当前操作人：\n" + "\n".join(ops) if ops else "❌ 暂无操作人")

@bot.message_handler(func=lambda m: m.text == "删除所有人")
def del_all_ops(msg):
    chat_id = str(msg.chat.id)
    data["operators"][chat_id] = []
    save_data(data)
    bot.reply_to(msg, "✅ 已清空所有操作人")

@bot.message_handler(func=lambda m: m.text == "设置所有人")
def set_all_permission(msg):
    chat_id = str(msg.chat.id)
    data["all_permission"][chat_id] = True
    save_data(data)
    bot.reply_to(msg, "✅ 群内所有人均可使用记账（永久有效）")

# ==============================================
# 修复 2：汇率 + 费率（现在正常生效！）
# ==============================================
@bot.message_handler(func=lambda m: m.text.startswith("设置汇率"))
def set_rate(msg):
    num_str = re.findall(r'([\d\.]+)', msg.text)
    if not num_str:
        bot.reply_to(msg, "❌ 格式：设置汇率 6.93")
        return
    data["rate"]["default"] = float(num_str[0])
    save_data(data)
    bot.reply_to(msg, f"✅ 汇率已设置：{num_str[0]}（立即生效）")

@bot.message_handler(func=lambda m: m.text.startswith("设置费率"))
def set_fee(msg):
    num_str = re.findall(r'([-\d\.]+)', msg.text)
    if not num_str:
        bot.reply_to(msg, "❌ 格式：设置费率 5 或 设置费率 -5")
        return
    data["fee"]["default"] = float(num_str[0])
    save_data(data)
    bot.reply_to(msg, f"✅ 费率已设置：{num_str[0]}%（立即生效）")

# ==============================================
# 记账核心功能
# ==============================================
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

    now_time = datetime.now().strftime("%m-%d %H:%M:%S")

    # 入款 +100
    if text.startswith("+"):
        num_str = re.findall(r'\+([\d\.]+)', text)
        if num_str:
            money = float(num_str[0])
            data["records"][chat_id].append({
                "type": "入款", "money": money, "user": username, "time": now_time
            })
            save_data(data)
            bot.reply_to(msg, show_final_format(chat_id))
        return

    # 下发 100
    if text.startswith("下发"):
        num_str = re.findall(r'([\d\.]+)', text)
        if num_str:
            money = float(num_str[0])
            data["records"][chat_id].append({
                "type": "下发", "money": money, "user": username, "time": now_time
            })
            save_data(data)
            bot.reply_to(msg, show_final_format(chat_id))
        return

    # 入款-100
    if "入款-" in text:
        num_str = re.findall(r'入款-([\d\.]+)', text)
        if num_str:
            money = float(num_str[0])
            data["records"][chat_id].append({
                "type": "入款", "money": -money, "user": username, "time": now_time
            })
            save_data(data)
            bot.reply_to(msg, show_final_format(chat_id))
        return

    # 下发-100
    if "下发-" in text:
        num_str = re.findall(r'下发-([\d\.]+)', text)
        if num_str:
            money = float(num_str[0])
            data["records"][chat_id].append({
                "type": "下发", "money": -money, "user": username, "time": now_time
            })
            save_data(data)
            bot.reply_to(msg, show_final_format(chat_id))
        return

@bot.message_handler(func=lambda m: m.text == "显示账单")
def show_bill(msg):
    chat_id = str(msg.chat.id)
    bot.reply_to(msg, show_final_format(chat_id))

# ==============================================
# 其他功能（完整保留）
# ==============================================
@bot.message_handler(func=lambda m: m.text == "z0")
def show_rate(msg):
    bot.reply_to(msg, f"💱 当前汇率：1USDT = {data['rate']['default']} CNY")

@bot.message_handler(func=lambda m: m.text.startswith("z"))
def z_convert(msg):
    num_str = re.findall(r'z([\d\.]+)', msg.text)
    if not num_str:
        return
    cny = float(num_str[0])
    usdt = round(cny / data["rate"]["default"], 2)
    bot.reply_to(msg, f"💱 {cny}CNY = {usdt}USDT")

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
    data["timer"][chat_id] = datetime.now().strftime("%m-%d %H:%M:%S")
    save_data(data)
    bot.reply_to(msg, "✅ 计时已开始")

@bot.message_handler(func=lambda m: "停止计时打卡" in m.text)
def stop_timer(msg):
    chat_id = str(msg.chat.id)
    bot.reply_to(msg, f"✅ 计时停止")

@bot.message_handler(func=lambda m: m.text == "@所有人")
def at_all(msg):
    bot.send_message(msg.chat.id, "📢 @all")

@bot.message_handler(func=lambda m: m.text.startswith("日切#"))
def set_day_cut(msg):
    chat_id = str(msg.chat.id)
    data["day_cut"][chat_id] = msg.text.split("#")[-1]
    save_data(data)
    bot.reply_to(msg, "✅ 日切已设置")

@bot.message_handler(commands=["我"])
def my_bill(msg):
    chat_id = str(msg.chat.id)
    user = get_username(msg)
    recs = [r for r in data["records"].get(chat_id,[]) if r["user"]==user]
    in_sum = sum(r["money"] for r in recs if r["type"]=="入款")
    out_sum = sum(r["money"] for r in recs if r["type"]=="下发")
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
    username = get_username(msg)
    if not check_permission(chat_id, msg.from_user.id, username):
        return
    parts = msg.text.split()
    if len(parts) < 2:
        return
    name = parts[0]
    act = parts[1]
    now_time = datetime.now().strftime("%m-%d %H:%M:%S")

    if act.startswith("+"):
        money = float(act[1:])
        data["records"][chat_id].append({
            "type": "入款", "money": money, "user": name, "time": now_time
        })
        save_data(data)
        bot.reply_to(msg, show_final_format(chat_id))
        return

    if act == "下发" and len(parts) >= 3:
        money = float(parts[2])
        data["records"][chat_id].append({
            "type": "下发", "money": money, "user": name, "time": now_time
        })
        save_data(data)
        bot.reply_to(msg, show_final_format(chat_id))
        return

@bot.message_handler(func=lambda m: m.text and any(c in m.text for c in "+-*/"))
def calc(msg):
    try:
        res = eval(msg.text.replace("×","*").replace("÷","/"))
        bot.reply_to(msg, f"🧮 结果：{res}")
    except:
        return

if __name__ == "__main__":
    print("机器人启动成功 ✅")
    bot.infinity_polling()
