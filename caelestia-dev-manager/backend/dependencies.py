"""Read distribution metadata without importing component code or contacting an index."""
import json
import re
import shutil
from email.parser import Parser

from packaging.requirements import InvalidRequirement, Requirement
from packaging.utils import canonicalize_name
from packaging.version import InvalidVersion

from backend.paths import SafetyError, no_symlinks


def clean_output(value):
    if isinstance(value, bytes):
        value = value.decode("utf-8", errors="replace")
    value = re.sub(r"\x1b\[[0-9;]*[A-Za-z]", "", value or "")
    # pip may print authenticated index URLs. Never persist their credentials or query tokens.
    value = re.sub(r"https?://[^\s<>'\"]+", "[redacted URL]", value)
    value = re.sub(r"(?i)\b(password|token|api[_-]?key)=\S+", r"\1=[redacted]", value)
    return value[-16000:].strip()


def failure_report(manifest, stage, error):
    output = clean_output("\n".join(clean_output(getattr(error, key, "")) for key in ("stdout", "stderr")))
    reported = []
    for pattern in (r"No matching distribution found for ([^\n]+)",
                    r"Could not find a version that satisfies the requirement ([^\n]+)"):
        for match in re.findall(pattern, output, re.IGNORECASE):
            requirement = match.split(" (from ")[0].strip()
            if requirement not in reported:
                reported.append(requirement)
    if type(error).__name__ == "TimeoutExpired":
        reason = "Preparation timed out; package availability could not be established."
    elif re.search(r"ReadTimeout|ConnectTimeout|ConnectionError|ProxyError|SSLError|CERTIFICATE_VERIFY_FAILED|Temporary failure|Connection broken|Could not fetch|Network is unreachable|Name or service not known", output, re.I):
        reason = "Network, proxy, TLS or package-index access failed; this does not establish that a package is missing."
    elif reported:
        reason = "No matching binary wheel was found for the reported requirement, Python version and configured index."
    elif "ResolutionImpossible" in output or "conflicting dependencies" in output.lower():
        reason = "The declared package versions have a dependency conflict."
    elif stage == "environment":
        reason = "The component's Python virtual environment could not be created."
    else:
        reason = "Dependency preparation failed; inspect the captured output below."
    return {"component_id": manifest["id"], "component_name": manifest["name"], "stage": stage,
            "requirements": manifest.get("dependencies", {}).get("python", []),
            "reported_requirements": reported, "reason": reason,
            "exit_code": getattr(error, "returncode", None), "output": output or clean_output(str(error))}


class DependencyError(SafetyError):
    def __init__(self, report):
        self.report = report
        names = ", ".join(report["reported_requirements"]) or "See preparation details"
        super().__init__(f"{report['component_name']} ({report['component_id']}): dependency preparation failed. {names}. {report['reason']}")

    def details(self):
        return (str(self) + "\n\nRequested Python dependencies:\n" + "\n".join(self.report["requirements"]) +
                "\n\nStage: " + self.report["stage"] + "\nPython version: " + self.report.get("python_version", "unknown") +
                "\n\nCaptured output (URLs redacted):\n" + self.report["output"] +
                "\n\nInstallation has not proceeded. Review the requirement, Python compatibility and index/network settings, then retry Install. "
                "Binary-wheel-only preparation remains enforced; system packages are never installed automatically.")


def distributions(environment):
    """Inspect METADATA as data; do not run the environment interpreter or import its packages."""
    no_symlinks(environment)
    versions = {}
    for site in environment.glob("lib/python*/site-packages"):
        no_symlinks(site)
        for info in site.glob("*.dist-info/METADATA"):
            no_symlinks(info)
            if info.stat().st_size > 1024 * 1024:
                continue
            metadata = Parser().parsestr(info.read_text(encoding="utf-8"))
            if metadata.get("Name") and metadata.get("Version"):
                versions[canonicalize_name(metadata["Name"])] = metadata["Version"]
    return versions


def python_version(environment):
    """venv records its actual interpreter version; it can differ from the manager's."""
    try:
        config = no_symlinks(environment / "pyvenv.cfg")
        if config.stat().st_size <= 65536:
            match = re.search(r"^version\s*=\s*(\S+)", config.read_text(encoding="utf-8"), re.MULTILINE)
            if match: return match.group(1)
    except (OSError, ValueError):
        pass
    return "unknown"


def report(manifest, environment, marker=None, failure=None):
    deps = manifest.get("dependencies", {})
    tools = [{"requirement": name, "status": "available" if shutil.which(name) else "missing",
              "path": shutil.which(name)} for name in deps.get("system", [])]
    inspection_error = ""
    try:
        versions = distributions(environment)
        prepared = marker is None
        if marker is not None:
            prepared = no_symlinks(marker).is_file() and json.loads(marker.read_text()).get("dependencies") == deps.get("python", [])
    except (OSError, ValueError, UnicodeError, AttributeError) as error:
        versions, prepared = {}, False
        inspection_error = clean_output(str(error))
    packages = []
    for requirement in deps.get("python", []):
        try:
            req = Requirement(requirement)
        except InvalidRequirement:
            packages.append({"requirement": requirement, "status": "invalid requirement", "installed_version": None})
            continue
        version = versions.get(canonicalize_name(req.name))
        try:
            matches = version is not None and req.specifier.contains(version, prereleases=True)
        except InvalidVersion:
            matches = False
        status = "prepared" if matches and prepared else "installed; preparation incomplete" if matches else "version mismatch" if version else "missing" if environment.is_dir() else "not prepared"
        packages.append({"requirement": requirement, "status": status, "installed_version": version})
    error = None
    if failure is not None:
        try:
            candidate = json.loads(no_symlinks(failure).read_text())
            if (isinstance(candidate, dict) and candidate.get("component_id") == manifest["id"]
                    and isinstance(candidate.get("reason"), str) and isinstance(candidate.get("output"), str)
                    and isinstance(candidate.get("reported_requirements"), list)
                    and all(isinstance(x, str) for x in candidate["reported_requirements"])):
                error = candidate
        except (OSError, ValueError):
            pass
    ready = not inspection_error and all(x["status"] == "available" for x in tools) and all(x["status"] == "prepared" for x in packages)
    return {"ready": ready, "environment": str(environment), "python_version": python_version(environment), "system": tools, "python": packages,
            "inspection_error": inspection_error, "last_preparation_error": error}
