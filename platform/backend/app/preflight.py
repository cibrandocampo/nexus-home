"""Start-up check run by the image's entrypoint before migrations: exits with a clear message."""

import sys

from app.core.config import get_settings, production_problems


def main() -> int:
    problems = production_problems(get_settings())
    for problem in problems:
        print(f"Configuration error: {problem}.", file=sys.stderr)
    if problems:
        print(
            "Refusing to start in production. Set a long random SECRET_KEY "
            "(for example: openssl rand -hex 32) and a new DEVICE_TOKEN_KEY "
            "(openssl rand -base64 32 | tr '+/' '-_'); see docs/configuration.md.",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":  # pragma: no cover - exercised through main()
    sys.exit(main())
