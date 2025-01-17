from minecraft_launcher_lib.helper import download_file, get_requests_response_cache, parse_maven_metadata, empty
from minecraft_launcher_lib.exceptions import VersionNotFound, UnsupportedVersion, ExternalProgramError
from minecraft_launcher_lib.types import FabricMinecraftVersion, FabricLoader, CallbackDict
from minecraft_launcher_lib.install import install_minecraft_version
from typing import List, Optional, Union
from minecraft_launcher_lib.utils import is_version_valid
import subprocess
import tempfile
import random
import os


def get_all_minecraft_versions() -> List[FabricMinecraftVersion]:
    """
    Returns all available Minecraft Versions for fabric
    """
    FABRIC_MINECARFT_VERSIONS_URL = "https://meta.fabricmc.net/v2/versions/game"
    return get_requests_response_cache(FABRIC_MINECARFT_VERSIONS_URL).json()


def get_stable_minecraft_versions() -> List[str]:
    """
    Returns a list which only contains the stable Minecraft versions that supports fabric
    """
    minecraft_versions = get_all_minecraft_versions()
    stable_versions = []
    for i in minecraft_versions:
        if i["stable"] is True:
            stable_versions.append(i["version"])
    return stable_versions


def get_latest_minecraft_version() -> str:
    """
    Returns the latest unstable Minecraft versions that supports fabric. This could be a snapshot.
    """
    minecraft_versions = get_all_minecraft_versions()
    return minecraft_versions[0]["version"]


def get_latest_stable_minecraft_version() -> str:
    """
    Returns the latest stable Minecraft version that supports fabric
    """
    stable_versions = get_stable_minecraft_versions()
    return stable_versions[0]


def is_minecraft_version_supported(version: str) -> bool:
    """
    Checks if a Minecraft version supported by fabric
    """
    minecraft_versions = get_all_minecraft_versions()
    for i in minecraft_versions:
        if i["version"] == version:
            return True
    return False


def get_all_loader_versions() -> List[FabricLoader]:
    """
    Returns all loader versions
    """
    FABRIC_LOADER_VERSIONS_URL = "https://meta.fabricmc.net/v2/versions/loader"
    return get_requests_response_cache(FABRIC_LOADER_VERSIONS_URL).json()


def get_latest_loader_version() -> str:
    """
    Get the latest loader version
    """
    loader_versions = get_all_loader_versions()
    return loader_versions[0]["version"]


def get_latest_installer_version() -> str:
    """
    Returns the latest installer version
    """
    FABRIC_INSTALLER_MAVEN_URL = "https://maven.fabricmc.net/net/fabricmc/fabric-installer/maven-metadata.xml"
    return parse_maven_metadata(FABRIC_INSTALLER_MAVEN_URL)["latest"]


def install_fabric(minecraft_version: str, minecraft_directory: Union[str, os.PathLike], loader_version: str = None, callback: Optional[CallbackDict] = None, java: str = None) -> None:
    """
    Install a fabric version
    """
    path = str(minecraft_directory)
    if not callback:
        callback = {}
    # Check if the given version exists
    if not is_version_valid(minecraft_version, minecraft_directory):
        raise VersionNotFound(minecraft_version)
    # Check if the given Minecraft version supported
    if not is_minecraft_version_supported(minecraft_version):
        raise UnsupportedVersion(minecraft_version)
    # Get latest loader version if not given
    if not loader_version:
        loader_version = get_latest_loader_version()
    # Make sure the Minecraft version is installed
    install_minecraft_version(minecraft_version, path, callback=callback)
    # Get installer version
    installer_version = get_latest_installer_version()
    installer_download_url = f"https://maven.fabricmc.net/net/fabricmc/fabric-installer/{installer_version}/fabric-installer-{installer_version}.jar"
    # Generate a temporary path for downloading the installer
    installer_path = os.path.join(tempfile.gettempdir(), f"fabric-installer-{random.randrange(100,10000)}.tmp")
    # Download the installer
    download_file(installer_download_url, installer_path, callback=callback)
    # Run the installer see https://fabricmc.net/wiki/install#cli_installation
    callback.get("setStatus", empty)("Running fabric installer")
    command = [java or "java", "-jar", installer_path, "client", "-dir", path, "-mcversion", minecraft_version, "-loader", loader_version, "-noprofile", "-snapshot"]
    result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode != 0:
        raise ExternalProgramError(command, result.stdout, result.stderr)
    # Delete the installer we don't need them anymore
    os.remove(installer_path)
    # Install all libs of fabric
    fabric_minecraft_version = f"fabric-loader-{loader_version}-{minecraft_version}"
    install_minecraft_version(fabric_minecraft_version, path, callback=callback)
