# -*- coding: utf-8 -*-
import sys

from .server import serve


def main() -> int:
    return serve()


if __name__ == "__main__":
    sys.exit(main())
