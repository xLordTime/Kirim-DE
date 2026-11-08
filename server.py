#!/usr/bin/env python3
"""Kirim-DE: Einrichtung, geprüfte Updates und Datenbankimport (Python 3.11+)."""
import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time
import venv
from zipfile import ZipFile, ZIP_DEFLATED

ROOT = Path(__file__).resolve().parent
SERVICE = "kirim-de.service"
REPOSITORY = "https://github.com/xLordTime/Kirim-DE.git"


def run(*args, root=ROOT, capture=False, env=None):
    result = subprocess.run([str(arg) for arg in args], cwd=root, check=True,
        text=True, stdout=subprocess.PIPE if capture else None, env=env)
    return result.stdout.strip() if capture else ""


def ensure_env(root=ROOT):
    path = root / ".env"
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        return path
    with os.fdopen(fd, "wb") as stream:
        stream.write((root / ".env.example").read_bytes())
    print(".env wurde automatisch angelegt. Bitte DISCORD_TOKEN eintragen.")
    return path


def settings(root=ROOT):
    values = {}
    path = ensure_env(root)
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        if line.strip() and not line.lstrip().startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip().strip("\"'")
    values.update(os.environ)
    def resolve(value):
        path = Path(value).expanduser()
        return path if path.is_absolute() else root / path
    data = resolve(values.get("KIRIM_DATA_DIR") or "data")
    data.mkdir(parents=True, exist_ok=True)
    return {
        "data": data,
        "items": resolve(values["KIRIM_ITEMS_DB"]) if values.get("KIRIM_ITEMS_DB") else (
            root / "items.db" if (root / "items.db").is_file() else data / "items.db"),
        "decks": resolve(values["KIRIM_DECKS_DB"]) if values.get("KIRIM_DECKS_DB") else (
            root / "decks.db" if (root / "decks.db").is_file() else data / "decks.db"),
    }


def python_in(directory):
    return directory / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def active_python(root=ROOT):
    state = settings(root)["data"] / "runtime.json"
    if state.is_file():
        path = Path(json.loads(state.read_text())["python"])
    else:
        path = python_in(root / ".venv")
    if not path.is_file():
        raise RuntimeError("Python-Umgebung fehlt. Zuerst python3 server.py setup ausführen.")
    return path


@contextmanager
def maintenance_lock(root=ROOT):
    lock = settings(root)["data"] / ".maintenance.lock"
    try:
        lock.mkdir()
    except FileExistsError:
        raise RuntimeError(f"Eine Wartung läuft bereits ({lock}). Nach einem abgebrochenen Prozess den leeren Ordner manuell entfernen.")
    try:
        yield
    finally:
        lock.rmdir()


def install_dependencies(directory, source=ROOT):
    if not python_in(directory).is_file():
        venv.EnvBuilder(with_pip=True).create(directory)
    python = python_in(directory)
    run(python, "-m", "pip", "install", "--disable-pip-version-check", "-r", source / "requirements.txt", root=source)
    return python


def check_bot(python, source=ROOT, config_root=ROOT):
    config = settings(config_root)
    environment = os.environ.copy()
    environment.update(KIRIM_DATA_DIR=str(config["data"].resolve()),
        KIRIM_ITEMS_DB=str(config["items"].resolve()), KIRIM_DECKS_DB=str(config["decks"].resolve()),
        DISCORD_TOKEN="", KIRIM_SYNC_COMMANDS="false")
    flag = "--check" if config["items"].is_file() else "--code-only"
    run(python, "-m", "bot", flag, root=source, env=environment)
    run(python, "-m", "unittest", "discover", "-s", "tests", root=source, env=environment)


def database_copy(source, destination):
    with sqlite3.connect(source.resolve().as_uri() + "?mode=ro", uri=True) as original:
        with sqlite3.connect(destination) as target:
            original.backup(target)


