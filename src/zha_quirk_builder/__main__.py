from multiprocessing import freeze_support

from zha_quirk_builder.app import main

if __name__ == "__main__":
    freeze_support()
    raise SystemExit(main())
