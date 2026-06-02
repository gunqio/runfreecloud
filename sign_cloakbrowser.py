import os, re, logging, random, base64, json, math, time
from pathlib import Path
from datetime import datetime, timedelta
import ddddocr

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

EMAIL    = os.environ["EMAIL"]
PASSWORD = os.environ["PASSWORD"]
BASE_URL     = "https://run.freecloud.ltd"
LOGIN_URL    = f"{BASE_URL}/login"
SERVICE_PAGE = f"{BASE_URL}/service?groupid=305"
SIGN_PAGE    = f"{BASE_URL}/addons?_plugin=5&controller=index&action=index"

# 代理：Xray 本地 SOCKS5
PROXY_SERVER = "socks5://127.0.0.1:10808"

SCREENSHOT_DIR = Path("./screenshots")
SCREENSHOT_DIR.mkdir(exist_ok=True)

# ---------- WxPusher 推送 ----------
WXPUSHER_TOKEN = os.environ.get("WXPUSHER_TOKEN", "")
WXPUSHER_UID   = os.environ.get("WXPUSHER_UID", "")

def wxpush(content: str):
    if not WXPUSHER_TOKEN or not WXPUSHER_UID:
        log.warning("📨 WXPUSHER_TOKEN 或 WXPUSHER_UID 未配置，跳过推送")
        return
    import urllib.request
    payload = json.dumps({
        "appToken": WXPUSHER_TOKEN,
        "content":  content,
        "contentType": 1,
        "uids": [WXPUSHER_UID],
    }).encode()
    try:
        req = urllib.request.Request(
            "https://wxpusher.zjiecode.com/api/send/message",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            result = json.loads(resp.read())
            if result.get("success"):
                log.info("📨 WxPusher 推送成功")
            else:
                log.warning(f"📨 WxPusher 推送失败: {result}")
    except Exception as e:
        log.warning(f"📨 WxPusher 推送异常: {e}")

ocr = ddddocr.DdddOcr(beta=True, show_ad=False)

# ---------- 工具函数 ----------
def take_screenshot(page, name):
    try:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = str(SCREENSHOT_DIR / f"{ts}_{name}.png")
        page.screenshot(path=path, full_page=False)
        log.info(f"📸 截图: {path}")
    except Exception as e:
        log.warning(f"截图失败: {e}")

def get_text(page) -> str:
    try:
        return page.inner_text("body") or ""
    except:
        return ""

def human_delay(min_s=0.3, max_s=0.8):
    time.sleep(random.uniform(min_s, max_s))

def wait_for_url_contains(page, keyword, timeout=10) -> bool:
    try:
        page.wait_for_url(f"**{keyword}**", timeout=timeout * 1000)
        return True
    except:
        return keyword in page.url

def js_click(page, selector, desc="") -> bool:
    try:
        result = page.evaluate(f"""() => {{
            var el = document.querySelector('{selector}');
            if (el) {{ el.click(); return true; }}
            return false;
        }}""")
        if result:
            log.info(f"JS 点击成功: {desc or selector}")
            return True
    except Exception as e:
        log.warning(f"JS 点击失败 [{desc}]: {e}")
    return False

def click_layui_ok(page, desc="确定") -> bool:
    """layui 弹窗确定是 <a class='layui-layer-btn0'>，不是 <button>"""
    result = page.evaluate("""() => {
        var a = document.querySelector('a.layui-layer-btn0');
        if (a) { a.click(); return 'layui-a'; }
        var btns = document.querySelectorAll('button');
        for (var b of btns) {
            if (b.innerText.trim() === '确定' && b.offsetParent !== null) {
                b.click(); return 'button';
            }
        }
        return null;
    }""")
    log.info(f"点击{desc}: {result}")
    return bool(result)

def read_expiry_from_service_page(page):
    result = page.evaluate("""() => {
        var tables = document.querySelectorAll('table');
        for (var tbl of tables) {
            var headers = tbl.querySelectorAll('th');
            var colIdx = -1;
            for (var i = 0; i < headers.length; i++) {
                if (headers[i].innerText.indexOf('到期') !== -1) { colIdx = i; break; }
            }
            if (colIdx >= 0) {
                var rows = tbl.querySelectorAll('tbody tr');
                for (var row of rows) {
                    var tds = row.querySelectorAll('td');
                    if (tds[colIdx]) {
                        var t = tds[colIdx].innerText.trim();
                        var m = t.match(/20\\d\\d-\\d{2}-\\d{2}/);
                        if (m) return m[0];
                    }
                }
            }
        }
        var rows = document.querySelectorAll('tr');
        for (var row of rows) {
            var rowText = row.innerText || '';
            if (rowText.indexOf('已激活') !== -1 || rowText.indexOf('Active') !== -1) {
                var m = rowText.match(/20\\d\\d-\\d{2}-\\d{2}/);
                if (m) return m[0];
            }
        }
        return null;
    }""")
    return str(result) if result else None

# ---------- Cloudflare 等待 ----------
def is_cf_blocked(page) -> bool:
    try:
        body = get_text(page).lower()
        return "verify you are human" in body or ("cloudflare" in body and "security" in body)
    except:
        return False

def wait_cf_pass(page, timeout=45) -> bool:
    log.info("等待 Cloudflare 验证自动通过...")
    for i in range(timeout):
        if not is_cf_blocked(page):
            log.info(f"✅ Cloudflare 验证通过（{i}s）")
            return True
        if i % 5 == 0 and i > 0:
            log.info(f"  CF 等待中... {i}s")
        time.sleep(1)
    log.error(f"Cloudflare 验证超时（{timeout}s）")
    return False

def navigate(page, url, timeout=45) -> bool:
    log.info(f"导航到: {url}")
    try:
        page.goto(url, timeout=30000, wait_until="domcontentloaded")
    except Exception as e:
        log.warning(f"goto 超时/异常: {e}，继续等待...")

    if not is_cf_blocked(page):
        return True

    if wait_cf_pass(page, timeout=timeout):
        return True

    # 刷新一次再等
    log.info("CF 未过，刷新重试...")
    try:
        page.reload(wait_until="domcontentloaded", timeout=30000)
    except:
        pass
    return wait_cf_pass(page, timeout=30)

# ---------- 验证码 ----------
def fill_captcha(page) -> str:
    for _ in range(3):
        cap_img = None
        try:
            loc = page.locator("#allow_login_email_captcha").first
            if loc.is_visible(timeout=3000):
                cap_img = loc
        except:
            pass
        if cap_img is None:
            try:
                loc = page.locator("img[alt='验证码']").first
                if loc.is_visible(timeout=3000):
                    cap_img = loc
            except:
                pass
        if cap_img:
            src = cap_img.get_attribute("src") or ""
            if src.startswith("data:image"):
                b64 = src.split(",", 1)[1]
                img_bytes = base64.b64decode(b64)
                raw = ocr.classification(img_bytes)
                code = re.sub(r'[^0-9]', '', raw)
                log.info(f"识别验证码: {code}")
                page.evaluate(f"""
                    (function() {{
                        var input =
                            document.querySelector('#captcha_allow_login_email_captcha') ||
                            document.querySelector('input[name="captcha"]') ||
                            document.querySelector('input[placeholder*="验证码"]');
                        if (input) {{
                            input.focus();
                            input.value = '{code}';
                            input.dispatchEvent(new Event('input', {{bubbles:true}}));
                            input.dispatchEvent(new Event('change', {{bubbles:true}}));
                        }}
                    }})()
                """)
                return code
        time.sleep(1)
    return ""

# ---------- 登录 ----------
def login(page, max_retries=3) -> bool:
    for attempt in range(1, max_retries + 1):
        log.info(f"登录 {attempt}/{max_retries}")
        if not navigate(page, LOGIN_URL):
            log.error("CF 验证失败，重试登录")
            continue

        try:
            page.wait_for_selector(
                'input[name="email"], input[placeholder="请输入邮箱地址"]',
                timeout=10000
            )
        except:
            log.warning("找不到邮箱输入框，重试")
            take_screenshot(page, f"login_fail_{attempt}")
            continue

        email_el = page.locator('input[name="email"]').first
        email_el.click()
        email_el.fill("")
        email_el.type(EMAIL, delay=random.randint(50, 120))
        human_delay()

        pass_el = page.locator('input[name="password"]').first
        pass_el.click()
        pass_el.fill("")
        pass_el.type(PASSWORD, delay=random.randint(50, 120))
        human_delay()

        captcha = fill_captcha(page)
        if not captcha:
            log.warning("验证码识别失败，重试")
            continue

        try:
            page.locator("button.btn.btn-primary").first.click()
        except:
            page.get_by_role("button", name="登录").click()
        log.info("已点击登录，检查跳转...")

        if wait_for_url_contains(page, "/clientarea", 10):
            log.info("✅ 登录成功")
            take_screenshot(page, "02_login_success")
            return True

        log.warning("登录后未跳转，重试")
        take_screenshot(page, f"login_no_redirect_{attempt}")

    return False

# ---------- 签到 ----------
def sign(page):
    log.info("前往签到页...")
    if not navigate(page, SIGN_PAGE):
        log.warning("签到页 CF 验证失败")
        return None

    for _ in range(10):
        body = get_text(page)
        if "我要签到" in body or "已签到" in body or "今日已" in body:
            break
        time.sleep(1)

    body = get_text(page)
    if "已签到" in body or "今日已" in body:
        log.info("今日已签到")
        take_screenshot(page, "02_already_signed")
        bal = re.search(r'账户余额剩余\s*([\d.]+)\s*积分', body)
        return bal.group(1) if bal else None

    if "我要签到" not in body:
        log.warning(f"未找到签到按钮, 片段: {body[:200]}")
        take_screenshot(page, "02_sign_check")
        return None

    page.get_by_role("button", name="我要签到").click()
    log.info("已点击'我要签到'")
    time.sleep(1.5)

    body = get_text(page)
    match = re.search(r'请计算[：:]\s*(\d+)\s*([+\-*/])\s*(\d+)', body)
    if match:
        a, op, b = int(match[1]), match[2], int(match[3])
        if   op == '+': result = a + b
        elif op == '-': result = a - b
        elif op == '*': result = a * b
        elif op == '/': result = a / b if b != 0 else 0
        else:           result = 0
        result_str = (
            str(int(result)) if result == int(result)
            else f"{math.floor(result * 100 + 0.5) / 100:.2f}".rstrip("0").rstrip(".")
        )
        log.info(f"数学题: {a} {op} {b} = {result_str}")

        ans_el = page.locator('input[placeholder="请输入答案"]').first
        ans_el.click()
        ans_el.type(result_str, delay=80)
        page.get_by_role("button", name="验证答案").click()
        log.info("已点击验证答案，等待弹窗...")
        time.sleep(2)

        # 弹窗1：验证成功 → 点确定
        for _ in range(12):
            body = get_text(page)
            if "验证成功" in body or "继续签到" in body:
                log.info("检测到验证成功弹窗，点击确定...")
                click_layui_ok(page, "验证弹窗确定")
                time.sleep(1.5)
                break
            time.sleep(0.5)

        # 弹窗2：签到成功 → 点确定
        for _ in range(12):
            body = get_text(page)
            if "签到成功" in body:
                log.info("检测到签到成功弹窗，点击确定...")
                click_layui_ok(page, "签到成功确定")
                time.sleep(1.5)
                break
            time.sleep(0.5)

    log.info("签到流程完成")
    take_screenshot(page, "03_sign_complete")

    # 刷新签到页，读取最新积分
    time.sleep(1)
    page.goto(SIGN_PAGE, wait_until="domcontentloaded", timeout=30000)
    time.sleep(2)
    body = get_text(page)
    bal = re.search(r'账户余额剩余\s*([\d.]+)\s*积分', body)
    balance = bal.group(1) if bal else None
    log.info(f"签到后最新积分: {balance}")
    return balance

# ---------- 续费 ----------
def renew(page):
    log.info("检查续费...")
    page.goto(SERVICE_PAGE, wait_until="domcontentloaded", timeout=30000)
    time.sleep(3)
    take_screenshot(page, "03b_service_page")

    expiry_str = read_expiry_from_service_page(page)
    if not expiry_str:
        body = get_text(page)
        m = re.search(r'到期时间[：:\s]*(\d{4}-\d{2}-\d{2})', body)
        if not m:
            m = re.search(r'(\d{4}-\d{2}-\d{2})', body)
        expiry_str = m.group(1) if m else None

    if not expiry_str:
        log.info("未找到到期日")
        return False, None, None

    expiry = datetime.strptime(expiry_str, "%Y-%m-%d")
    remain = (expiry - datetime.now()).days
    log.info(f"到期: {expiry_str}，剩余 {remain} 天")

    # 到期前两天才续费（与原 runfreecloud 逻辑一致）
    if remain > 2:
        log.info(f"距到期还有 {remain} 天，暂不续费")
        return False, expiry_str, remain

    log.info(f"剩余 {remain} 天，开始续费...")

    # 第1步：勾选 checkbox
    js_click(page, "input#customCheck", "全选checkbox") or \
        js_click(page, "input.custom-control-input", "行checkbox")
    time.sleep(1)
    take_screenshot(page, "04a_checked")

    # 第2步：点续费按钮
    if not (js_click(page, "button#readBtn", "续费按钮") or
            js_click(page, "button.btn-outline-primary", "续费按钮outline")):
        log.warning("找不到续费按钮，放弃")
        return False, expiry_str, remain
    time.sleep(3)
    take_screenshot(page, "04b_after_renew_click")

    # 第3步：批量续费页 → 立即续费
    js_click(page, "button.xfSubmit", "立即续费") or \
        js_click(page, "button[type='submit']", "立即续费 submit")
    time.sleep(3)
    take_screenshot(page, "04c_after_xfsubmit")

    # 第4步：账单页 → 立即支付
    js_click(page, "button#payamount", "立即支付") or \
        js_click(page, "button.btnWidth", "立即支付 btnWidth")
    time.sleep(3)
    take_screenshot(page, "04d_after_payamount")

    # 第5步：弹窗 → 立即支付
    if not js_click(page, "button.pay-now", "弹窗立即支付"):
        try:
            page.evaluate("payNow();")
            log.info("直接调用 payNow()")
        except Exception as e:
            log.warning(f"payNow() 失败: {e}")
    time.sleep(3)
    take_screenshot(page, "04e_after_paynow")

    body = get_text(page)
    if "success" in body.lower() or "成功" in body or "/service" in page.url:
        log.info("✅ 续费完成")
        take_screenshot(page, "04f_renew_complete")
        return True, expiry_str, remain
    else:
        log.warning("续费流程可能未完成，请查看截图")
        return False, expiry_str, remain

# ---------- 主流程 ----------
def main():
    from cloakbrowser import launch

    log.info("启动 CloakBrowser（源码级指纹伪装）...")
    # geoip=True：根据代理 IP 自动匹配时区/语言，消除指纹矛盾
    browser = launch(
        headless=False,
        humanize=True,
        proxy=PROXY_SERVER,
        geoip=True,
    )
    page = browser.new_page()

    try:
        if not login(page):
            wxpush("❌ 登录失败，请检查账号密码或网络")
            return

        balance = sign(page)
        renewed, expiry_str, remain = renew(page)

        # 续费后重新读最新到期日
        if renewed:
            try:
                page.goto(SERVICE_PAGE, wait_until="domcontentloaded", timeout=30000)
                time.sleep(3)
                new_expiry = read_expiry_from_service_page(page)
                if new_expiry:
                    expiry_str = new_expiry
                    log.info(f"续费后最新到期日: {expiry_str}")
            except Exception as e:
                log.warning(f"续费后读取到期日失败: {e}")

        # 积分为 None 时再读一次
        if balance is None:
            try:
                page.goto(SIGN_PAGE, wait_until="domcontentloaded", timeout=30000)
                time.sleep(2)
                body = get_text(page)
                bal = re.search(r'账户余额剩余\s*([\d.]+)\s*积分', body)
                if bal:
                    balance = bal.group(1)
            except Exception as e:
                log.warning(f"读取积分失败: {e}")

        lines = ["✅ 签到成功"]
        if balance is not None:
            lines.append(f"账户余额剩余 {balance} 积分")
        if expiry_str:
            lines.append(f"到期时间 {expiry_str}")
            if renewed:
                lines.append("✅ 已自动续期")
            else:
                renew_date = (
                    datetime.strptime(expiry_str, "%Y-%m-%d") - timedelta(days=2)
                ).strftime("%Y-%m-%d")
                lines.append(f"不用续期，等到 {renew_date} 再续期")
        wxpush("\n".join(lines))

    except Exception as e:
        log.exception(e)
        take_screenshot(page, "99_error")
        wxpush(f"❌ Runfreecloud 任务异常: {e}")
    finally:
        time.sleep(5)
        browser.close()
        log.info("任务结束")

if __name__ == "__main__":
    main()
