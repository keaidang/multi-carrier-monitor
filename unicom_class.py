#!/usr/bin/env python3
# _*_ coding:utf-8 _*_

import re
import random
import string
import requests
import base64
from datetime import datetime
from Crypto.PublicKey import RSA
from Crypto.Cipher import PKCS1_v1_5


class Unicom:
    # 联通App端公钥
    PUBLIC_KEY = (
        "MIGfMA0GCSqGSIb3DQEBAQUAA4GNADCBiQKBgQDc+CZK9bBA9IU+gZUOc6FUGu7y"
        "O9WpTNB0PzmgFBh96Mg1WrovD1oqZ+eIF4LjvxKXGOdI79JRdve9NPhQo07+uqGQ"
        "gE4imwNnRx7PFtCRryiIEcUoavuNtuRVoBAm6qdB0SrctgaqGfLgKvZHOnwTjyNq"
        "jBUxzMeQlEC2czEMSwIDAQAB"
    )

    def __init__(self, phonenum=None, password=None, cookie=None, appId=None):
        self.phonenum = phonenum
        self.password = password
        self.cookie = cookie
        self.appId = appId

        self.session = requests.Session()
        self.headers = {
            "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 Alliance/1.0.0 client/iphone_c/9.0100",
            "Accept": "*/*",
            "Accept-Language": "zh-CN,zh-Hans;q=0.9",
        }

    def encrypt(self, text):
        """RSA加密 (PKCS#1 v1.5)"""
        if not text:
            return ""
        key_pem = f"-----BEGIN PUBLIC KEY-----\n{self.PUBLIC_KEY}\n-----END PUBLIC KEY-----"
        pub_key = RSA.import_key(key_pem.encode('utf-8'))
        cipher = PKCS1_v1_5.new(pub_key)
        ciphertext = cipher.encrypt(text.encode('utf-8'))
        return base64.b64encode(ciphertext).decode('utf-8')

    def random_string(self, length=160):
        """生成随机字符串"""
        chars = string.ascii_letters + string.digits
        return ''.join(random.choice(chars) for _ in range(length))

    def send_sms_code(self, phonenum):
        """发送短信验证码"""
        url = "https://m.client.10010.com/mobileService/sendRadomNum.htm"
        headers = self.headers.copy()
        headers["Content-Type"] = "application/x-www-form-urlencoded"

        payload = {
            "mobile": self.encrypt(phonenum),
            "version": "iphone_c@9.0100"
        }

        response = self.session.post(url, headers=headers, data=payload)
        return response.json()

    def login_sms(self, phonenum, smscode):
        """短信验证码登录"""
        url = "https://m.client.10010.com/mobileService/radomLogin.htm"
        headers = self.headers.copy()
        headers["Content-Type"] = "application/x-www-form-urlencoded"

        app_id = self.random_string(160)
        payload = {
            "mobile": self.encrypt(phonenum),
            "password": self.encrypt(smscode),
            "appId": app_id,
            "version": "iphone_c@9.0100"
        }

        response = self.session.post(url, headers=headers, data=payload)
        res_data = response.json()

        if res_data.get("code") == "0":
            cookies = response.headers.get("Set-Cookie") or response.headers.get("set-cookie")
            if cookies:
                if isinstance(cookies, list):
                    self.cookie = "; ".join(cookies)
                else:
                    self.cookie = cookies
            self.appId = res_data.get("appId") or app_id
            self.phonenum = phonenum

        return res_data

    def query(self, cookie=None):
        """查询流量、话费、语音（Cookie方案，双接口）"""
        cookie_val = cookie or self.cookie
        if not cookie_val:
            return {"code": "expired", "desc": "未配置 Cookie，请重新登录或导入 Cookie"}

        # 补全可能丢失的 s 字符
        if cookie_val.startswith("ervicequerybusiness="):
            cookie_val = "s" + cookie_val

        # ========== 接口1: 流量明细 (mxx) ==========
        flow_url = "https://mxx.client.10010.com/servicequerybusiness/operationservice/queryOcsPackageFlowLeftContentRevisedInJune"
        flow_payload = "duanlianjieabc=&channelCode=&serviceType=&saleChannel=&externalSources=&contactCode=&ticket=&ticketPhone=&ticketChannel=&version=WT&userNumber=&language=chinese"
        flow_headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Content-Type": "application/x-www-form-urlencoded",
            "Origin": "https://imgxx.client.10010.com",
            "Referer": "https://imgxx.client.10010.com/",
            "cookie": cookie_val
        }

        res_flow_data = None
        try:
            r_flow = self.session.post(flow_url, headers=flow_headers, data=flow_payload, timeout=15)
            try:
                res_flow_data = r_flow.json()
            except Exception:
                text = r_flow.content.decode('gb18030', errors='ignore').strip()
                if text in ["999999", "999998"]:
                    return {"code": "expired", "desc": "登录会话已过期，请重新登录抓取 Cookie"}
                return {"code": "error", "desc": f"流量接口返回异常: {text[:200]}"}
        except Exception as e:
            return {"code": "error", "desc": f"请求流量接口失败: {str(e)}"}

        if isinstance(res_flow_data, (int, float, str)):
            val_str = str(res_flow_data)
            if val_str in ["999999", "999998"]:
                return {"code": "expired", "desc": "登录会话已过期，请重新登录抓取 Cookie"}
            return {"code": "error", "desc": f"流量接口返回异常: {val_str[:200]}"}

        if not isinstance(res_flow_data, dict):
            return {"code": "error", "desc": "流量接口返回数据格式错误"}

        # ========== 从流量接口响应中提取语音数据 ==========
        voice_used = -1
        voice_remain = -1
        voice_total = -1
        try:
            for res in res_flow_data.get("resources", []):
                if res.get("type") == "Voice":
                    voice_remain = int(float(res.get("remainResource") or 0))
                    voice_used = int(float(res.get("userResource") or 0))
                    voice_total = voice_used + voice_remain
                    break
            # 兜底: 用顶层字段
            if voice_used < 0:
                vh = res_flow_data.get("voiceHeadUsed")
                vs = res_flow_data.get("voiceSumresource")
                cv = res_flow_data.get("canUseValueAll")
                if vh is not None and cv is not None:
                    voice_used = int(float(vh))
                    voice_remain = int(float(cv))
                    voice_total = voice_used + voice_remain
        except Exception:
            pass

        # ========== 查询话费余额 (m.client) ==========
        balance_val = -1.0
        balance_url = "https://m.client.10010.com/servicequerybusiness/balancenew/accountBalancenew.htm"
        balance_payload = "duanlianjieabc=&channelCode=&serviceType=&saleChannel=&externalSources=&contactCode=&version=WT"
        balance_headers = flow_headers.copy()
        balance_headers["Origin"] = "https://img.client.10010.com"
        balance_headers["Referer"] = "https://img.client.10010.com/"
        try:
            r_bal = self.session.post(balance_url, headers=balance_headers, data=balance_payload, timeout=15)
            bal_data = r_bal.json()
            if isinstance(bal_data, dict) and "curntbalancecust" in bal_data:
                balance_val = float(bal_data["curntbalancecust"])
        except Exception as e:
            print(f"查询联通余额出错: {e}")

        # 注入到返回数据中
        res_flow_data["balance_val"] = balance_val
        res_flow_data["voice_used"] = voice_used
        res_flow_data["voice_remain"] = voice_remain
        res_flow_data["voice_total"] = voice_total
        res_flow_data["code"] = "0000"

        return res_flow_data

    def to_summary(self, data, phonenum=""):
        """格式化输出统一的摘要数据"""
        if not data or not isinstance(data, dict):
            return {}

        phonenum = phonenum or self.phonenum
        time_str = data.get("time") or datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # ===== 流量汇总 =====
        # allUserFlow 和 summary.sum 单位是 MB
        try:
            total_used_mb = float(data.get("allUserFlow") or data.get("summary", {}).get("sum") or 0)
        except (ValueError, TypeError):
            total_used_mb = 0

        try:
            free_flow_mb = float(data.get("summary", {}).get("freeFlow") or 0)
        except (ValueError, TypeError):
            free_flow_mb = 0

        # resources[0] 是流量资源，remainResource 单位也是 MB
        remain_mb = 0
        resources = data.get("resources", [])
        for res in resources:
            res_type = res.get("type", "")
            if res_type == "flow" or res_type == "":
                try:
                    remain_mb = float(res.get("remainResource") or 0)
                except (ValueError, TypeError):
                    pass
                break

        # 计算通用流量 (MB -> bytes)
        fee_used_mb = max(0.0, total_used_mb - free_flow_mb)
        fee_total_mb = fee_used_mb + remain_mb

        MB = 1024 * 1024
        common_use = int(fee_used_mb * MB)
        common_total = int(fee_total_mb * MB)
        special_use = int(free_flow_mb * MB)
        special_total = -1

        flow_use = int(total_used_mb * MB)
        flow_total = common_total

        # ===== 话费 & 语音 =====
        balance_val = data.get("balance_val", -1.0)
        voice_used = data.get("voice_used", -1)
        voice_remain = data.get("voice_remain", -1)
        voice_total = data.get("voice_total", -1)

        # ===== 流量包明细 =====
        common_packages = []
        special_packages = []
        flow_items = []
        has_details = False

        calc_common_use = 0
        calc_common_total = 0
        calc_special_use = 0
        calc_special_total = 0
        has_special_unlimited = False

        for res in resources:
            res_type = res.get("type", "")
            if res_type not in ("flow", ""):
                continue
            details = res.get("details", [])
            if details:
                has_details = True
            for det in details:
                name = det.get("addUpItemName") or det.get("feePolicyName") or det.get("packageName") or ""
                if not name:
                    continue

                use_mb = float(det.get("use") or 0)
                total_mb = float(det.get("total") or 0)
                remain_det_mb = float(det.get("remain") or 0)

                use_bytes = int(use_mb * MB)
                total_bytes = int(total_mb * MB)
                remain_bytes = int(remain_det_mb * MB)

                is_special = any(k in name for k in ["专用", "定向", "专属", "免流", "APP", "腾讯", "阿里", "抖音", "爱奇艺", "优酷", "B站", "快手", "网易"])

                pkg_info = {
                    "name": name,
                    "use": self._fmt(use_mb),
                    "total": self._fmt(total_mb)
                }

                if is_special:
                    special_packages.append(pkg_info)
                    calc_special_use += use_bytes
                    if total_bytes <= 0:
                        has_special_unlimited = True
                    else:
                        calc_special_total += total_bytes
                else:
                    common_packages.append(pkg_info)
                    calc_common_use += use_bytes
                    calc_common_total += total_bytes

                flow_items.append({
                    "name": name,
                    "use": use_bytes,
                    "balance": remain_bytes,
                    "total": total_bytes
                })

        if has_details:
            common_use = calc_common_use
            common_total = calc_common_total
            special_use = calc_special_use
            special_total = -1 if has_special_unlimited or (calc_special_total == 0 and calc_special_use > 0) else calc_special_total
            flow_use = common_use + special_use
            flow_total = common_total + (special_total if special_total > 0 else 0)
        else:
            # 兜底
            common_use = int(fee_used_mb * MB)
            common_total = int(fee_total_mb * MB)
            special_use = int(free_flow_mb * MB)
            special_total = -1
            flow_use = int(total_used_mb * MB)
            flow_total = common_total

            common_packages.append({
                "name": "国内通用流量",
                "use": self._fmt(fee_used_mb),
                "total": self._fmt(fee_total_mb)
            })
            if free_flow_mb > 0:
                special_packages.append({
                    "name": "免流/定向流量",
                    "use": self._fmt(free_flow_mb),
                    "total": "∞"
                })
            flow_items.append({"name": "国内通用流量", "use": common_use, "balance": int(remain_mb * MB), "total": common_total})
            if free_flow_mb > 0:
                flow_items.append({"name": "免流/定向流量", "use": special_use, "balance": -1, "total": -1})

        # ===== formattedText =====
        lines = []
        lines.append(f"手机：{phonenum}")
        lines.append(f"余额：{balance_val:.2f} 元" if balance_val >= 0 else "余额：--")
        if voice_total >= 0:
            lines.append(f"通话：{voice_used} / {voice_total} min（剩余 {voice_remain} min）")
        else:
            lines.append("通话：-- / -- min")
        lines.append("总流量")
        lines.append(f"  - 通用：{self._fmt(common_use / MB)} / {self._fmt(common_total / MB)}")
        lines.append(f"  - 定向：{self._fmt(special_use / MB)} / {self._fmt(special_total / MB) if special_total > 0 else '∞'}")
        lines.append("")
        lines.append("【流量包明细】")
        lines.append("")
        lines.append("国内通用流量")
        for pkg in common_packages:
            lines.append(f"  [{pkg['name']}] 已用 {pkg['use']} / 共 {pkg['total']}")
        if special_packages:
            lines.append("")
            lines.append("专用流量")
            for pkg in special_packages:
                lines.append(f"  [{pkg['name']}] 已用 {pkg['use']} / {pkg['total']}")

        summary = {
            "phonenum": phonenum,
            "balance": int(balance_val * 100) if balance_val >= 0 else -1,
            "voiceUsage": voice_used if voice_used >= 0 else 0,
            "voiceBalance": voice_remain if voice_remain >= 0 else 0,
            "voiceTotal": voice_total,
            "flowUse": flow_use,
            "flowTotal": flow_total,
            "flowOver": 0,
            "commonUse": common_use,
            "commonTotal": common_total,
            "commonOver": 0,
            "specialUse": special_use,
            "specialTotal": special_total,
            "createTime": time_str,
            "flowItems": flow_items,
            "commonPackages": common_packages,
            "specialPackages": special_packages,
            "formattedText": "\\n".join(lines),
            "carrier": "unicom"
        }

        return summary

    @staticmethod
    def _fmt(mb_val):
        """将 MB 值格式化为人类可读的字符串"""
        if mb_val < 0:
            return "∞"
        if mb_val >= 1024:
            return f"{mb_val / 1024:.2f}GB"
        return f"{mb_val:.2f}MB"
