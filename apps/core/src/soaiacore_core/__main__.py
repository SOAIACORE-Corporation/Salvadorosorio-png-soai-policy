from __future__ import annotations

import uvicorn


def main() -> None:
    uvicorn.run(
        "soaiacore_core.main:app",
        host="0.0.0.0",
        port=8000,
        access_log=True,
    )


if __name__ == "__main__":
    main()
