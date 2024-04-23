import minecraft_launcher_lib
class NotServerError(Exception):
    def __init__(self, m):
        super().__init__(m)
def get_server_list(mc_dir=str()):
    try:
        with open(f'{mc_dir}\\server.txt') as server_file:
            serverlist=server_file.read()
            # 使用 splitlines() 方法将其转换为列表
            server_version_list = serverlist.splitlines()
            return server_version_list
    except FileNotFoundError:
        raise NotServerError(f'“{mc_dir}”中没有安装mc服务器')

def get_options():
    return minecraft_launcher_lib.utils.generate_test_options()

def get_installed_version(mc_dir=str()):    
    return minecraft_launcher_lib.utils.get_installed_versions(minecraft_directory=mc_dir)

def get_minecraft_directory():
    return minecraft_launcher_lib.utils.get_minecraft_directory()

def get_install_version_list():
    return minecraft_launcher_lib.utils.get_version_list()