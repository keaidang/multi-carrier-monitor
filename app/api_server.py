#!/usr/bin/env python3
# _*_ coding:utf-8 _*_

import os
import sys
import json
from datetime import datetime
from flask import Flask, request, jsonify, render_template

# 导入父目录的依赖
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)
from telecom_class import Telecom
from unicom_class import Unicom
import threading
import requests

def get_phone_location(phone):
    """通过第三方API获取手机号归属地"""
    try:
        # 使用 360 的归属地查询接口
        url = f"https://cx.shouji.360.cn/phonearea.php?number={phone}"
        r = requests.get(url, timeout=5)
        res = r.json()
        if res.get("code") == 0:
            data = res.get("data", {})
            return data.get("province", "联通"), data.get("city", "账户")
    except Exception as e:
        print(f"获取号码归属地异常: {e}")
    return "联通", "账户"

class TelecomProxy:
    def __init__(self):
        object.__setattr__(self, "_local", threading.local())
    
    @property
    def _telecom(self):
        if not hasattr(self._local, "instance"):
            self._local.instance = Telecom()
        return self._local.instance

    def __getattr__(self, name):
        return getattr(self._telecom, name)

    def __setattr__(self, name, value):
        setattr(self._telecom, name, value)

telecom = TelecomProxy()

class UnicomProxy:
    def __init__(self):
        object.__setattr__(self, "_local", threading.local())
    
    @property
    def _unicom(self):
        if not hasattr(self._local, "instance"):
            self._local.instance = Unicom()
        return self._local.instance

    def __getattr__(self, name):
        return getattr(self._unicom, name)

    def __setattr__(self, name, value):
        setattr(self._unicom, name, value)

unicom = UnicomProxy()

app = Flask(__name__, template_folder='templates')
app.json.ensure_ascii = False
app.json.sort_keys = False

# 登录信息存储文件
LOGIN_INFO_FILE = os.environ.get("CONFIG_PATH", os.path.join(parent_dir, "config", "login_info.json"))


@app.after_request
def after_request(response):
    """支持 CORS 和禁用缓存"""
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type')
    response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE,OPTIONS')
    # 禁用缓存
    response.headers.add('Cache-Control', 'no-cache, no-store, must-revalidate, public, max-age=0')
    response.headers.add('Pragma', 'no-cache')
    response.headers.add('Expires', '0')
    return response


@app.route('/')
def index():
    """主页"""
    return render_template('index.html')


@app.route('/debug')
def debug():
    """调试页面"""
    return render_template('debug.html')


def load_login_info():
    """加载本地登录信息"""
    try:
        with open(LOGIN_INFO_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}


def save_login_info(login_info):
    """保存登录信息到本地"""
    os.makedirs(os.path.dirname(LOGIN_INFO_FILE), exist_ok=True)
    with open(LOGIN_INFO_FILE, "w", encoding="utf-8") as f:
        json.dump(login_info, f, ensure_ascii=False, indent=2)


@app.route("/login", methods=["POST", "GET"])
def login():
    """登录接口"""
    data = request.get_json() if request.method == "POST" else request.args
    phonenum, password = data.get("phonenum"), data.get("password")
    carrier = data.get("carrier", "telecom")
    
    if not phonenum or not password:
        return jsonify({"message": "手机号和密码不能为空"}), 400
    elif whitelist_num := os.environ.get("WHITELIST_NUM"):
        if not phonenum in whitelist_num:
            return jsonify({"message": "手机号不在白名单"}), 400

    login_info = load_login_info()
    
    if carrier == "unicom":
        return jsonify({"responseData": {"resultCode": "9999", "resultMsg": "联通暂不支持密码登录，请使用 Cookie 导入方式"}}), 400

    # 电信登录原有逻辑
    data = telecom.do_login(phonenum, password)
    if data.get("responseData") and data.get("responseData").get("resultCode") == "0000":
        login_info[phonenum] = data["responseData"]["data"]["loginSuccessResult"]
        login_info[phonenum]["phonenum"] = phonenum
        login_info[phonenum]["password"] = password
        login_info[phonenum]["carrier"] = "telecom"
        login_info[phonenum]["createTime"] = datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S"
        )
        save_login_info(login_info)
        return jsonify(data), 200
    else:
        return jsonify(data), 400


