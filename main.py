"""
微博爬虫 - 程序入口
串联全流程：
    配置加载 → 用户读取 → 浏览器初始化 → Cookie 管理
    → 遍历用户爬取 → 结果汇总 → Excel 输出 → 资源清理
"""

import shutil
import sys
import traceback
from datetime import datetime
from pathlib import Path

# --- 确保 settings.py 存在（首次运行自动从模板创建）---
_SETTINGS_FILE = Path(__file__).resolve().parent / "config" / "settings.py"
_SETTINGS_TEMPLATE = Path(__file__).resolve().parent / "config" / "settings.example.py"
if not _SETTINGS_FILE.exists() and _SETTINGS_TEMPLATE.exists():
    shutil.copy(_SETTINGS_TEMPLATE, _SETTINGS_FILE)
    print(f"[初始化] 已从模板创建 {_SETTINGS_FILE}")

from loguru import logger

from config.settings import (
    LOG_DIR,
    LOG_LEVEL,
    LOG_FORMAT,
    LOG_ROTATION,
    LOG_RETENTION,
    OUTPUT_DIR,
    COOKIE_DIR,
    DOWNLOAD_DIR,
    RESULT_DIR,
    HEADLESS,
)
from utils.config_reader import read_users, update_last_crawl_time, validate_user
from utils.excel_writer import create_result_workbook, append_result_row, write_results
from utils.anti_ban import human_like_delay
from core.browser import BrowserManager
from core.cookie_manager import CookieManager
from core.crawler import WeiboCrawler


# ================================================================
# 初始化日志
# ================================================================
def setup_logging() -> None:
    """配置 loguru 日志（控制台 + 文件）"""
    # 移除默认 handler
    logger.remove()

    # 控制台输出（彩色）
    logger.add(
        sys.stdout,
        format=LOG_FORMAT,
        level=LOG_LEVEL,
        colorize=True,
    )

    # 文件输出（按天轮转）
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_file = LOG_DIR / "crawler_{time:YYYY-MM-DD}.log"
    logger.add(
        str(log_file),
        format=LOG_FORMAT,
        level=LOG_LEVEL,
        rotation=LOG_ROTATION,
        retention=LOG_RETENTION,
        encoding="utf-8",
    )

    logger.info("=" * 60)
    logger.info("微博爬虫启动")
    logger.info("=" * 60)


# ================================================================
# 初始化输出目录
# ================================================================
def ensure_output_dirs() -> None:
    """确保所有输出目录存在"""
    for d in (OUTPUT_DIR, COOKIE_DIR, DOWNLOAD_DIR, RESULT_DIR):
        d.mkdir(parents=True, exist_ok=True)
    logger.debug("📁 输出目录就绪")


