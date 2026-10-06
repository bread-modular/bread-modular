"""Explicit pinned acquisition only. No install, PATH change or online execution."""
import json
import os
import platform
import posixpath
import tarfile
import time
import urllib.request
import zipfile
from pathlib import Path, PurePosixPath

from safety import (GateError, RUNTIME, digest, require, safe_path, tree_hashes,
                    write_json)

PINS = {
    "freerouting": {
        "version": "2.5.0", "tag": "v2.5.0", "license": "GPL-3.0",
        "name": "freerouting-2.5.0.jar", "size": 64599107,
        "sha256": "f6f51bb02245e8e717f9359bd260cc9c5c0b1bc0acc8b7cb2cd5b8ffeb5de3c7",
        "url": "https://github.com/freerouting/freerouting/releases/download/v2.5.0/freerouting-2.5.0.jar",
        "metadata": "https://api.github.com/repos/freerouting/freerouting/releases/tags/v2.5.0"},
    "jre": {
        "version": "25.0.4.1+1", "tag": "jdk-25.0.4.1+1", "license": "GPL-2.0 with Classpath Exception + bundled notices",
        "name": "OpenJDK25U-jre_x64_linux_hotspot_25.0.4.1_1.tar.gz", "size": 61718288,
        "sha256": "1731a34baadec5479258ea0202e4d5d865d2efeee60cb0c7d7eb056fe96ca219",
        "url": "https://github.com/adoptium/temurin25-binaries/releases/download/jdk-25.0.4.1%2B1/OpenJDK25U-jre_x64_linux_hotspot_25.0.4.1_1.tar.gz",
        "metadata": "https://api.github.com/repos/adoptium/temurin25-binaries/releases/tags/jdk-25.0.4.1%2B1"},
}
LICENSE_URL = "https://raw.githubusercontent.com/freerouting/freerouting/v2.5.0/LICENSE"
LICENSE_SHA = "e1c0ad728983d8a57335e52cf1064f1affd1d454173d8cebd3ed8b4a72b48704"
TRUSTED_HOSTS = {"github.com", "api.github.com", "release-assets.githubusercontent.com",
                 "objects.githubusercontent.com", "raw.githubusercontent.com"}
JRE_DIR = "jdk-25.0.4.1+1-jre"


def architecture():
    require(platform.system() == "Linux" and platform.machine() == "x86_64",
            "pinned runtime supports Linux x86_64 ONLY; no alternative download")


def trusted_url(url):
    from urllib.parse import urlsplit
    parsed = urlsplit(url)
    require(parsed.scheme == "https" and parsed.hostname in TRUSTED_HOSTS and
            not parsed.username and not parsed.password and parsed.port in (None, 443),
            "untrusted download/redirect URL")


class TrustedRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        trusted_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def download(url, path, max_bytes, expected=None):
    trusted_url(url)
    path = safe_path(path)
    require(not path.exists(), "download overwrite refused")
    start = time.monotonic()
    opener = urllib.request.build_opener(TrustedRedirect())
    request = urllib.request.Request(url, headers={"User-Agent": "bread-bounded-routing/1"})
    with opener.open(request, timeout=30) as response, path.open("xb") as stream:
        trusted_url(response.url)
        count = 0
        while True:
            require(time.monotonic() - start < 180, "download time budget exceeded")
            data = response.read(1024 * 1024)
            if not data:
                break
            count += len(data)
            require(count <= max_bytes, "download size limit exceeded")
            stream.write(data)
    if expected:
        require(digest(path) == expected, "download SHA256 mismatch")
    return {"url": url, "sha256": digest(path), "bytes": count,
            "duration_seconds": round(time.monotonic()-start, 3)}


def verify_metadata(data, pin):
    require(data.get("tag_name") == pin["tag"] and not data.get("draft") and not data.get("prerelease"),
            "pinned release metadata mismatch")
    assets = [x for x in data.get("assets", []) if x.get("name") == pin["name"]]
    require(len(assets) == 1, "missing/ambiguous pinned release asset")
    asset = assets[0]
    require(asset.get("digest") == "sha256:"+pin["sha256"] and
            asset.get("size") == pin["size"] and asset.get("browser_download_url") == pin["url"],
            "pinned asset metadata mismatch")
    return {"release_id": data["id"], "asset_id": asset["id"], "published_at": data["published_at"],
            "asset_updated_at": asset["updated_at"]}


