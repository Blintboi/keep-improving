"""Official Minecraft Java data and dedicated runtimes; no generic Java match."""
import os
from pathlib import Path
import ntpath
from .model import Game, within


def runtime_roots():
    return [str(Path(os.environ.get(key, default)) / "Minecraft Launcher" / "runtime")
            for key, default in (("ProgramFiles(x86)", r"C:\Program Files (x86)"),
                                 ("ProgramFiles", r"C:\Program Files"))] + [
        str(Path(os.environ.get("APPDATA", "")) / ".minecraft" / "runtime")]


def is_runtime(path, roots=None):
    return (ntpath.basename(path).lower() in {"java.exe", "javaw.exe"}
            and any(within(path, root) for root in (runtime_roots() if roots is None else roots)))


def scan(data_root=None):
    root = Path(data_root) if data_root else Path(os.environ.get("APPDATA", "")) / ".minecraft"
    if root.is_dir() and (root / "versions").is_dir():
        return [Game("minecraft:java", "Minecraft Java Edition", "Minecraft", str(root))]
    return []


def launcher():
    for key, default in (("ProgramFiles(x86)", r"C:\Program Files (x86)"),
                         ("ProgramFiles", r"C:\Program Files")):
        path = Path(os.environ.get(key, default)) / "Minecraft Launcher" / "MinecraftLauncher.exe"
        if path.is_file():
            return str(path)
    return ""
