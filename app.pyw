import sys


def _run():
    if "--helper" in sys.argv[1:]:
        from tunnelcrab.helper import run_helper

        run_helper(sys.argv)
        return
    from tunnelcrab.app_webview import main

    main()


if __name__ == "__main__":
    _run()
