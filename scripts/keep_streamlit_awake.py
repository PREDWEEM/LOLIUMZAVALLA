from __future__ import annotations

import os
import re
import sys
import time
from pathlib import Path

from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError, sync_playwright


APP_URL = os.environ.get(
    "APP_URL",
    "https://f8d5dqg4evu9tvthrrffkl.streamlit.app/",
).strip()
ARTIFACT_DIR = Path(os.environ.get("KEEPALIVE_ARTIFACT_DIR", "keepalive-artifacts"))
APP_READY_SELECTOR = '[data-testid="stAppViewContainer"]'


def _body_text(page: Page) -> str:
    try:
        return page.locator("body").inner_text(timeout=10_000)
    except Exception:
        return ""


def _save_diagnostics(page: Page, label: str) -> None:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    try:
        page.screenshot(
            path=str(ARTIFACT_DIR / f"{label}.png"),
            full_page=True,
            timeout=20_000,
        )
    except Exception as exc:
        print(f"No se pudo guardar la captura: {exc}")

    try:
        (ARTIFACT_DIR / f"{label}.html").write_text(
            page.content(),
            encoding="utf-8",
        )
    except Exception as exc:
        print(f"No se pudo guardar el HTML: {exc}")


def _wake_sleeping_app(page: Page) -> bool:
    body = _body_text(page)
    sleeping = bool(
        re.search(
            r"gone to sleep|app has gone to sleep|zzz|wake (?:this|the) app",
            body,
            flags=re.IGNORECASE,
        )
    )
    if not sleeping:
        return False

    print("Se detectó la pantalla de hibernación de Streamlit.")
    candidates = (
        page.get_by_role(
            "button",
            name=re.compile(r"get this app back up|wake|yes", re.IGNORECASE),
        ),
        page.get_by_role(
            "link",
            name=re.compile(r"get this app back up|wake|yes", re.IGNORECASE),
        ),
        page.get_by_text(
            re.compile(r"yes,? get this app back up|wake (?:this|the) app", re.IGNORECASE)
        ),
    )

    for locator in candidates:
        try:
            if locator.count() > 0 and locator.first.is_visible(timeout=2_000):
                locator.first.click(timeout=10_000)
                print("Se solicitó reactivar la aplicación.")
                return True
        except Exception:
            continue

    print("La pantalla de hibernación fue detectada, pero no se encontró el control de reactivación.")
    return False


def _wait_until_ready(page: Page, timeout_seconds: int = 180) -> bool:
    deadline = time.monotonic() + timeout_seconds
    last_url = ""

    while time.monotonic() < deadline:
        current_url = page.url
        if current_url != last_url:
            print(f"URL actual: {current_url}")
            last_url = current_url

        _wake_sleeping_app(page)

        try:
            app = page.locator(APP_READY_SELECTOR)
            if app.count() > 0 and app.first.is_visible(timeout=2_000):
                body = _body_text(page)
                if not re.search(
                    r"gone to sleep|app has gone to sleep|zzz",
                    body,
                    flags=re.IGNORECASE,
                ):
                    return True
        except Exception:
            pass

        page.wait_for_timeout(5_000)

    return False


def main() -> int:
    if not APP_URL.startswith(("https://", "http://")):
        print(f"APP_URL inválida: {APP_URL}", file=sys.stderr)
        return 2

    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Abriendo la aplicación con Chromium: {APP_URL}")

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            headless=True,
            args=["--disable-dev-shm-usage", "--no-sandbox"],
        )
        context = browser.new_context(
            viewport={"width": 1440, "height": 1000},
            locale="es-AR",
            user_agent=(
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
            ),
        )
        page = context.new_page()
        page.set_default_timeout(20_000)

        page.on(
            "console",
            lambda message: print(f"[browser:{message.type}] {message.text}"),
        )
        page.on(
            "pageerror",
            lambda error: print(f"[browser:error] {error}"),
        )

        try:
            response = page.goto(
                APP_URL,
                wait_until="domcontentloaded",
                timeout=120_000,
            )
            if response is not None:
                print(f"Respuesta inicial del navegador: HTTP {response.status}")

            ready = _wait_until_ready(page)
            if not ready:
                print("La interfaz de Streamlit no quedó disponible dentro del tiempo esperado.")
                print(f"URL final: {page.url}")
                print("Contenido visible (primeros 1500 caracteres):")
                print(_body_text(page)[:1500])
                _save_diagnostics(page, "keepalive-error")
                return 1

            print("La interfaz de Streamlit está activa y el navegador abrió la sesión de la app.")
            print("Manteniendo la conexión abierta durante 45 segundos...")
            page.wait_for_timeout(45_000)
            _save_diagnostics(page, "keepalive-success")
            return 0

        except PlaywrightTimeoutError as exc:
            print(f"Tiempo de espera agotado: {exc}")
            _save_diagnostics(page, "keepalive-timeout")
            return 1
        except Exception as exc:
            print(f"Error inesperado: {exc}")
            _save_diagnostics(page, "keepalive-error")
            return 1
        finally:
            context.close()
            browser.close()


if __name__ == "__main__":
    raise SystemExit(main())
