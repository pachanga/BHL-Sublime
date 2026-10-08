from __future__ import annotations

import os
import re
import shutil
import threading
import traceback
from typing import Dict, Optional, Tuple

import sublime
import sublime_plugin
from LSP.plugin import AbstractPlugin, WorkspaceFolder, register_plugin, unregister_plugin

from . import download, project

SETTINGS_FILE = "LSP-bhl.sublime-settings"


def _custom_executable() -> str:
    """User-provided `executablePath`; takes precedence over the downloaded release."""
    return sublime.load_settings(SETTINGS_FILE).get("executablePath") or ""


def _installs_root() -> str:
    return os.path.join(Bhl.storage_path(), "BHL", "lsp-releases")


def _status(message: str) -> None:
    sublime.set_timeout(lambda: sublime.status_message("BHL: " + message), 0)


class _InstallProgress:
    """Status bar activity indicator with a text progress bar; safe to call from any thread."""

    WIDTH = 20

    def __init__(self) -> None:
        self._indicator: Optional[sublime.ActivityIndicator] = None
        self._lock = threading.Lock()
        self._stopped = False
        sublime.set_timeout(self._start, 0)

    def _start(self) -> None:
        with self._lock:
            if self._stopped:
                return
            window = sublime.active_window()
            if window:
                try:
                    self._indicator = sublime.ActivityIndicator(window, "BHL: starting…")
                    self._indicator.start()
                except Exception:
                    traceback.print_exc()
                    self._indicator = None

    def __call__(self, message: str) -> None:
        match = re.search(r"(\d+)%$", message)
        if match:
            filled = int(match.group(1)) * self.WIDTH // 100
            message = "{} [{}{}]".format(
                message, "█" * filled, "░" * (self.WIDTH - filled))
        # The plain status message is the reliable fallback; the indicator is a bonus.
        sublime.set_timeout(lambda: sublime.status_message("BHL: " + message), 0)
        sublime.set_timeout(lambda: self._set_label("BHL: " + message), 0)

    def _set_label(self, label: str) -> None:
        with self._lock:
            if self._indicator and not self._stopped:
                try:
                    self._indicator.label = label
                except Exception:
                    traceback.print_exc()

    def stop(self) -> None:
        sublime.set_timeout(self._stop, 0)

    def _stop(self) -> None:
        with self._lock:
            self._stopped = True
            if self._indicator:
                self._indicator.stop()
                self._indicator = None


# Window id -> project directory picked via "BHL: Select Project File"; lives until Sublime exits.
_selected_projects: Dict[int, str] = {}

_offered_download = False
# Installs share one directory per release, so two at once would clobber each other.
_install_lock = threading.Lock()


def _install_in_background(release) -> None:
    threading.Thread(target=_install, args=(release,), daemon=True).start()


def _install(release) -> None:
    version = download.release_version(release["tag_name"])
    progress = _InstallProgress()
    try:
        with _install_lock:
            download.install_release(release, _installs_root(), progress)
    except Exception as e:
        traceback.print_exc()
        sublime.set_timeout(lambda: sublime.error_message(f"BHL: failed to install {version}: {e}"), 0)
        return
    finally:
        progress.stop()
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
        traceback.print_exc()
        sublime.set_timeout(lambda: sublime.error_message(
            f"BHL: failed to check for LSP releases: {e}\n\n"
            "Run \"BHL: Manage LSP Versions\" to retry or set the executablePath setting."
        ), 0)
        return
    if not releases:
        sublime.set_timeout(lambda: sublime.error_message("BHL: no LSP releases found on GitHub."), 0)
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

    @classmethod
    def on_pre_start(
        cls,
        window: sublime.Window,
        initiating_view: sublime.View,
        workspace_folders,
        configuration,
    ) -> Optional[str]:
        """
        Pins the server root to the directory containing bhl.proj. The server only reads bhl.proj
        from the root of a workspace folder, so a parent folder or no folder at all would make it
        fall back to defaults and ignore the project settings.
        """
        proj_dir = _selected_projects.get(window.id())
        if proj_dir and not os.path.isfile(os.path.join(proj_dir, project.PROJECT_FILE)):
            del _selected_projects[window.id()]
            proj_dir = None
        if not proj_dir:
            proj_dir = project.resolve(initiating_view.file_name(), [f.path for f in workspace_folders])
        if not proj_dir:
            return None
        workspace_folders[:] = [WorkspaceFolder.from_path(proj_dir)]
        return proj_dir


class BhlSelectProjectFileCommand(sublime_plugin.WindowCommand):
    """Pick the bhl.proj the server should use for this window, overriding the automatic choice."""

    def run(self) -> None:
        view = self.window.active_view()
        file_name = view.file_name() if view else None
        candidates = []
        if file_name:
            nearest = project.find_upwards(os.path.dirname(file_name))
            if nearest:
                candidates.append(nearest)
        for found in project.find_in_folders(self.window.folders()):
            if found not in candidates:
                candidates.append(found)

        items = [[os.path.basename(c) or c, c] for c in candidates]
        items.append(["Browse…", "Choose a bhl.proj file"])
        automatic = self.window.id() in _selected_projects
        if automatic:
            items.append(["Automatic", "Forget the selection and detect the project again"])
        current = _selected_projects.get(self.window.id())

        def on_select(index: int) -> None:
            if index < 0:
                return
            if index < len(candidates):
                self._apply(candidates[index])
            elif index == len(candidates):
                sublime.open_dialog(
                    self._on_browse,
                    file_types=[("BHL project", ["proj"])],
                    directory=os.path.dirname(file_name) if file_name else None,
                )
            else:
                _selected_projects.pop(self.window.id(), None)
                self._restart()

        placeholder = f"Current: {current}" if current else "Select the BHL project"
        self.window.show_quick_panel(items, on_select, placeholder=placeholder)

    def _on_browse(self, path) -> None:
        if not path:
            return
        if os.path.basename(path) != project.PROJECT_FILE:
            sublime.error_message(f'BHL: expected a "{project.PROJECT_FILE}" file, got "{os.path.basename(path)}".')
            return
        self._apply(os.path.dirname(path))

    def _apply(self, proj_dir: str) -> None:
        _selected_projects[self.window.id()] = proj_dir
        self._restart()

    def _restart(self) -> None:
        view = self.window.active_view()
        if view:
            view.run_command("lsp_restart_server", {"config_name": Bhl.name()})
        sublime.status_message("BHL: project selection updated")


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
