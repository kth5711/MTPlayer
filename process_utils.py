import os
import subprocess


def hidden_subprocess_kwargs() -> dict:
    if os.name != "nt":
        return {}
    kwargs: dict = {}
    creationflags = int(getattr(subprocess, "CREATE_NO_WINDOW", 0) or 0)
    if creationflags:
        kwargs["creationflags"] = creationflags
    startup_cls = getattr(subprocess, "STARTUPINFO", None)
    if startup_cls is not None:
        startupinfo = startup_cls()
        startupinfo.dwFlags |= int(getattr(subprocess, "STARTF_USESHOWWINDOW", 0) or 0)
        startupinfo.wShowWindow = int(getattr(subprocess, "SW_HIDE", 0) or 0)
        kwargs["startupinfo"] = startupinfo
    return kwargs