@app.route("/send_sms_code", methods=["POST", "GET"])
def send_sms_code():
    """发送短信验证码接口"""
    data = request.get_json() if request.method == "POST" else request.args
    phonenum = data.get("phonenum")
    if not phonenum:
        return jsonify({"message": "手机号不能为空"}), 400
    res = unicom.send_sms_code(phonenum)
    if res.get("rsp_code") == "0000":
        return jsonify({"status": "success", "message": "验证码发送成功", "data": res}), 200
    else:
        return jsonify({"status": "error", "message": res.get("desc") or "验证码发送失败", "data": res}), 400


@app.route("/login_sms", methods=["POST", "GET"])
def login_sms():
    """验证码登录接口"""
    data = request.get_json() if request.method == "POST" else request.args
    phonenum = data.get("phonenum")
    smscode = data.get("smscode")
    if not phonenum or not smscode:
        return jsonify({"message": "手机号和验证码不能为空"}), 400
    
    login_info = load_login_info()
    res = unicom.login_sms(phonenum, smscode)
    if res.get("code") == "0":
        prov, city = get_phone_location(phonenum)
        login_info[phonenum] = {
            "phonenum": phonenum,
            "password": "",
            "carrier": "unicom",
            "cookie": unicom.cookie,
            "appId": unicom.appId,
            "provinceName": prov,
            "cityName": city,
            "createTime": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        save_login_info(login_info)
        return jsonify({"responseData": {"resultCode": "0000", "resultMsg": "短信登录成功", "data": {"loginSuccessResult": login_info[phonenum]}}}), 200
    else:
        return jsonify({"responseData": {"resultCode": "9999", "resultMsg": res.get("dsc") or "短信登录失败"}}), 400


@app.route("/login_cookie", methods=["POST", "GET"])
def login_cookie():
    """Cookie导入接口"""
    data = request.get_json() if request.method == "POST" else request.args
    phonenum = data.get("phonenum")
    cookie = data.get("cookie")
    if not phonenum or not cookie:
        return jsonify({"message": "手机号和Cookie不能为空"}), 400
    
    login_info = load_login_info()
    login_info[phonenum] = {
        "phonenum": phonenum,
        "password": "",
        "carrier": "unicom",
        "cookie": cookie,
        "appId": "",
        "provinceName": "联通",
        "cityName": "账户(Cookie)",
        "createTime": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    save_login_info(login_info)
    return jsonify({"responseData": {"resultCode": "0000", "resultMsg": "Cookie 导入成功", "data": {"loginSuccessResult": login_info[phonenum]}}}), 200



def query_data(query_func, **kwargs):
    """
    查询数据，如果本地没有登录信息或密码不匹配，则尝试登录后再查询
    """
    data = request.get_json() if request.method == "POST" else request.args
    phonenum, password = data.get("phonenum"), data.get("password")
    # 检查登录信息，避免重复登录
    login_info = load_login_info()
    if (
        phonenum in login_info
        and login_info[phonenum].get("phonenum") == phonenum
        and login_info[phonenum].get("password") == password
    ):
        telecom.set_login_info(login_info[phonenum])
        data = query_func(**kwargs)
        if data.get("responseData"):
            return jsonify(data), 200
        elif data.get("headerInfos", {}).get("code") != "X201":
            # X201 = token 过期
            return jsonify(data), 400
    # 重新登录
    login_data, status_code = login()
    login_data = json.loads(login_data.data)
    if status_code == 200:
        telecom.set_login_info(login_data["responseData"]["data"]["loginSuccessResult"])
        data = query_func(**kwargs)
        if data.get("responseData"):
            return jsonify(data), 200
        else:
            return jsonify(data), 400
    else:
        return jsonify(login_data), 400


@app.route("/qryImportantData", methods=["POST", "GET"])
def qry_important_data():
    """查询基本数据接口"""
    return query_data(telecom.qry_important_data)


@app.route("/userFluxPackage", methods=["POST", "GET"])
def user_flux_package():
    """查询流量包接口"""
    return query_data(telecom.user_flux_package)


@app.route("/qryShareUsage", methods=["POST", "GET"])
def qry_share_usage():
    """查询共享用量接口"""
    if request.method == "POST":
        data = request.get_json() or {}
    else:
        data = request.args
    return query_data(telecom.qry_share_usage, billing_cycle=data.get("billing_cycle"))


@app.route("/summary", methods=["POST", "GET"])
def summary():
    """查询基本数据简化接口"""
    important_data, status_code = query_data(telecom.qry_important_data)
    if status_code == 200:
        data = telecom.to_summary(
            json.loads(important_data.data)["responseData"]["data"]
        )
        return jsonify(data), 200


@app.route("/all_accounts", methods=["GET"])
def all_accounts():
    """获取所有已登录的账户列表"""
    login_info = load_login_info()
    accounts = []
    changed = False
    for phonenum, info in login_info.items():
        # 如果省份是通用的，尝试修复
        if info.get("provinceName") in ["联通", "电信", ""] or info.get("cityName") in ["账户", "账户(Cookie)", ""]:
            prov, city = get_phone_location(phonenum)
            info["provinceName"] = prov
            info["cityName"] = city
            changed = True
            
        accounts.append({
            "phonenum": phonenum,
            "createTime": info.get("createTime", ""),
            "provinceName": info.get("provinceName", ""),
            "cityName": info.get("cityName", ""),
            "carrier": info.get("carrier", "telecom")
        })
    
    if changed:
        save_login_info(login_info)
        
    return jsonify({"accounts": accounts}), 200


@app.route("/delete_account/<phonenum>", methods=["DELETE"])
def delete_account(phonenum):
    """删除指定账户"""
    login_info = load_login_info()
    if phonenum not in login_info:
        return jsonify({"message": "账户不存在"}), 404

    del login_info[phonenum]
    save_login_info(login_info)
    return jsonify({"message": f"账户 {phonenum} 已删除"}), 200


@app.route("/account_summary/<phonenum>", methods=["GET"])
def account_summary(phonenum):
    """获取指定账户的信息"""
    try:
        login_info = load_login_info()
        if phonenum not in login_info:
            return jsonify({"message": "账户不存在"}), 404

        login_info_data = login_info[phonenum]
        
        # 实时修复逻辑
        if login_info_data.get("provinceName") in ["联通", "电信", ""] or login_info_data.get("cityName") in ["账户", "账户(Cookie)", ""]:
            prov, city = get_phone_location(phonenum)
            login_info_data["provinceName"] = prov
            login_info_data["cityName"] = city
            save_login_info(login_info)

        is_unicom = (login_info_data.get("carrier") == "unicom")

        if is_unicom:
            unicom.cookie = login_info_data.get("cookie")
            unicom.appId = login_info_data.get("appId")
            unicom.phonenum = phonenum
            
            raw_data = unicom.query()
            if not isinstance(raw_data, dict):
                return jsonify({"message": "联通查询返回格式错误"}), 400
            
            if raw_data.get("code") in ["999999", "999998", "expired", "error"]:
                desc = raw_data.get("desc", "Cookie 已过期，请重新导入")
                return jsonify({"message": desc}), 400
            
            if raw_data.get("code") == "0000":
                summary_data = unicom.to_summary(raw_data)
                summary_data["provinceName"] = login_info_data.get("provinceName", "联通")
                summary_data["cityName"] = login_info_data.get("cityName", "账户")
                return jsonify(summary_data), 200
            else:
                return jsonify({"message": raw_data.get("desc") or "联通查询返回异常"}), 400

        # 以下是电信原有逻辑
        telecom.set_login_info(login_info_data)
        
        # 1. 获取基本数据 (余额，通话等)
        important_data = telecom.qry_important_data()
        
        # 2. 获取流量包明细数据
        flux_package_data = {}
        try:
            flux_package_data = telecom.user_flux_package()
        except Exception as e:
            print(f"获取详细包数据出错: {e}")

        if important_data.get("responseData"):
            # 获取转换后的数据
            summary_data = telecom.to_summary(important_data["responseData"]["data"])
            summary_data["provinceName"] = login_info_data.get("provinceName", "")
            summary_data["cityName"] = login_info_data.get("cityName", "")
            summary_data["carrier"] = "telecom"

            # 从流量包列表中提取真实的 GB 数值
            raw_data = important_data["responseData"]["data"]
            flow_list = raw_data.get("flowInfo", {}).get("flowList", [])

            # 解析流量包中的真实GB数值
            total_gb = 0
            common_gb = 0
            special_gb = 0
            common_use_gb = 0
            special_use_gb = 0
            new_flow_items = []
            
            is_special_unlimited_flag = False

            for item in flow_list:
                try:
                    title = item.get("title", "")
                    if "云盘" in title or "空间" in title:
                        continue

                    right_end = item.get("rightTitleEnd", "")
                    left_end = item.get("leftTitleHh", "0GB")

                    # 解析已用量 (use)
                    use = 0
                    if "MB" in left_end:
                        use_mb_str = left_end.replace("MB", "").strip()
                        use = float(use_mb_str) / 1024 if use_mb_str else 0
                    elif "GB" in left_end:
                        use_gb_str = left_end.replace("GB", "").strip()
                        use = float(use_gb_str) if use_gb_str else 0

                    # 解析总量 (total)
                    total = -1  # 默认 -1 表示无上限/不限量
                    if "/" in right_end:
                        if "GB" in right_end:
                            total_str = right_end.split("/")[1].replace("GB", "").strip()
                            total = float(total_str) if total_str else 0
                        elif "MB" in right_end:
                            total_str = right_end.split("/")[1].replace("MB", "").strip()
                            total = (float(total_str) / 1024) if total_str else 0

                    if "通用" in title or "国内" in title:
                        if total > 0:
                            common_gb += total
                            total_gb += total
                        common_use_gb += use
                    elif "专用" in title or "定向" in title:
                        if total > 0:
                            special_gb += total
                            total_gb += total
                        else:
                            is_special_unlimited_flag = True
                        special_use_gb += use

                    # 余额计算
                    balance_val = (total - use) if total >= 0 else 0

                    new_flow_items.append({
                        "name": title,
                        "use": int(use * 1024 * 1024 * 1024),
                        "balance": int(balance_val * 1024 * 1024 * 1024),
                        "total": int(total * 1024 * 1024 * 1024) if total >= 0 else -1
                    })
                except (ValueError, IndexError, AttributeError, TypeError) as e:
                    # 如果解析失败，跳过该条目
                    continue

            # 更新汇总数据为基于 GB 的计算
            if total_gb > 0:
                summary_data["flowTotal"] = int(total_gb * 1024 * 1024 * 1024)  # 转换回字节以保持兼容性
                summary_data["flowUse"] = int((common_use_gb + special_use_gb) * 1024 * 1024 * 1024)
                summary_data["commonTotal"] = int(common_gb * 1024 * 1024 * 1024)
                summary_data["commonUse"] = int(common_use_gb * 1024 * 1024 * 1024)
                if special_gb > 0:
                    summary_data["specialTotal"] = int(special_gb * 1024 * 1024 * 1024)
                elif is_special_unlimited_flag:
                    summary_data["specialTotal"] = -1
                else:
                    summary_data["specialTotal"] = 0
                summary_data["specialUse"] = int(special_use_gb * 1024 * 1024 * 1024)
                summary_data["flowItems"] = new_flow_items

            # 3. 解析各个详细的子流量包
            common_packages = []
            special_packages = []

            if flux_package_data.get("responseData"):
                package_list = flux_package_data["responseData"]["data"].get("productOFFRatable", {}).get("ratableResourcePackages", [])
                for pkg in package_list:
                    pkg_title = pkg.get("title", "")
                    product_infos = pkg.get("productInfos", [])
                    
                    is_common = "通用" in pkg_title or "国内" in pkg_title
                    is_special = "专用" in pkg_title or "定向" in pkg_title
                    
                    if not (is_common or is_special):
                        continue
                        
                    target_list = common_packages if is_common else special_packages
                    
                    for prod in product_infos:
                        title = prod.get("title", "")
                        if "云盘" in title or "空间" in title:
                            continue
                        
                        is_infinite = prod.get("isInfiniteAmount") == "1"
                        if is_infinite:
                            inf_val = prod.get("infiniteValue") or "0"
                            inf_unit = prod.get("infiniteUnit") or "GB"
                            use_str = f"{inf_val}{inf_unit}"
                            total_str = "无限"
                        else:
                            use_str = prod.get("leftHighlight") or "0KB"
                            right_common = prod.get("rightCommon") or ""
                            right_high = prod.get("rightHighlight") or ""
                            if "/共" in right_common:
                                total_str = right_common.replace("/共", "").strip()
                            elif right_common.startswith("/"):
                                total_str = right_common.replace("/", "").strip()
                            else:
                                total_str = right_common.strip() or right_high.strip() or "未知"
                                
                        if use_str.isdigit():
                            use_str = use_str + "KB"
                        if total_str.isdigit():
                            total_str = total_str + "GB"
                            
                        if total_str.startswith("共"):
                            total_str = total_str[1:]
                            
                        target_list.append({
                            "name": title,
                            "use": use_str,
                            "total": total_str
                        })

            # 4. 生成 formattedText 文本结构
            lines = []
            lines.append(f"手机：{phonenum}")
            
            balance_yuan = (summary_data.get("balance", 0) / 100)
            lines.append(f"余额：{balance_yuan:.2f}元")
            
            voice_use = summary_data.get("voiceUsage", 0)
            voice_total = summary_data.get("voiceTotal", 0)
            lines.append(f"通话：{voice_use} / {voice_total} min")
            
            lines.append("总流量")
            
            # 通用
            com_use_gb = (summary_data.get("commonUse", 0) / 1024 / 1024 / 1024)
            com_tot_gb = (summary_data.get("commonTotal", 0) / 1024 / 1024 / 1024)
            
            lines.append(f"  - 通用：{com_use_gb:.2f} / {com_tot_gb:.2f} GB")
            
            # 定向
            spec_use_gb = (summary_data.get("specialUse", 0) / 1024 / 1024 / 1024)
            spec_tot_gb = (summary_data.get("specialTotal", 0) / 1024 / 1024 / 1024)
            
            if is_special_unlimited_flag or spec_tot_gb < 0:
                lines.append(f"  - 定向：{spec_use_gb:.2f} / ∞")
            else:
                lines.append(f"  - 定向：{spec_use_gb:.2f} / {spec_tot_gb:.2f} GB")
                
            lines.append("")
            lines.append("【流量包明细】")
            lines.append("")
            
            lines.append("国内通用流量")
            for pkg in common_packages:
                total_prefix = "" if pkg['total'].startswith("共") else "共"
                lines.append(f"[{pkg['name']}]已用{pkg['use']}/{total_prefix}{pkg['total']}")
                
            lines.append("")
            lines.append("专用流量")
            for pkg in special_packages:
                total_disp = pkg['total']
                if "无限" in total_disp or total_disp == "-1" or total_disp == "无上限":
                    total_disp = "∞"
                lines.append(f"[{pkg['name']}]已用{pkg['use']}/{total_disp}")

            summary_data["commonPackages"] = common_packages
            summary_data["specialPackages"] = special_packages
            summary_data["formattedText"] = "\n".join(lines)

            return jsonify(summary_data), 200
        else:
            return jsonify(important_data), 400
    except Exception as e:
        import traceback
        error_msg = f"服务器错误: {str(e)}"
        traceback.print_exc()
        return jsonify({"message": error_msg}), 500


def start_keep_alive():
    import threading
    import time
    
    def keep_alive_task():
        # 启动后延迟 10 秒开始第一次保活
        time.sleep(10)
        while True:
            try:
                login_info = load_login_info()
                for phonenum, info in list(login_info.items()):
                    if info.get("carrier") == "unicom" and info.get("cookie"):
                        cookie = info.get("cookie")
                        from unicom_class import Unicom
                        unicom = Unicom(phonenum=phonenum, cookie=cookie)
                        print(f"[Keep-Alive] 正在保活联通账号: {phonenum}...")
                        res = unicom.query()
                        if isinstance(res, dict) and res.get("code") == "0000":
                            print(f"[Keep-Alive] 账号 {phonenum} 保活成功！")
                        else:
                            print(f"[Keep-Alive] 账号 {phonenum} 保活失败: {res.get('desc') if isinstance(res, dict) else '未知错误'}")
            except Exception as e:
                print(f"[Keep-Alive] 保活执行出错: {e}")
            time.sleep(300) # 每 5 分钟请求一次以保活会话
            
    thread = threading.Thread(target=keep_alive_task, daemon=True)
    thread.start()


start_keep_alive()


if __name__ == "__main__":
    app.run(debug=os.environ.get("DEBUG", False), host="0.0.0.0", port=10000)