def backup(root=ROOT):
    config = settings(root)
    directory = config["data"] / "backups"
    directory.mkdir(mode=0o700, exist_ok=True)
    name = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ") + ".zip"
    path = directory / name
    # Schon während des Schreibens ausschließlich für den Eigentümer lesbar.
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "wb") as output, tempfile.TemporaryDirectory() as temporary:
        with ZipFile(output, "w", ZIP_DEFLATED) as archive:
            archive.write(root / ".env", "config/.env")
            for key in ("items", "decks"):
                if config[key].is_file():
                    copy = Path(temporary) / f"{key}.db"
                    database_copy(config[key], copy)
                    archive.write(copy, f"data/{key}.db")
            for filename in ("runtime.json", "emojis.json"):
                file = config["data"] / filename
                if file.is_file():
                    archive.write(file, f"data/{filename}")
            custom = config["data"] / "locales"
            if custom.is_dir():
                for file in sorted(custom.glob("*.json")):
                    archive.write(file, "data/locales/" + file.name)
            archive.writestr("version.json", json.dumps({
                "commit": run("git", "rev-parse", "HEAD", root=root, capture=True),
                "created_utc": datetime.now(timezone.utc).isoformat(),
            }))
    return path


def require_clean_tree(root=ROOT):
    if run("git", "status", "--porcelain", "--untracked-files=no", root=root, capture=True):
        raise RuntimeError("Lokale Änderungen an Programmdateien vorhanden. Vor dem Update committen oder sichern.")