# ================================================================
# 主流程
# ================================================================
def main() -> None:
    """主函数"""
    # --- 初始化 ---
    setup_logging()
    ensure_output_dirs()

    # --- 1. 读取 & 校验用户配置 ---
    try:
        users = read_users()
    except FileNotFoundError as e:
        logger.error(f"❌ 配置文件缺失: {e}")
        logger.error("请在 config/users.csv 中添加待爬取用户（参考项目文档格式）")
        return
    except ValueError as e:
        logger.error(f"❌ 配置文件格式错误: {e}")
        return

    if not users:
        logger.warning("⚠️ 用户列表为空，请检查 config/users.csv")
        return

    # 过滤校验失败的用户
    valid_users = []
    for user in users:
        if validate_user(user):
            valid_users.append(user)
        else:
            logger.warning(f"⏭ 跳过用户 {user.get('user_id', '?')}（校验不通过）")

    if not valid_users:
        logger.error("❌ 所有用户配置校验均失败，无法继续")
        return

    logger.info(f"📋 待爬取用户: {len(valid_users)} 个")

    # --- 2. 启动浏览器 ---
    bm = BrowserManager()
    try:
        bm.start(headless=HEADLESS)
    except Exception as e:
        logger.error(f"❌ 浏览器启动失败: {e}")
        return

    all_results = []  # 汇总所有用户结果

    # --- 预创建 Excel（逐条写入，无需等全部爬完）---
    wb, ws, output_path = create_result_workbook()
    row_state = {"idx": 2}  # 数据行从第 2 行开始（第 1 行是表头）

    try:
        # --- 3. Cookie 管理 ---
        cm = CookieManager(bm)
        cookies_ok = cm.is_cookie_valid()

        if not cookies_ok:
            try:
                cm.ensure_valid_cookie()
            except RuntimeError as e:
                logger.error(f"❌ 登录失败: {e}")
                return

        # 获取 Cookie 列表（供下载器使用）
        cookies = bm.context.cookies()
        logger.info(f"🍪 已准备 {len(cookies)} 条 Cookie 供下载器使用")

        # --- 4. 遍历用户 ---
        for idx, user in enumerate(valid_users, start=1):
            user_id = user["user_id"]
            username = user.get("username", "")
            start_date = user["start_date"]
            end_date = user.get("end_date")  # 可能为 None

            logger.info("─" * 50)
            logger.info(
                f"📌 [{idx}/{len(valid_users)}] 开始处理用户: {username} ({user_id})"
            )
            logger.info(f"   日期范围: {start_date} ~ {end_date or '最新'}")

            # 用户之间的人类行为延时
            if idx > 1:
                human_like_delay(5, 15)

            # 创建新页面（每个用户独立页面，避免状态干扰）
            page = bm.new_page()

            try:
                # 逐条写入回调（闭包捕获 user_id/ws/row_state/output_path）
                def on_post(result: dict) -> None:
                    append_result_row(ws, result, row_state["idx"])
                    row_state["idx"] += 1
                    wb.save(str(output_path))
                    update_last_crawl_time(
                        user_id, datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    )

                crawler = WeiboCrawler(
                    page=page,
                    user_id=user_id,
                    username=username,
                    start_date=start_date,
                    end_date=end_date,
                    cookies=cookies,
                    on_post_processed=on_post,
                )
                user_results = crawler.crawl()
                all_results.extend(user_results)
                logger.info(
                    f"✅ 用户 {username} 完成，共 {len(user_results)} 条微博"
                )
            except Exception as e:
                logger.error(f"❌ 用户 {username} 爬取异常: {e}")
                logger.debug(traceback.format_exc())
                # 记录一条失败信息（同时写入 Excel）
                fail_record = {
                    "用户id": user_id,
                    "用户名": username,
                    "微博发布时间": "",
                    "微博类型": "",
                    "文案": "",
                    "爬虫结果": f"失败: {str(e)[:100]}",
                    "微博url": "",
                    "图片数量": 0,
                    "Live图数量": 0,
                    "视频数量": 0,
                    "图片下载数量": 0,
                    "Live图下载数量": 0,
                    "视频下载数量": 0,
                }
                all_results.append(fail_record)
                try:
                    append_result_row(ws, fail_record, row_state["idx"])
                    row_state["idx"] += 1
                    wb.save(str(output_path))
                except Exception:
                    pass
            finally:
                # 关闭当前用户页面
                if not page.is_closed():
                    page.close()

        # --- 5. 收尾 ---
        if all_results:
            output_path = write_results(all_results, output_path)
            logger.info(f"🎉 全部完成！结果文件: {output_path}（共 {len(all_results)} 条）")
        else:
            logger.warning("⚠️ 未收集到任何结果")

    except KeyboardInterrupt:
        logger.warning("⏹ 用户中断（Ctrl+C）")
        try:
            ws.auto_filter.ref = ws.dimensions
            wb.save(str(output_path))
            logger.info(f"💾 已保存: {output_path}")
        except Exception as e:
            logger.error(f"❌ 保存失败: {e}")

    except Exception as e:
        logger.error(f"❌ 运行时异常: {e}")
        logger.debug(traceback.format_exc())
        try:
            ws.auto_filter.ref = ws.dimensions
            wb.save(str(output_path))
            logger.info(f"💾 已保存: {output_path}")
        except Exception as ex:
            logger.error(f"❌ 保存失败: {ex}")

    finally:
        # --- 6. 资源清理 ---
        logger.info("🧹 正在清理资源...")
        bm.stop()
        logger.info("👋 微博爬虫已退出")


if __name__ == "__main__":
    main()