from __future__ import annotations

import os
import shutil
import threading
from typing import Dict, Optional, Tuple

import sublime
import sublime_plugin
from LSP.plugin import AbstractPlugin, register_plugin, unregister_plugin

from . import download

SETTINGS_FILE = "LSP-bhl.sublime-settings"


def _custom_executable() -> str:
    """User-provided `executablePath`; takes precedence over the downloaded release."""
    return sublime.load_settings(SETTINGS_FILE).get("executablePath") or ""


def _installs_root() -> str:
    return os.path.join(Bhl.storage_path(), "BHL", "lsp-releases")


def _status(message: str) -> None:
    sublime.set_timeout(lambda: sublime.status_message("BHL: " + message), 0)


_offered_download = False


def _install_in_background(release) -> None:
    threading.Thread(target=_install, args=(release,), daemon=True).start()


def _install(release) -> None:
    version = download.release_version(release["tag_name"])
    try:
        download.install_release(release, _installs_root(), _status)
    except Exception as e:
        sublime.set_timeout(lambda: sublime.error_message(f"BHL: failed to install {version}: {e}"), 0)
        return
    sublime.set_timeout(lambda: sublime.message_dialog(
        f"Installed BHL {version}.\n\nReopen the .bhl file or run "
        "\"LSP: Restart Server\" to start it. Ignored while executablePath is set."
    ), 0)


def _offer_download_once() -> None:
    """Asks (once per Sublime session) whether to download the latest release."""
    global _offered_download
    if _offered_download or download.current_platform_suffix() is None:
        return
    _offered_download = True
    threading.Thread(target=_offer_download, daemon=True).start()


def _offer_download() -> None:
    try:
        releases = download.fetch_releases()
    except Exception as e:
        print(f"BHL: failed to fetch releases: {e}")
        return
    if not releases:
        return
    release = releases[0]
    version = download.release_version(release["tag_name"])

    def ask() -> None:
        if sublime.ok_cancel_dialog(
            f"BHL language server is not installed.\n\nDownload BHL LSP {version} from GitHub?",
            "Download",
        ):
            _install_in_background(release)

    sublime.set_timeout(ask, 0)


class Bhl(AbstractPlugin):

    @classmethod
    def name(cls) -> str:
        return "bhl"

    @classmethod
    def configuration(cls) -> Tuple[sublime.Settings, str]:
        return sublime.load_settings(SETTINGS_FILE), "Packages/BHL-Sublime/LSP-bhl.sublime-settings"

    @classmethod
    def additional_variables(cls) -> Dict[str, str]:
        settings = sublime.load_settings(SETTINGS_FILE)
        executable = _custom_executable() or download.installed_binary(_installs_root()) or "bhl"
        force_rebuild = bool(settings.get("forceRebuild", False))
        rebuild = "1" if force_rebuild else ""
        return {
            "bhl": executable,
            "bhl_rebuild": rebuild,
            "bhl_silent": rebuild,
        }

    @classmethod
    def can_start(
        cls,
        window: sublime.Window,
        initiating_view: sublime.View,
        workspace_folders,
        configuration,
    ) -> Optional[str]:
        executable = _custom_executable()
        if executable:
            if not os.path.isfile(executable):
                return (
                    f'BHL executable not found at "{executable}". '
                    "Update the executablePath setting."
                )
        elif not download.installed_binary(_installs_root()) and not shutil.which("bhl"):
            _offer_download_once()
            return (
                "No BHL LSP binary available. Run \"BHL: Manage LSP Versions\" "
                "or set the executablePath setting."
            )
        return None


class BhlManageLspVersionsCommand(sublime_plugin.WindowCommand):
    """Pick a BHL LSP release to download, or remove the downloaded one."""

    def run(self) -> None:
        _status("fetching releases…")
        threading.Thread(target=self._fetch, daemon=True).start()

    def _fetch(self) -> None:
        try:
            releases = download.fetch_releases()
        except Exception as e:
            sublime.set_timeout(lambda: sublime.error_message(f"BHL: failed to fetch releases: {e}"), 0)
            return
        sublime.set_timeout(lambda: self._show(releases), 0)

    def _show(self, releases) -> None:
        installed = download.version_from_binary_path(download.installed_binary(_installs_root()))
        items = []
        actions = []
        if installed:
            items.append(["Remove downloaded release", f"currently {installed}"])
            actions.append(None)
        for release in releases:
            version = download.release_version(release["tag_name"])
            tags = []
            if version == installed:
                tags.append("installed")
            if release.get("prerelease"):
                tags.append("pre-release")
            published = str(release.get("published_at") or "")[:10]
            items.append([version, " · ".join(filter(None, [published] + tags))])
            actions.append(release)

        def on_select(index: int) -> None:
            if index < 0:
                return
            release = actions[index]
            if release is None:
                download.remove_installs(_installs_root())
                sublime.status_message("BHL: downloaded release removed")
            else:
                _install_in_background(release)

        placeholder = f"Currently installed: {installed}" if installed else "Select a version to install"
        self.window.show_quick_panel(items, on_select, placeholder=placeholder)


def plugin_loaded() -> None:
    register_plugin(Bhl)
    _register_debug_adapter()


def _register_debug_adapter(attempts: int = 0) -> None:
    try:
        from Debugger.modules import dap
    except ImportError:
        print(f"BHL: Debugger not available (attempt {attempts})")
        if attempts < 20:
            sublime.set_timeout(lambda: _register_debug_adapter(attempts + 1), 500)
        return

    print(f"BHL: registering debug adapter (attempt {attempts})")

    class BhlDebugAdapter(dap.AdapterConfiguration):
        type = "bhl"

        @property
        def configuration_snippets(self):
            return [
                {
                    "label": "BHL: Attach to Debug Server",
                    "description": "Attach to a running BHL debug server (e.g. inside Unity)",
                    "body": {
                        "type": "bhl",
                        "request": "attach",
                        "name": "Attach to BHL",
                        "host": "localhost",
                        "port": 7777,
                        "timeout": 30,
                    },
                }
            ]

        # Debugger <= 0.11.6 passes `log`, newer master passes `console`; accept either.
        async def start(self, *args, configuration=None, **kwargs):
            logger = kwargs.get("console") or kwargs.get("log")
            if configuration is None:
                configuration = args[-1]
                logger = logger or (args[0] if len(args) > 1 else None)
            host = configuration.get("host") or "localhost"
            port = configuration["port"]
            timeout = configuration.get("timeout") or 30
            if logger is not None:
                logger.info(f"Connecting to BHL debug server on {host}:{port}")
            return dap.SocketTransport(host=host, port=port, timeout=timeout)

    print(f"BHL: debug adapter registered")


def plugin_unloaded() -> None:
    unregister_plugin(Bhl)
