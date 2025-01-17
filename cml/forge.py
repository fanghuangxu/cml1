import minecraft_launcher_lib
from minecraft_launcher_lib.helper import download_file, get_library_path, get_jar_mainclass, parse_maven_metadata, empty
from minecraft_launcher_lib.install import install_minecraft_version, install_libraries
from typing import Dict, List, Any, Union, Optional
from minecraft_launcher_lib.exceptions import VersionNotFound
from minecraft_launcher_lib.types import CallbackDict
import subprocess
import platform
import tempfile
import random
import zipfile
import shutil
import json
import os

__all__ = ["install_forge_version", "run_forge_installer", "list_forge_versions", "find_forge_version", "is_forge_version_valid", "supports_automatic_install"]


def extract_file(handler: zipfile.ZipFile, zip_path: str, extract_path: str) -> None:
    """
    Extract a file from a zip handler into the given path
    """
    try:
        os.makedirs(os.path.dirname(extract_path))
    except Exception:
        pass
    with handler.open(zip_path, "r") as f:
        with open(extract_path, "wb") as w:
            w.write(f.read())


def get_data_library_path(libname: str, path: str) -> str:
    """
    Turns the libname into a path
    """
    # Remove the []
    libname = libname[1:-1]
    libpath = os.path.join(path, "libraries")
    parts = libname.split(":")
    if len(parts) == 3:  # 如果只有三部分，假设最后一部分是版本和额外信息的组合
        base_path, libname, combined = parts
        # 假设 combined 是 "version(extra)" 的格式，你可以进一步拆分
        parts = combined.split("(")
        if len(parts) == 2:
            version, extra = parts
        else:
    # 如果拆分结果不符合预期，可以选择设置默认值或者抛出异常
            version = parts[0]
            extra = ""  # 设置默认值为空字符串或者其他默认值
        extra = extra[:-1]  # 移除末尾的括号
    else:
        base_path, libname, version, extra = parts
    for i in base_path.split("."):
        libpath = os.path.join(libpath, i)
    try:
        extra, fileend = extra.split("@")
    except ValueError:
        fileend = "jar"
    libpath = os.path.join(libpath, libname, version, libname + "-" + version + "-" + extra + "." + fileend)
    return libpath


def forge_processors(data: Dict[str, Any], minecraft_directory: Union[str, os.PathLike], lzma_path: str, installer_path: str, callback: CallbackDict, java: str = None) -> None:
    """
    Run the processors of the install_profile.json
    """
    path = str(minecraft_directory)
    argument_vars = {"{MINECRAFT_JAR}": os.path.join(path, "versions", data["minecraft"], data["minecraft"] + ".jar")}
    for key, value in data["data"].items():
        if value["client"].startswith("[") and value["client"].endswith("]"):
            argument_vars["{" + key + "}"] = get_data_library_path(value["client"], path)
        else:
            argument_vars["{" + key + "}"] = value["client"]
    root_path = os.path.join(tempfile.gettempdir(), "forge-root-" + str(random.randrange(1, 100000)))
    argument_vars["{INSTALLER}"] = installer_path
    argument_vars["{BINPATCH}"] = lzma_path
    argument_vars["{ROOT}"] = root_path
    argument_vars["{SIDE}"] = "client"
    if platform.system() == "Windows":
        classpath_seperator = ";"
    else:
        classpath_seperator = ":"
    callback.get("setMax", empty)(len(data["processors"]))
    for count, i in enumerate(data["processors"]):
        if "client" not in i.get("sides", ["client"]):
            # Skip server side only processors
            continue
        callback.get("setStatus", empty)("Running processor " + i["jar"])
        # Get the classpath
        classpath = ""
        for c in i["classpath"]:
            classpath = classpath + get_library_path(c, path) + classpath_seperator
        classpath = classpath + get_library_path(i["jar"], path)
        mainclass = get_jar_mainclass(get_library_path(i["jar"], path))
        command = [java or "java", "-cp", classpath, mainclass]
        for c in i["args"]:
            var = argument_vars.get(c, c)
            if var.startswith("[") and var.endswith("]"):
                command.append(get_library_path(var[1:-1], path))
            else:
                command.append(var)
        for key, value in argument_vars.items():
            for pos in range(len(command)):
                command[pos] = command[pos].replace(key, value)
        subprocess.call(command)
        callback.get("setProgress", empty)(count)
    if os.path.exists(root_path):
        shutil.rmtree(root_path)


