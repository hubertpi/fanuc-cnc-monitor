"""Generate a restricted binding from an immutable, hash-checked upstream source.

FANUC copyright and upstream license must be reviewed independently before
distributing builds. This script never fetches or copies native SDK binaries.
"""
import hashlib
import json
import re
import sys
import urllib.request
from pathlib import Path

REVISION = "b9080d0938757789159714c38305fe559728e146"
HERE = Path(__file__).resolve().parent


def select_linux64(source):
    """Resolve only the pinned binding's simple conditional compilation syntax.

    Never inspect dormant Windows/program-number imports as active ABI. Unknown
    expressions fail the build rather than silently picking a layout.
    """
    symbols = {"LINUX64"}
    stack = []
    active = True
    output = []
    def evaluate(expression):
        expression = expression.strip()
        if expression.startswith("(") and expression.endswith(")"):
            expression = expression[1:-1].strip()
        match = re.fullmatch(r"(!?)\s*([A-Za-z_][A-Za-z_0-9]*)", expression)
        if not match:
            raise ValueError("Unsupported binding preprocessor expression")
        enabled = match[2] in symbols
        return not enabled if match[1] else enabled
    for line in source.splitlines(keepends=True):
        directive = re.match(r"\s*#(if|elif|else|endif)\b(.*)", line)
        if not directive:
            if re.match(r"\s*#(?:define|undef)\b", line):
                raise ValueError("Unexpected binding symbol mutation")
            if active:
                output.append(line)
            continue
        action, expression = directive.groups()
        if action == "if":
            selected = evaluate(expression)
            stack.append([active, selected, False])
            active = active and selected
        elif not stack:
            raise ValueError("Unbalanced binding preprocessor")
        elif action == "elif":
            parent, matched, seen_else = stack[-1]
            if seen_else:
                raise ValueError("Branch after else")
            selected = evaluate(expression)
            active = parent and not matched and selected
            stack[-1][1] = matched or selected
        elif action == "else":
            parent, matched, seen_else = stack[-1]
            if seen_else:
                raise ValueError("Duplicate else")
            active = parent and not matched
            stack[-1][2] = True
        else:
            active = stack.pop()[0]
    if stack:
        raise ValueError("Unclosed binding preprocessor")
    return "".join(output)


def restrict(source, allowed):
    source = select_linux64(source)
    source = re.sub(r"(?m)^\s*//.*$", "", source)
    # Match the complete attribute+extern declaration; no string-prefix permission.
    pattern = re.compile(r'\[DllImport\([^\n]*\)\]\s*public static extern [^;]+;', re.MULTILINE)
    def replacement(match):
        declaration = match.group()
        name = re.search(r'public static extern\s+\w+\s+(\w+)\s*\(', declaration).group(1)
        entry = re.search(r'EntryPoint\s*=\s*"([^"]+)"', declaration)
        if name in allowed and entry and entry.group(1) != name:
            raise ValueError("Approved method is mapped to a different native entry point")
        return declaration if name in allowed else "// Unapproved native entry point removed by Fanuc CNC Monitor."
    result = pattern.sub(replacement, source)
    methods = set(re.findall(r'public static extern\s+\w+\s+(\w+)\s*\(', result))
    imports = re.findall(r'\[DllImport\(', result)
    if methods != allowed or len(imports) != len(re.findall(r'public static extern', result)):
        raise ValueError("Binding shape changed or native declaration was not recognized; refuse build")
    return "// Modified for Fanuc CNC Monitor: only explicit read/session imports retained.\n" + result


def verify_source(raw, expected):
    # Git's Windows checkout may change LF to CRLF. Pin canonical Git blob
    # bytes, so the Linux Docker build verifies the actual upstream source.
    canonical = raw.replace(b"\r\n", b"\n")
    if hashlib.sha256(canonical).hexdigest() != expected:
        raise ValueError("Upstream binding hash mismatch")
    return canonical.decode("utf-8-sig")


def main():
    lock = json.loads((HERE / "upstream.lock.json").read_text())
    raw = Path(sys.argv[1]).read_bytes() if len(sys.argv) > 1 else urllib.request.urlopen(
        f"https://raw.githubusercontent.com/Ladder99/fanuc-driver/{REVISION}/fanuc/fwlib.cs", timeout=30).read()
    allow = json.loads((HERE / "allowlist.json").read_text())
    output = restrict(verify_source(raw, lock["binding_sha256"]), set(allow["read"] + allow["session"]))
    (HERE / "RestrictedFocas.generated.cs").write_text(output, encoding="utf-8")
    print("Verified and restricted FOCAS binding generated; native binaries excluded")


if __name__ == "__main__":
    main()