def safe_extract(archive, dest):
    """Validate entire archive before writes. Symlinks last, never extract through them."""
    dest = safe_path(dest)
    require(not dest.exists(), "extraction overwrite refused")
    with tarfile.open(archive, "r:gz") as tar:
        members = tar.getmembers()
        require(0 < len(members) <= 10000, "archive member count limit")
        entries, links, total = {}, set(), 0
        for member in members:
            name = member.name.rstrip("/")
            parts = PurePosixPath(name).parts
            require(name and not name.startswith("/") and "\\" not in name and
                    all(x not in (".", "..") for x in parts) and len(name) < 512,
                    "unsafe archive path")
            require(name == str(PurePosixPath(name)) and name not in entries,
                    "duplicate/noncanonical archive path")
            require(parts[0] == JRE_DIR, "unexpected archive root")
            require(member.isdir() or member.isfile() or member.issym(), "unsupported archive member type")
            if member.issym():
                target = member.linkname
                require(target and not target.startswith("/") and "\\" not in target, "unsafe symlink target")
                resolved = posixpath.normpath(posixpath.join(posixpath.dirname(name), target))
                require(resolved == JRE_DIR or resolved.startswith(JRE_DIR+"/"), "archive symlink escape")
                links.add(name)
            total += member.size
            require(total <= 400*1024*1024, "archive expansion limit")
            entries[name] = member
        for name, member in entries.items():
            require(not any(str(p) in links for p in PurePosixPath(name).parents), "archive symlink ancestor")
            if member.issym():
                target = posixpath.normpath(posixpath.join(posixpath.dirname(name), member.linkname))
                require(target in entries and not entries[target].issym(), "dangling/chained archive symlink")
        dest.mkdir(mode=0o700)
        for name, member in entries.items():
            if member.issym():
                continue
            path = dest / name
            path.parent.mkdir(parents=True, exist_ok=True)
            if member.isdir():
                path.mkdir(exist_ok=True)
            else:
                with tar.extractfile(member) as src, path.open("xb") as output:
                    import shutil
                    shutil.copyfileobj(src, output)
                path.chmod(0o755 if member.mode & 0o111 else 0o644)
        for name in links:
            path = dest / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.symlink_to(entries[name].linkname)
    return dest / JRE_DIR


def prepare(allow_downloads=False):
    require(allow_downloads, "prepare-runtime requires explicit --allow-downloads")
    architecture()
    root = safe_path(RUNTIME)
    require(not root.exists(), "runtime directory already exists; doctor checks it, no overwrite")
    root.mkdir(mode=0o700)
    result = {"status": "failed", "pins": PINS, "downloads": {}, "metadata": {}, "execution": "NONE"}
    try:
        for key,pin in PINS.items():
            metadata = root / (key+"-release.json")
            result["downloads"][key+"-metadata"] = download(pin["metadata"], metadata, 2*1024*1024)
            result["metadata"][key] = verify_metadata(json.loads(metadata.read_text()), pin)
            result["downloads"][key] = download(pin["url"], root/pin["name"], pin["size"], pin["sha256"])
            require((root/pin["name"]).stat().st_size == pin["size"], "artifact size mismatch")
        result["downloads"]["license"] = download(LICENSE_URL, root/"Freerouting-LICENSE.txt", 40000, LICENSE_SHA)
        jre = safe_extract(root/PINS["jre"]["name"], root/"extracted")
        release = (jre/"release").read_text()
        require('JAVA_VERSION="25.0.4.1"' in release and 'OS_ARCH="x86_64"' in release and
                'OS_NAME="Linux"' in release and 'IMPLEMENTOR="Eclipse Adoptium"' in release,
                "JRE release identity mismatch")
        java = jre/"bin/java"
        elf = java.read_bytes()[:20]
        require(elf[:6] == b"\x7fELF\x02\x01" and elf[18:20] == b"\x3e\x00", "not Linux x64 ELF Java")
        with zipfile.ZipFile(root/PINS["freerouting"]["name"]) as jar:
            require("app/freerouting/Freerouting.class" in jar.namelist(), "not expected Freerouting JAR")
            result["jar_notice_entries"] = [x for x in jar.namelist() if any(n in x.lower() for n in ("license", "notice", "copying"))]
        notices = [p for p in (jre/"legal").rglob("*") if p.is_file()]
        require((jre/"legal/java.base/LICENSE").is_file() and
                (jre/"legal/java.base/ADDITIONAL_LICENSE_INFO").is_file() and len(notices) > 10,
                "JRE legal notices missing")
        result.update(status="prepared", java_relative=str(java.relative_to(root)),
                      jre_tree=tree_hashes(root/"extracted", allow_links=True),
                      notices={str(p.relative_to(root)): digest(p) for p in notices})
    except Exception as exc:
        result["error"] = f"{type(exc).__name__}: {exc}"
        raise
    finally:
        write_json(root/"provenance.json", result, exclusive=True)
    return result


def validate_runtime():
    architecture()
    root = safe_path(RUNTIME)
    require((root/"provenance.json").is_file(), "pinned runtime missing; explicitly prepare-runtime first")
    manifest = json.loads((root/"provenance.json").read_text())
    require(manifest.get("status") == "prepared" and manifest.get("pins") == PINS, "runtime provenance mismatch")
    for key,pin in PINS.items():
        require(digest(safe_path(root/pin["name"])) == pin["sha256"], f"{key} artifact SHA256 mismatch")
        verify_metadata(json.loads((root/(key+"-release.json")).read_text()), pin)
    require(digest(safe_path(root/"Freerouting-LICENSE.txt")) == LICENSE_SHA, "license mismatch")
    require(tree_hashes(root/"extracted", allow_links=True) == manifest["jre_tree"], "extracted JRE tree changed")
    java = safe_path(root/manifest["java_relative"])
    require(os.access(java, os.X_OK), "local Java not executable")
    return java, root/PINS["freerouting"]["name"], manifest