def install_forge_version(versionid: str, path: str, callback: Optional[CallbackDict] = None, java: Optional[str] = None) -> None:
    """
    Installs a forge version. Fore more information look at the documentation.
    """
    if callback is None:
        callback = {}
    FORGE_DOWNLOAD_URL = "https://files.minecraftforge.net/maven/net/minecraftforge/forge/{version}/forge-{version}-installer.jar"
    temp_file_path = os.path.join(tempfile.gettempdir(), "forge-installer-" + str(random.randrange(1, 100000)) + ".tmp")
    if not download_file(FORGE_DOWNLOAD_URL.format(version=versionid), temp_file_path, callback):
        raise VersionNotFound(versionid)
    zf = zipfile.ZipFile(temp_file_path, "r")
    # Read the install_profile.json
    with zf.open("install_profile.json", "r") as f:
        version_content = f.read()
    version_data = json.loads(version_content)
    forge_version_id = version_data["version"]
    # Make sure, the base version is installed
    install_minecraft_version(version_data["minecraft"], path, callback=callback)
    # Install all needed libs from install_profile.json
    install_libraries(version_data, path, callback)
    # Extract the version.json
    version_json_path = os.path.join(path, "versions", forge_version_id, forge_version_id + ".json")
    extract_file(zf, "version.json", version_json_path)
    # Extract forge libs from the installer
    forge_lib_path = os.path.join(path, "libraries", "net", "minecraftforge", "forge", versionid)
    try:
        extract_file(zf, "maven/net/minecraftforge/forge/{version}/forge-{version}.jar".format(version=versionid), os.path.join(forge_lib_path, "forge-" + versionid + ".jar"))
        extract_file(zf, "maven/net/minecraftforge/forge/{version}/forge-{version}-universal.jar".format(version=versionid), os.path.join(forge_lib_path, "forge-" + versionid + "-universal.jar"))
    except KeyError:
        pass
    # Extract the client.lzma
    lzma_path = os.path.join(tempfile.gettempdir(), "lzma-" + str(random.randrange(1, 100000)) + ".tmp")
    try:
        extract_file(zf, "data/client.lzma", lzma_path)
    except KeyError:
        pass
    zf.close()
    # Install the rest with the vanilla function
    install_minecraft_version(forge_version_id, path, callback=callback)
    # Run the processors
    forge_processors(version_data, path, lzma_path, temp_file_path, callback, java)
    # Delete the temporary files
    os.remove(temp_file_path)
    if os.path.isfile(lzma_path):
        os.remove(lzma_path)


def run_forge_installer(version: str, java: Optional[str] = None) -> None:
    """
    Run the forge installer of the given forge version
    """
    FORGE_DOWNLOAD_URL = "https://files.minecraftforge.net/maven/net/minecraftforge/forge/{version}/forge-{version}-installer.jar"
    temp_file_path = os.path.join(tempfile.gettempdir(), "forge-" + str(random.randrange(1, 100000)) + ".tmp")
    download_file(FORGE_DOWNLOAD_URL.format(version=version), temp_file_path, {})
    subprocess.call([java or "java", "-jar", temp_file_path])
    os.remove(temp_file_path)


def list_forge_versions() -> List[str]:
    """
    Returns a list of all forge versions
    """
    MAVEN_METADATA_URL = "https://files.minecraftforge.net/maven/net/minecraftforge/forge/maven-metadata.xml"
    return parse_maven_metadata(MAVEN_METADATA_URL)["versions"]


def find_forge_version(vanilla_version: str) -> Optional[str]:
    """
    Find the latest forge version that is compatible to the given vanilla version
    """
    version_list = list_forge_versions()
    for i in version_list:
        version_split = i.split("-")
        if version_split[0] == vanilla_version:
            return i
    return None


def is_forge_version_valid(forge_version: str) -> bool:
    """
    Checks if a forge version is valid
    """
    forge_version_list = list_forge_versions()
    return forge_version in forge_version_list


def supports_automatic_install(forge_version: str) -> bool:
    """
    Checks if install_forge_version() supports the given forge version
    """
    try:
        vanilla_version, forge = forge_version.split("-")
        version_split = vanilla_version.split(".")
        version_number = int(version_split[1])
        if version_number >= 13:
            return True
        else:
            return False
    except Exception:
        return False


def forge_to_installed_version(forge_version: str) -> str:
    """
    Returns the Version under which Forge will be installed from the given Forge version.
    Raises a ValueError if the Version is invalid.
    """
    try:
        vanilla_part, forge_part = forge_version.split("-")
        return f"{vanilla_part}-forge-{forge_part}"
    except ValueError:
        raise ValueError(f"{forge_version} is not a valid forge version") from None

def find_forge_version(version):
    return minecraft_launcher_lib.forge.find_forge_version(vanilla_version=version)