import argparse
import sys

from openemail.app import create_app


def main() -> int:
    try:
        parser = argparse.ArgumentParser(description="OpenEmail - Linux桌面邮件客户端")
        parser.add_argument(
            "--theme", choices=["light", "dark", "system"], help="覆盖主题设置"
        )
        parser.add_argument("--debug", action="store_true", help="启用调试模式")
        args = parser.parse_args()

        app, window = create_app()

        if args.theme:
            from openemail.config import settings

            settings.theme = args.theme
            from openemail.app import apply_theme

            apply_theme()

        window.show()

        ret = app.exec()

        # 停止后台任务管理器
        from openemail.background.background_manager import background_task_manager

        background_task_manager.stop()

        # 关闭语义搜索系统
        from openemail.search.semantic_search import shutdown_semantic_search

        shutdown_semantic_search()

        from openemail.storage.database import db

        db.close()

        return ret

    except Exception as e:
        import traceback

        print(f"应用程序启动失败: {e}")
        print(traceback.format_exc())
        return 1


if __name__ == "__main__":
    sys.exit(main())
