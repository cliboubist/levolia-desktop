#!/usr/bin/env python3
"""Re-apply the Levolia text rebranding after an upstream merge.

Idempotent. Run from the repo root:

    python3 scripts/levolia/rebrand.py

Structural changes (remote-only onboarding, settings, icons, French locale,
update guard) live in the git history of the `levolia` branch and merge
normally. This script only handles the high-churn text substitutions in the
desktop locale files and main-process strings, so those files can be taken
from upstream on conflict and rebranded again.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DESKTOP = ROOT / "apps" / "desktop"
LOCALES = ["en", "ar", "ja", "zh", "zh-hant", "ru"]
TEST_FILES_WITH_BRAND_STRINGS = [
    "src/app/updates-overlay.blockers.test.tsx",
    "src/i18n/runtime.test.ts",
    "src/lib/version-status.test.ts",
    "src/app/settings/connections-registry.test.tsx",
    "src/app/settings/gateway-settings.test.tsx",
    "src/components/assistant-ui/thread/status-tail-only.test.tsx",
    "src/components/assistant-ui/thread/streaming.test.tsx",
    "src/components/desktop-install-overlay.test.tsx",
]

# Exact substitutions for user-facing examples that still mention hermes in lowercase.
EN_EXACT = {
    "Path prefixes are supported, for example /hermes.": "Path prefixes are supported, for example /levolia.",
    "urlPlaceholder: 'https://hermes.example.com'": "urlPlaceholder: 'https://levolia.example.com'",
    "placeholder: '@hermes:example.org'": "placeholder: '@levolia:example.org'",
    "'/quit': 'exit hermes'": "'/quit': 'exit Levolia'",
    "sshHermesPathDesc: 'Full path to the remote hermes binary. Blank = auto-detect.'":
        "sshHermesPathDesc: 'Full path to the Levolia agent binary on the server. Blank = auto-detect.'",
    "timedOut: 'Timed out waiting for the gateway. Is `hermes gateway` running?'":
        "timedOut: 'Timed out waiting for the server. Is the Levolia agent running?'",
    "remoteUrlPlaceholder: 'https://gateway.example.com/hermes'": "remoteUrlPlaceholder: 'https://votre-entreprise.levolia.ai'",
}

# Onboarding copy rewritten for the remote-only flow (English source of truth).
EN_ONBOARDING = {
    "setupChoiceTitle: 'Set up Levolia'": "setupChoiceTitle: 'Connect Levolia'",
    "'Connect this app to a Levolia gateway you already run, or install Levolia locally on this computer.'":
        "'Enter the server address and the access token provided by Levolia to link this computer to your agent.'",
    "remoteSetupTitle: 'Connect to existing Levolia'": "remoteSetupTitle: 'Connect to your Levolia server'",
    "remoteSetupDesc: 'Enter your gateway URL. Levolia will detect whether it needs a token or browser sign-in.'":
        "remoteSetupDesc: 'Enter the server address and the access token you received from Levolia. Nothing is installed on this computer.'",
    "remoteUrlTitle: 'Gateway URL'": "remoteUrlTitle: 'Server address'",
    "remoteUrlDesc: 'Use the base URL of the Levolia gateway, including https:// when remote.'":
        "remoteUrlDesc: 'The address of your Levolia server, starting with https://.'",
    "probeError: 'Could not reach that Levolia gateway.'":
        "probeError: 'Could not reach that Levolia server. Check the address and your internet connection.'",
    "tokenTitle: 'Session token'": "tokenTitle: 'Access token'",
    "tokenDesc: 'Paste the session token from the remote gateway .env file.'": "tokenDesc: 'Paste the access token provided by Levolia.'",
    "pasteSessionToken: 'Paste session token'": "pasteSessionToken: 'Paste access token'",
    "enterUrlFirst: 'Enter a gateway URL first.'": "enterUrlFirst: 'Enter the server address first.'",
    "incompleteTokenTest: 'Enter a session token before testing this gateway.'":
        "incompleteTokenTest: 'Enter the access token before testing the connection.'",
}

KEY_RE = re.compile(r"^([ \t]*)([A-Za-z]*)Levolia([A-Za-z]*):", re.M)
LITERAL_RE = re.compile(r"'(?:[^'\\\n]|\\.)*'|`(?:[^`\\]|\\.)*`|\"(?:[^\"\\\n]|\\.)*\"")


def brand_text(s: str) -> str:
    s = s.replace("Hermes Desktop", "Levolia").replace("Hermes Cloud", "Nous Cloud").replace("Hermes", "Levolia")
    s = s.replace("Levolia Cloud", "Nous Cloud")
    # Object keys must keep their original identifiers (they are typed).
    return KEY_RE.sub(lambda m: f"{m.group(1)}{m.group(2)}Hermes{m.group(3)}:", s)


def rebrand_locales() -> None:
    for name in LOCALES:
        p = DESKTOP / "src" / "i18n" / f"{name}.ts"
        s = brand_text(p.read_text())
        if name == "en":
            for a, b in {**EN_ONBOARDING, **EN_EXACT}.items():
                s = s.replace(a, b)
        p.write_text(s)
        print(f"rebranded {p.relative_to(ROOT)}")


def rebrand_main_process() -> None:
    p = DESKTOP / "electron" / "main.ts"
    out = []
    for line in p.read_text().split("\n"):
        stripped = line.lstrip()
        if stripped.startswith("//") or stripped.startswith("*"):
            out.append(line)
            continue
        out.append(LITERAL_RE.sub(lambda m: re.sub(r"\bHermes\b(?![A-Za-z_])", "Levolia", m.group(0)), line))
    s = "\n".join(out)
    s = s.replace("process.env.HERMES_DESKTOP_APP_NAME || 'Hermes'", "process.env.HERMES_DESKTOP_APP_NAME || 'Levolia'")
    p.write_text(s)
    print(f"rebranded {p.relative_to(ROOT)}")


def rebrand_tests() -> None:
    for rel in TEST_FILES_WITH_BRAND_STRINGS:
        p = DESKTOP / rel
        if not p.exists():
            continue
        s = brand_text(p.read_text())
        if rel.endswith("runtime.test.ts"):
            s = s.replace("Hermes 桌面版", "Levolia 桌面版")
        if rel.endswith("desktop-install-overlay.test.tsx"):
            s = s.replace("PlaceholderText('https://gateway.example.com/hermes')", "PlaceholderText('https://votre-entreprise.levolia.ai')")
            s = s.replace("'Gateway URL'", "'Server address'").replace("'Paste session token'", "'Paste access token'")
        p.write_text(s)
        print(f"rebranded {p.relative_to(ROOT)}")


def main() -> int:
    rebrand_locales()
    rebrand_main_process()
    rebrand_tests()
    print("done — now run: cd apps/desktop && npm run typecheck && npm run test:ui")
    return 0


if __name__ == "__main__":
    sys.exit(main())