def service_active():
    if os.name == "nt" or not shutil.which("systemctl"):
        return False
    result = subprocess.run(["systemctl", "is-active", SERVICE],
        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
    return result.returncode == 0 and result.stdout.strip() == "active"


def write_runtime(config, python):
    path = config["data"] / "runtime.json"
    temporary = path.with_suffix(".tmp")
    # Venv-Symlinks nicht auf den globalen Interpreter auflösen.
    temporary.write_text(json.dumps({"python": str(python.absolute())}) + "\n")
    os.replace(temporary, path)


def control_service(action, root=ROOT):
    prefix = [] if not hasattr(os, "geteuid") or os.geteuid() == 0 else ["sudo"]
    run(*prefix, "systemctl", action, SERVICE, root=root)


def wait_for_service(config, timeout=45):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if not service_active():
            raise RuntimeError("Der aktualisierte Bot-Dienst ist ausgefallen.")
        if (config["data"] / "ready.json").is_file():
            return
        time.sleep(1)
    raise RuntimeError("Der aktualisierte Bot hat sich nicht rechtzeitig bei Discord angemeldet.")


def apply_update(target, root=ROOT):
    require_clean_tree(root)
    previous = run("git", "rev-parse", "HEAD", root=root, capture=True)
    target = run("git", "rev-parse", "--verify", target + "^{commit}", root=root, capture=True)
    if previous == target:
        print("Kirim-DE ist aktuell.")
        return
    run("git", "merge-base", "--is-ancestor", previous, target, root=root)
    config = settings(root)
    runtime = config["data"] / "runtime.json"
    previous_runtime = runtime.read_bytes() if runtime.exists() else None
    saved = backup(root)
    print(f"Sicherung erstellt: {saved}")
    # Eine neue Umgebung verhindert, dass fehlgeschlagene Updates alte Pakete ändern.
    new_environment = config["data"] / "venvs" / target
    with tempfile.TemporaryDirectory(prefix="kirim-stage-") as temporary:
        stage = Path(temporary) / "source"
        run("git", "worktree", "add", "--detach", stage, target, root=root)
        try:
            python = install_dependencies(new_environment, source=stage)
            check_bot(python, source=stage, config_root=root)
        finally:
            run("git", "worktree", "remove", "--force", stage, root=root)
    was_running = service_active()
    if was_running:
        control_service("stop", root=root)
        (config["data"] / "ready.json").unlink(missing_ok=True)
    applied = False
    try:
        # Git lehnt überschreibende Änderungen und divergierende Historien ab.
        run("git", "merge", "--ff-only", target, root=root)
        applied = True
        write_runtime(config, python)
        if was_running:
            control_service("start", root=root)
            wait_for_service(config)
    except BaseException:
        if applied:
            run("git", "reset", "--keep", previous, root=root)
        if previous_runtime is None:
            runtime.unlink(missing_ok=True)
        else:
            runtime.write_bytes(previous_runtime)
        if was_running:
            control_service("start", root=root)
        raise
    print(f"Update abgeschlossen: {target[:12]}.")
    if not was_running:
        print("Kein systemd-Dienst aktiv. Einen laufenden Konsolenprozess bitte manuell neu starten.")


def update(root=ROOT):
    require_clean_tree(root)
    remote = run("git", "remote", "get-url", "origin", root=root, capture=True)
    if remote not in {REPOSITORY, REPOSITORY.removesuffix(".git"), "git@github.com:xLordTime/Kirim-DE.git"}:
        raise RuntimeError("origin muss auf xLordTime/Kirim-DE zeigen.")
    run("git", "fetch", "--no-tags", "origin", "main", root=root)
    apply_update("FETCH_HEAD", root=root)


def import_database(source, root=ROOT, decks=False):
    if not source.is_file():
        raise RuntimeError("Die angegebene Datenbank existiert nicht.")
    with source.open("rb") as stream:
        if stream.read(16) != b"SQLite format 3\x00":
            raise RuntimeError("Keine SQLite-Datenbank. Eine Git-LFS-Zeigerdatei reicht nicht aus.")
    config = settings(root)
    target = config["decks" if decks else "items"]
    if source.resolve() == target.resolve():
        raise RuntimeError("Quelle und Ziel sind identisch.")
    if service_active():
        raise RuntimeError("Den Bot-Dienst vor einem Datenbankimport stoppen.")
    with sqlite3.connect(source.resolve().as_uri() + "?mode=ro", uri=True) as db:
        if db.execute("PRAGMA quick_check").fetchone()[0] != "ok":
            raise RuntimeError("Die Datenbank ist beschädigt.")
        tables = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        required = {"deck"} if decks else {"locale_en", "items", "spells", "mobs", "pets", "fish", "effects", "spell_effects", "statcaps"}
        if required - tables:
            raise RuntimeError("Inkompatible Datenbank; fehlend: " + ", ".join(sorted(required - tables)))
    if target.exists():
        print(f"Sicherung: {backup(root)}")
    target.parent.mkdir(parents=True, exist_ok=True)
    descriptor, name = tempfile.mkstemp(prefix="kirim-db-", suffix=".db", dir=target.parent)
    os.close(descriptor)
    temporary = Path(name)
    try:
        database_copy(source, temporary)
        os.replace(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)
    print(f"Datenbank importiert: {target}")


def service_template(root=ROOT):
    if os.name == "nt":
        raise RuntimeError("systemd ist nur für Linux verfügbar.")
    import getpass
    text = f"""[Unit]
Description=Kirim-DE Wizard101 Discord Bot
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User={getpass.getuser()}
WorkingDirectory="{root}"
ExecStart="{sys.executable}" "{root / 'server.py'}" run
Restart=on-failure
RestartSec=10
TimeoutStopSec=30
UMask=0077
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=full

[Install]
WantedBy=multi-user.target
"""
    destination = root / SERVICE
    destination.write_text(text)
    print(f"{destination} erstellt. Installieren mit:")
    print(f"sudo cp '{destination}' /etc/systemd/system/{SERVICE}")
    print(f"sudo systemctl daemon-reload\nsudo systemctl enable --now {SERVICE}")


def main():
    if sys.version_info < (3, 11):
        raise SystemExit("Python 3.11 oder neuer ist erforderlich.")
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for command in ("setup", "run", "check", "update", "backup", "service"):
        sub.add_parser(command)
    importer = sub.add_parser("import-db")
    importer.add_argument("source", type=Path)
    importer.add_argument("--decks", action="store_true")
    emoji_parser = sub.add_parser("emojis", help="App-Emojis verwalten")
    emoji_commands = emoji_parser.add_subparsers(dest="emoji_command", required=True)
    emoji_commands.add_parser("sync", help="Fehlende Wizard101-Symbole in die Discord-App importieren")
    args = parser.parse_args()
    try:
        ensure_env()
        if args.command == "run":
            os.chdir(ROOT)
            os.execv(str(active_python()), [str(active_python()), "-m", "bot"])
        elif args.command == "service":
            service_template()
        elif args.command == "check":
            check_bot(active_python())
        else:
            with maintenance_lock():
                if args.command == "setup":
                    python = install_dependencies(ROOT / ".venv")
                    check_bot(python)
                    if not settings()["items"].is_file():
                        print("Programm ist eingerichtet. Zum Spielen noch eine wizdb-Datenbank importieren.")
                elif args.command == "update":
                    update()
                elif args.command == "backup":
                    print(backup())
                elif args.command == "import-db":
                    import_database(args.source, decks=args.decks)
                elif args.command == "emojis":
                    run(active_python(), "-m", "bot.emoji_sync")
    except (RuntimeError, OSError, sqlite3.Error, subprocess.CalledProcessError) as error:
        raise SystemExit(f"Kirim-DE: {error}")


if __name__ == "__main__":
    main()
